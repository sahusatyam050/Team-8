from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
from typing import Dict, Any, List, Optional
import os


class MongoDB:
    """MongoDB handler for storing scraped data."""
    
    def __init__(self, connection_string: str = None):
        """
        Initialize MongoDB connection.
        
        Args:
            connection_string: MongoDB connection URI
        """
        self.connection_string = connection_string or os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.client = None
        self.db = None
        self.collection = None
        
    def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            self.client.admin.command('ping')
            
            # Get database and collection
            self.db = self.client['web_scraper']
            self.collection = self.db['scrapes']
            
            # Create indexes
            self.collection.create_index("url")
            self.collection.create_index("scraped_at")
            
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"MongoDB connection failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if MongoDB is connected."""
        if not self.client:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except:
            return False
    
    def save_scrape(self, url: str, title: str, data: Dict[str, Any], 
                    indexed_in_rag: bool = False) -> Optional[str]:
        """
        Save scraped data to MongoDB.
        
        Args:
            url: URL that was scraped
            title: Page title
            data: Complete scraped data
            indexed_in_rag: Whether data is indexed in ChromaDB
            
        Returns:
            Inserted document ID as string, or None if failed
        """
        if not self.is_connected():
            if not self.connect():
                return None
        
        try:
            document = {
                "url": url,
                "title": title,
                "scraped_at": datetime.utcnow(),
                "data": data,
                "indexed_in_rag": indexed_in_rag,
                "status": "success",
                "error": None
            }
            
            result = self.collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Failed to save scrape: {e}")
            return None
    
    def get_scrape_by_id(self, scrape_id: str) -> Optional[Dict[str, Any]]:
        """
        Get scraped data by ID.
        
        Args:
            scrape_id: MongoDB ObjectId as string
            
        Returns:
            Scrape document or None
        """
        if not self.is_connected():
            if not self.connect():
                return None
        
        try:
            from bson.objectid import ObjectId
            result = self.collection.find_one({"_id": ObjectId(scrape_id)})
            if result:
                result['_id'] = str(result['_id'])
                result['scraped_at'] = result['scraped_at'].isoformat()
            return result
        except Exception as e:
            print(f"Failed to get scrape: {e}")
            return None
    
    def get_scrape_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent scrape for a URL.
        
        Args:
            url: URL to search for
            
        Returns:
            Most recent scrape document or None
        """
        if not self.is_connected():
            if not self.connect():
                return None
        
        try:
            result = self.collection.find_one(
                {"url": url},
                sort=[("scraped_at", -1)]
            )
            if result:
                result['_id'] = str(result['_id'])
                result['scraped_at'] = result['scraped_at'].isoformat()
            return result
        except Exception as e:
            print(f"Failed to get scrape by URL: {e}")
            return None
    
    def get_all_scrapes(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """
        Get all scrapes with pagination.
        
        Args:
            limit: Maximum number of results
            skip: Number of results to skip
            
        Returns:
            List of scrape documents
        """
        if not self.is_connected():
            if not self.connect():
                return []
        
        try:
            cursor = self.collection.find().sort("scraped_at", -1).skip(skip).limit(limit)
            results = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                doc['scraped_at'] = doc['scraped_at'].isoformat()
                results.append(doc)
            return results
        except Exception as e:
            print(f"Failed to get scrapes: {e}")
            return []
    
    def get_scrape_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored scrapes.
        
        Returns:
            Dictionary with statistics
        """
        if not self.is_connected():
            if not self.connect():
                return {"total": 0, "indexed": 0}
        
        try:
            total = self.collection.count_documents({})
            indexed = self.collection.count_documents({"indexed_in_rag": True})
            
            return {
                "total_scrapes": total,
                "indexed_in_rag": indexed,
                "not_indexed": total - indexed
            }
        except Exception as e:
            print(f"Failed to get stats: {e}")
            return {"total": 0, "indexed": 0}
    
    def update_rag_status(self, scrape_id: str, indexed: bool) -> bool:
        """
        Update RAG indexing status.
        
        Args:
            scrape_id: MongoDB ObjectId as string
            indexed: New indexing status
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            if not self.connect():
                return False
        
        try:
            from bson.objectid import ObjectId
            result = self.collection.update_one(
                {"_id": ObjectId(scrape_id)},
                {"$set": {"indexed_in_rag": indexed}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Failed to update RAG status: {e}")
            return False
    
    def delete_scrape(self, scrape_id: str) -> bool:
        """
        Delete a scrape record.
        
        Args:
            scrape_id: MongoDB ObjectId as string
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            if not self.connect():
                return False
        
        try:
            from bson.objectid import ObjectId
            result = self.collection.delete_one({"_id": ObjectId(scrape_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Failed to delete scrape: {e}")
            return False
    
    def search_scrapes(self, query: str) -> List[Dict[str, Any]]:
        """
        Search scrapes by URL or title.
        
        Args:
            query: Search query
            
        Returns:
            List of matching scrape documents
        """
        if not self.is_connected():
            if not self.connect():
                return []
        
        try:
            cursor = self.collection.find({
                "$or": [
                    {"url": {"$regex": query, "$options": "i"}},
                    {"title": {"$regex": query, "$options": "i"}}
                ]
            }).sort("scraped_at", -1).limit(50)
            
            results = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                doc['scraped_at'] = doc['scraped_at'].isoformat()
                results.append(doc)
            return results
        except Exception as e:
            print(f"Failed to search scrapes: {e}")
            return []
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()


# Global MongoDB instance
mongodb = MongoDB()
