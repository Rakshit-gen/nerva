"""
Vector store service using Qdrant Cloud (free tier).
"""
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import uuid

from app.core.config import settings
from app.services.embeddings import EmbeddingService


# Global client instance
_qdrant_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client singleton."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=60,  # Increased timeout for slow connections
        )
    return _qdrant_client


class VectorStore:
    """
    Vector storage and retrieval using Qdrant.
    Handles embedding storage and similarity search.
    """
    
    def __init__(
        self,
        collection_name: str = None,
        embedding_service: EmbeddingService = None,
    ):
        """
        Initialize vector store.
        
        Args:
            collection_name: Qdrant collection name
            embedding_service: Service for generating embeddings
        """
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.client = get_qdrant_client()
        # FORCE API usage - never load local embedding model
        self.embedding_service = embedding_service or EmbeddingService(use_local=False)
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            collections = self.client.get_collections()
            exists = any(c.name == self.collection_name for c in collections.collections)
            
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_service.dimension,
                        distance=Distance.COSINE,
                    ),
                )
        except Exception as e:
            print(f"Warning: Could not ensure collection exists: {e}")
    
    def add(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]] = None,
        ids: List[str] = None,
    ) -> List[str]:
        """
        Add texts to the vector store.
        
        Args:
            texts: List of texts to embed and store
            metadatas: Optional metadata for each text
            ids: Optional IDs (generated if not provided)
            
        Returns:
            List of point IDs
        """
        if not texts:
            return []
        
        # Generate embeddings
        embeddings = self.embedding_service.embed_batch(texts)
        
        # Prepare metadata
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        
        # Create points
        points = []
        for i, (text, embedding, metadata, point_id) in enumerate(zip(texts, embeddings, metadatas, ids)):
            payload = {
                "text": text,
                **metadata,
            }
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            ))
        
        # Upsert to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        
        return ids
    
    def search(
        self,
        query: str,
        limit: int = 5,
        filter_conditions: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar texts.
        
        Args:
            query: Search query
            limit: Maximum results to return
            filter_conditions: Optional filter conditions
            
        Returns:
            List of results with text, score, and metadata
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed(query)
        
        # Build filter
        qdrant_filter = None
        if filter_conditions:
            must_conditions = []
            for key, value in filter_conditions.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                )
            qdrant_filter = models.Filter(must=must_conditions)
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=qdrant_filter,
        )
        
        # Format results
        formatted = []
        for result in results:
            formatted.append({
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": {k: v for k, v in result.payload.items() if k != "text"},
            })
        
        return formatted
    
    def search_by_episode(
        self,
        query: str,
        episode_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific episode's content.
        
        Args:
            query: Search query
            episode_id: Episode to search within
            limit: Maximum results
            
        Returns:
            Search results
        """
        return self.search(
            query=query,
            limit=limit,
            filter_conditions={"episode_id": episode_id},
        )
    
    def delete_by_episode(self, episode_id: str) -> int:
        """
        Delete all vectors for an episode.
        
        Args:
            episode_id: Episode ID
            
        Returns:
            Number of deleted points
        """
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="episode_id",
                            match=models.MatchValue(value=episode_id),
                        )
                    ]
                )
            ),
        )
        return result.status
    
    def get_episode_chunks(
        self,
        episode_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get all chunks for an episode.
        
        Args:
            episode_id: Episode ID
            limit: Maximum chunks to return
            
        Returns:
            List of chunks with metadata
        """
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="episode_id",
                        match=models.MatchValue(value=episode_id),
                    )
                ]
            ),
            limit=limit,
        )
        
        chunks = []
        for point in results:
            chunks.append({
                "id": point.id,
                "text": point.payload.get("text", ""),
                "chunk_index": point.payload.get("chunk_index", 0),
                "metadata": point.payload,
            })
        
        # Sort by chunk index
        chunks.sort(key=lambda x: x["chunk_index"])
        
        return chunks
