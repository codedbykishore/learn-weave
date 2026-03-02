import logging
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from ..config.chroma_settings import (
    CHROMA_HOST, CHROMA_PORT, CHROMA_COLLECTION_NAME, 
    EMBEDDING_MODEL, CHROMA_CLIENT_TYPE
)

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        self.client = None
        self.embedding_model = None
        self._initialized = False
        
        try:
            # Use HTTP client to connect to separate ChromaDB container
            if CHROMA_CLIENT_TYPE == "http":
                self.client = chromadb.HttpClient(
                    host=CHROMA_HOST,
                    port=CHROMA_PORT
                )
            else:
                # Fallback for development
                self.client = chromadb.PersistentClient(path="./chroma_db")
                
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            self._initialized = True
            logger.info("VectorService initialized successfully")
        except Exception as e:
            logger.warning(f"VectorService initialization failed (ChromaDB not available): {e}")
            logger.warning("Vector search features will be disabled")

    def create_collection(self, collection_id: str):
        """Create a new collection in the vector store"""
        if not self._initialized:
            logger.warning("VectorService not available, skipping create_collection")
            return
        try:
            self.client.create_collection(name=collection_id)
        except Exception as e:
            print(f"Error creating collection {collection_id}: {e}")

    def create_collection_by_course_id(self, course_id: int):
        """Create a collection for a specific course"""
        collection_id = "course_" + str(course_id)
        self.create_collection(collection_id)
    
    def add_content_by_course_id(self, course_id: int, content_id: str, text: str, metadata: Dict):
        """Add content to vector store"""
        if not self._initialized:
            logger.warning("VectorService not available, skipping add_content")
            return
        embedding = self.embedding_model.encode([text])
        self.client.get_or_create_collection("course_" + str(course_id)).add(
            documents=[text],
            embeddings=embedding.tolist(),
            metadatas=[metadata],
            ids=[content_id]
        )
    
    def search_by_course_id(self, course_id: int, query: str, n_results: int = 5, filter_metadata: Optional[Dict] = None):
        """Search for similar content"""
        if not self._initialized:
            logger.warning("VectorService not available, returning empty results")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        query_embedding = self.embedding_model.encode([query])
        results = self.client.get_or_create_collection("course_" + str(course_id)).query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results,
            where=filter_metadata
        )
        return results

    
    def delete_content_by_course_id(self, course_id: int, content_id: str):
        """Delete content from vector store"""
        if not self._initialized:
            return
        try:
            self.client.get_or_create_collection("course_" + str(course_id)).delete(ids=[content_id])
        except Exception as e:
            print(f"Error deleting content {content_id}: {e}")
    
    def update_content_by_course_id(self, course_id: int, content_id: str, text: str, metadata: Dict):
        """Update existing content"""
        self.delete_content_by_course_id(course_id, content_id)
        self.add_content_by_course_id(course_id, content_id, text, metadata)

    def get_collection_by_course_id(self, course_id: int):
        """Get collection by course ID"""
        return self.client.get_or_create_collection("course_" + str(course_id))
