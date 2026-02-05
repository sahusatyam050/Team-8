from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import WebScraper
from rag_engine import RAGEngine
from database import mongodb
from sentiment import sentiment_analyzer
from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Web Scraper API with RAG + MongoDB + Sentiment", version="4.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG engine
groq_api_key = os.getenv("GROQ_API_KEY")
rag_engine = RAGEngine(groq_api_key=groq_api_key)

# Initialize MongoDB
mongodb.connect()

# Initialize Sentiment Analyzer
# Loaded on startup


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    success: bool
    data: Dict[str, Any] = None
    error: str = None


class IndexRequest(BaseModel):
    url: str


class IndexResponse(BaseModel):
    success: bool
    data: Dict[str, Any] = None
    error: str = None


class QueryRequest(BaseModel):
    question: str
    n_results: int = 5


class QueryResponse(BaseModel):
    success: bool
    answer: str = None
    sources: List[Dict[str, str]] = None
    chunks_used: int = None
    error: str = None


class SentimentRequest(BaseModel):
    text: str


class SentimentResponse(BaseModel):
    success: bool
    data: Dict[str, Any] = None
    error: str = None


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Web Scraper API with RAG + MongoDB",
        "version": "3.0.0",
        "endpoints": {
            "/scrape": "POST - Scrape a website",
            "/scrape-and-index": "POST - Scrape, save to MongoDB, and index for RAG",
            "/query": "POST - Ask questions about indexed content",
            "/indexed-sources": "GET - List all RAG indexed sources",
            "/scrapes": "GET - Get all scrapes from MongoDB",
            "/scrapes/{scrape_id}": "GET - Get specific scrape",
            "/scrapes/{scrape_id}": "DELETE - Delete scrape",
            "/scrapes/{scrape_id}/reindex": "POST - Re-index scrape to RAG",
            "/scrapes/search": "GET - Search scrapes",
            "/scrapes/stats": "GET - Get scraping statistics",
            "/sentiment/analyze": "POST - Analyze text sentiment",
            "/scrapes/{scrape_id}/sentiment": "GET - Get sentiment for scrape",
            "/sentiment/stats": "GET - Overall sentiment statistics",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    groq_configured = groq_api_key is not None
    mongodb_connected = mongodb.is_connected()
    sentiment_ready = sentiment_analyzer.initialized
    return {
        "status": "healthy",
        "rag_enabled": groq_configured,
        "groq_api_configured": groq_configured,
        "mongodb_connected": mongodb_connected,
        "sentiment_analysis_ready": sentiment_ready
    }


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_website(request: ScrapeRequest):
    """
    Scrape a website, save to MongoDB, and return all extracted data.
    
    Args:
        request: ScrapeRequest containing the URL to scrape
        
    Returns:
        ScrapeResponse with scraped data or error message
    """
    try:
        # Create scraper instance
        scraper = WebScraper(request.url)
        
        # Scrape all data
        data = scraper.scrape_all()
        
        # Save to MongoDB (without RAG indexing)
        title = data.get('metadata', {}).get('title', 'Unknown')
        scrape_id = mongodb.save_scrape(
            url=request.url,
            title=title,
            data=data,
            indexed_in_rag=False  # Not indexed to RAG, just stored
        )
        
        # Add MongoDB ID to response
        if scrape_id:
            data['mongodb_id'] = scrape_id
        
        return ScrapeResponse(
            success=True,
            data=data
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@app.post("/scrape-and-index", response_model=IndexResponse)
async def scrape_and_index(request: IndexRequest):
    """
    Scrape a website, save to MongoDB, and index in RAG system.
    
    Args:
        request: IndexRequest containing the URL to scrape and index
        
    Returns:
        IndexResponse with indexing statistics and MongoDB ID
    """
    try:
        # First scrape the website
        scraper = WebScraper(request.url)
        scraped_data = scraper.scrape_all()
        
        # Save to MongoDB
        title = scraped_data.get('metadata', {}).get('title', 'Unknown')
        scrape_id = mongodb.save_scrape(
            url=request.url,
            title=title,
            data=scraped_data,
            indexed_in_rag=False
        )
        
        # Then index to RAG
        index_result = rag_engine.index_content(scraped_data)
        
        # Update MongoDB with RAG status
        if scrape_id and index_result.get('success'):
            mongodb.update_rag_status(scrape_id, True)
        
        response_data = index_result.copy() if index_result.get('success') else {}
        if scrape_id:
            response_data['mongodb_id'] = scrape_id
        
        return IndexResponse(
            success=index_result['success'],
            data=response_data if index_result['success'] else None,
            error=index_result.get('error')
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Query the RAG system with a question.
    
    Args:
        request: QueryRequest with the question and optional n_results
        
    Returns:
        QueryResponse with the answer, sources, and metadata
    """
    try:
        result = rag_engine.query_rag(request.question, request.n_results)
        
        if result['success']:
            return QueryResponse(
                success=True,
                answer=result['answer'],
                sources=result['sources'],
                chunks_used=result['chunks_used']
            )
        else:
            return QueryResponse(
                success=False,
                error=result['error']
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/indexed-sources")
async def get_indexed_sources():
    """Get list of all indexed sources."""
    try:
        sources = rag_engine.get_indexed_sources()
        return {
            "success": True,
            "sources": sources,
            "total": len(sources)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete-source")
async def delete_source(source_url: str):
    """Delete a specific source from the index."""
    try:
        result = rag_engine.delete_source(source_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear-index")
async def clear_index():
    """Clear all indexed content."""
    try:
        result = rag_engine.clear_all()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# MongoDB Endpoints

@app.get("/scrapes")
async def get_all_scrapes(limit: int = 100, skip: int = 0):
    """Get all scrapes from MongoDB."""
    try:
        scrapes = mongodb.get_all_scrapes(limit=limit, skip=skip)
        return {
            "success": True,
            "scrapes": scrapes,
            "count": len(scrapes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrapes/{scrape_id}")
async def get_scrape_by_id(scrape_id: str):
    """Get a specific scrape by ID."""
    try:
        scrape = mongodb.get_scrape_by_id(scrape_id)
        if not scrape:
            raise HTTPException(status_code=404, detail="Scrape not found")
        return {
            "success": True,
            "scrape": scrape
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scrapes/{scrape_id}")
async def delete_scrape_by_id(scrape_id: str):
    """Delete a scrape from MongoDB."""
    try:
        success = mongodb.delete_scrape(scrape_id)
        if not success:
            raise HTTPException(status_code=404, detail="Scrape not found")
        return {
            "success": True,
            "message": "Scrape deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scrapes/{scrape_id}/reindex")
async def reindex_scrape(scrape_id: str):
    """Re-index a scrape from MongoDB to RAG."""
    try:
        # Get scrape from MongoDB
        scrape = mongodb.get_scrape_by_id(scrape_id)
        if not scrape:
            raise HTTPException(status_code=404, detail="Scrape not found")
        
        # Index to RAG
        index_result = rag_engine.index_content(scrape['data'])
        
        # Update MongoDB status
        if index_result.get('success'):
            mongodb.update_rag_status(scrape_id, True)
        
        return {
            "success": index_result['success'],
            "data": index_result if index_result['success'] else None,
            "error": index_result.get('error')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrapes/search")
async def search_scrapes(q: str):
    """Search scrapes by URL or title."""
    try:
        results = mongodb.search_scrapes(q)
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrapes/stats")
async def get_scrape_stats():
    """Get scraping statistics."""
    try:
        stats = mongodb.get_scrape_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Sentiment Analysis Endpoints

@app.post("/sentiment/analyze", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    """Analyze sentiment of provided text."""
    try:
        if not sentiment_analyzer.initialized:
            return SentimentResponse(
                success=False,
                error="Sentiment analyzer not initialized"
            )
        
        result = sentiment_analyzer.analyze_text(request.text)
        return SentimentResponse(
            success=True,
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrapes/{scrape_id}/sentiment")
async def get_scrape_sentiment(scrape_id: str):
    """Get sentiment analysis for a scraped document."""
    try:
        # Get scrape from MongoDB
        scrape = mongodb.get_scrape_by_id(scrape_id)
        if not scrape:
            raise HTTPException(status_code=404, detail="Scrape not found")
        
        if not sentiment_analyzer.initialized:
            return {
                "success": False,
                "error": "Sentiment analyzer not initialized"
            }
        
        # Analyze sentiment
        analysis = sentiment_analyzer.analyze_scraped_data(scrape)
        
        return {
            "success": True,
            "sentiment": analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sentiment/stats")
async def get_sentiment_stats():
    """Get overall sentiment statistics across all scrapes."""
    try:
        if not sentiment_analyzer.initialized:
            return {
                "success": False,
                "error": "Sentiment analyzer not initialized"
            }
        
        # Get all scrapes
        scrapes = mongodb.get_all_scrapes(limit=100)
        
        if not scrapes:
            return {
                "success": True,
                "stats": {
                    "total_analyzed": 0,
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0
                }
            }
        
        # Analyze each scrape
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for scrape in scrapes[:20]:  # Limit to 20 for performance
            analysis = sentiment_analyzer.analyze_scraped_data(scrape)
            if 'summary' in analysis:
                overall = analysis['summary']['overall_sentiment']
                if overall == 'POSITIVE':
                    positive_count += 1
                elif overall == 'NEGATIVE':
                    negative_count += 1
                else:
                    neutral_count += 1
        
        total = positive_count + negative_count + neutral_count
        
        return {
            "success": True,
            "stats": {
                "total_analyzed": total,
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
                "positive_pct": round((positive_count / total * 100), 2) if total > 0 else 0,
                "negative_pct": round((negative_count / total * 100), 2) if total > 0 else 0,
                "neutral_pct": round((neutral_count / total * 100), 2) if total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
