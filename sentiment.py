from transformers import pipeline
from typing import Dict, List, Any
import statistics


class SentimentAnalyzer:
    """Sentiment analysis for scraped content using Hugging Face transformers."""
    
    def __init__(self):
        """Initialize the sentiment analysis pipeline."""
        try:
            # Load pre-trained sentiment analysis model
            # Using distilbert-base-uncased-finetuned-sst-2-english (fast and accurate)
            self.analyzer = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1  # CPU (use 0 for GPU if available)
            )
            self.initialized = True
        except Exception as e:
            print(f"Failed to initialize sentiment analyzer: {e}")
            self.analyzer = None
            self.initialized = False
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with label (POSITIVE/NEGATIVE) and score (0-1)
        """
        if not self.initialized or not text or len(text.strip()) == 0:
            return {"label": "NEUTRAL", "score": 0.5}
        
        try:
            # Truncate to max model length (512 tokens)
            text = text[:512]
            result = self.analyzer(text)[0]
            return {
                "label": result['label'],
                "score": round(result['score'], 4)
            }
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return {"label": "NEUTRAL", "score": 0.5}
    
    def analyze_paragraphs(self, paragraphs: List[str]) -> Dict[str, Any]:
        """
        Analyze sentiment of multiple paragraphs.
        
        Args:
            paragraphs: List of text paragraphs
            
        Returns:
            Dict with individual results and aggregate statistics
        """
        if not self.initialized or not paragraphs:
            return {
                "results": [],
                "summary": {
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0,
                    "total": 0,
                    "average_score": 0.5,
                    "overall_sentiment": "NEUTRAL"
                }
            }
        
        results = []
        positive_count = 0
        negative_count = 0
        scores = []
        
        for i, para in enumerate(paragraphs[:100]):  # Limit to 100 paragraphs
            if len(para.strip()) < 10:  # Skip very short paragraphs
                continue
                
            sentiment = self.analyze_text(para)
            results.append({
                "index": i,
                "text_preview": para[:100] + "..." if len(para) > 100 else para,
                "sentiment": sentiment['label'],
                "score": sentiment['score']
            })
            
            if sentiment['label'] == 'POSITIVE':
                positive_count += 1
                scores.append(sentiment['score'])
            elif sentiment['label'] == 'NEGATIVE':
                negative_count += 1
                scores.append(-sentiment['score'])
            else:
                scores.append(0)
        
        total = len(results)
        neutral_count = total - positive_count - negative_count
        avg_score = statistics.mean(scores) if scores else 0
        
        # Determine overall sentiment
        if avg_score > 0.2:
            overall = "POSITIVE"
        elif avg_score < -0.2:
            overall = "NEGATIVE"
        else:
            overall = "NEUTRAL"
        
        return {
            "results": results,
            "summary": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
                "total": total,
                "positive_pct": round((positive_count / total * 100), 2) if total > 0 else 0,
                "negative_pct": round((negative_count / total * 100), 2) if total > 0 else 0,
                "neutral_pct": round((neutral_count / total * 100), 2) if total > 0 else 0,
                "average_score": round(avg_score, 4),
                "overall_sentiment": overall
            }
        }
    
    def analyze_scraped_data(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze sentiment of complete scraped data.
        
        Args:
            scraped_data: Complete scraped data from MongoDB
            
        Returns:
            Dict with sentiment analysis results
        """
        if not self.initialized:
            return {"error": "Sentiment analyzer not initialized"}
        
        # Extract text data
        text_data = scraped_data.get('data', {}).get('text', {})
        paragraphs = text_data.get('paragraphs', [])
        
        if not paragraphs:
            return {
                "error": "No text content found to analyze",
                "url": scraped_data.get('url', ''),
                "title": scraped_data.get('title', '')
            }
        
        # Analyze paragraphs
        analysis = self.analyze_paragraphs(paragraphs)
        
        # Add metadata
        analysis['url'] = scraped_data.get('url', '')
        analysis['title'] = scraped_data.get('title', '')
        analysis['analyzed_at'] = scraped_data.get('scraped_at', '')
        
        return analysis
    
    def get_sentiment_label(self, score: float) -> str:
        """Convert score to label."""
        if score > 0.2:
            return "POSITIVE"
        elif score < -0.2:
            return "NEGATIVE"
        return "NEUTRAL"


# Global sentiment analyzer instance
sentiment_analyzer = SentimentAnalyzer()
