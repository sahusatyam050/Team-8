import os
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
#from langchain_text_splitter import RecursiveCharacterTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

from groq import Groq
import json


class RAGEngine:
    """RAG engine for indexing scraped content and answering questions."""
    
    def __init__(self, groq_api_key: str = None):
        # Initialize ChromaDB (local persistent storage)
        self.chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="web_scraper_rag",
            metadata={"description": "Scraped website content for RAG"}
        )
        
        # Initialize embedding model (local, no API needed)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Initialize Groq client for LLM
        self.groq_client = None
        if groq_api_key:
            self.groq_client = Groq(api_key=groq_api_key)
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into semantic chunks."""
        chunks = self.text_splitter.split_text(text)
        return chunks
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks."""
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    
    def index_content(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Index scraped website content into the vector database.
        
        Args:
            scraped_data: The complete scraped data from scraper.py
            
        Returns:
            Dict with indexing statistics
        """
        url = scraped_data['url']
        
        # Combine all text content
        all_text = []
        
        # Add metadata
        metadata = scraped_data['metadata']
        if metadata.get('title'):
            all_text.append(f"Title: {metadata['title']}")
        if metadata.get('description'):
            all_text.append(f"Description: {metadata['description']}")
        
        # Add headings
        for level, headings in scraped_data['text']['headings'].items():
            for heading in headings:
                all_text.append(f"Heading: {heading}")
        
        # Add paragraphs
        all_text.extend(scraped_data['text']['paragraphs'])
        
        # Combine into one text
        combined_text = "\n\n".join(all_text)
        
        # Chunk the text
        chunks = self.chunk_text(combined_text)
        
        if not chunks:
            return {
                "success": False,
                "error": "No text content to index"
            }
        
        # Create embeddings
        embeddings = self.create_embeddings(chunks)
        
        # Prepare data for ChromaDB
        ids = [f"{url}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source_url": url,
                "chunk_index": i,
                "title": metadata.get('title', ''),
                "total_chunks": len(chunks)
            }
            for i in range(len(chunks))
        ]
        
        # Add to ChromaDB
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        
        return {
            "success": True,
            "url": url,
            "chunks_indexed": len(chunks),
            "title": metadata.get('title', 'Unknown')
        }
    
    def query_rag(self, question: str, n_results: int = 5) -> Dict[str, Any]:
        """
        Query the RAG system with a question.
        
        Args:
            question: User's question
            n_results: Number of relevant chunks to retrieve
            
        Returns:
            Dict with answer and citations
        """
        if not self.groq_client:
            return {
                "success": False,
                "error": "Groq API key not configured. Set GROQ_API_KEY environment variable."
            }
        
        # Check if there's any indexed content
        collection_count = self.collection.count()
        if collection_count == 0:
            return {
                "success": False,
                "error": "No content indexed yet. Please scrape and index a website first."
            }
        
        # Create embedding for the question
        question_embedding = self.create_embeddings([question])[0]
        
        # Search for relevant chunks
        results = self.collection.query(
            query_embeddings=[question_embedding],
            n_results=min(n_results, collection_count)
        )
        
        # Extract retrieved documents and metadata
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        
        if not documents:
            return {
                "success": False,
                "error": "No relevant content found"
            }
        
        # Build context from retrieved chunks
        context = "\n\n".join([
            f"[Source {i+1}: {meta['source_url']}]\n{doc}"
            for i, (doc, meta) in enumerate(zip(documents, metadatas))
        ])
        
        # Create prompt for LLM
        prompt = f"""You are a helpful assistant that answers questions based on the provided context from scraped websites.

Context from indexed websites:
{context}

Question: {question}

Instructions:
- Answer the question based ONLY on the provided context
- If the context doesn't contain enough information to answer, say so
- Be concise and accurate
- Mention which source(s) you used in your answer

Answer:"""
        
        try:
            # Generate answer using Groq
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that answers questions based on scraped website content. Always cite your sources."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1024
            )
            
            answer = completion.choices[0].message.content
            
            # Extract unique sources
            sources = []
            seen_urls = set()
            for meta in metadatas:
                url = meta['source_url']
                if url not in seen_urls:
                    sources.append({
                        "url": url,
                        "title": meta.get('title', 'Unknown')
                    })
                    seen_urls.add(url)
            
            return {
                "success": True,
                "answer": answer,
                "sources": sources,
                "chunks_used": len(documents)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"LLM generation failed: {str(e)}"
            }
    
    def get_indexed_sources(self) -> List[Dict[str, Any]]:
        """Get list of all indexed sources."""
        try:
            # Get all documents
            all_data = self.collection.get()
            
            # Extract unique sources
            sources = {}
            for metadata in all_data['metadatas']:
                url = metadata['source_url']
                if url not in sources:
                    sources[url] = {
                        "url": url,
                        "title": metadata.get('title', 'Unknown'),
                        "chunks": 0
                    }
                sources[url]["chunks"] += 1
            
            return list(sources.values())
        except Exception as e:
            return []
    
    def delete_source(self, source_url: str) -> Dict[str, Any]:
        """Delete all chunks from a specific source."""
        try:
            # Get all IDs for this source
            results = self.collection.get(
                where={"source_url": source_url}
            )
            
            if results['ids']:
                self.collection.delete(
                    ids=results['ids']
                )
                return {
                    "success": True,
                    "deleted_chunks": len(results['ids'])
                }
            else:
                return {
                    "success": False,
                    "error": "Source not found"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def clear_all(self) -> Dict[str, Any]:
        """Clear all indexed content."""
        try:
            # Delete the collection and recreate it
            self.chroma_client.delete_collection(name="web_scraper_rag")
            self.collection = self.chroma_client.get_or_create_collection(
                name="web_scraper_rag",
                metadata={"description": "Scraped website content for RAG"}
            )
            return {"success": True, "message": "All content cleared"}
        except Exception as e:
            return {"success": False, "error": str(e)}
