"""
Embedding service using HuggingFace free inference API or local models.
"""
import numpy as np
from typing import List, Optional
import httpx

from app.core.config import settings


class EmbeddingService:
    """
    Generate text embeddings using HuggingFace Inference API (free tier)
    or local sentence-transformers.
    """
    
    def __init__(self, use_local: bool = False):
        """
        Initialize embedding service.
        
        Args:
            use_local: Use local sentence-transformers instead of API
        """
        self.use_local = use_local
        self.model_name = settings.HF_EMBEDDING_MODEL
        self.api_token = settings.HF_API_TOKEN
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_name}"
        
        self._local_model = None
        self._http_client = None
    
    def _get_http_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=60.0)
        return self._http_client
    
    def _get_local_model(self):
        """Load local sentence-transformers model."""
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self.model_name)
        return self._local_model
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
        """
        embeddings = self.embed_batch([text])
        return embeddings[0]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Clean texts
        texts = [self._clean_text(t) for t in texts]
        
        if self.use_local:
            return self._embed_local(texts)
        else:
            return self._embed_api(texts)
    
    def _clean_text(self, text: str) -> str:
        """Clean text for embedding."""
        if not text:
            return ""
        # Truncate very long texts
        max_length = 8192
        if len(text) > max_length:
            text = text[:max_length]
        return text.strip()
    
    def _embed_api(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using HuggingFace API."""
        client = self._get_http_client()
        
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        # Process in batches to avoid API limits
        batch_size = 10
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = client.post(
                    self.api_url,
                    headers=headers,
                    json={"inputs": batch, "options": {"wait_for_model": True}},
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Handle different response formats
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item[0], list):
                            # Mean pooling for token embeddings
                            embedding = np.mean(item, axis=0).tolist()
                        else:
                            embedding = item
                        all_embeddings.append(embedding)
                else:
                    raise ValueError(f"Unexpected API response format: {type(result)}")
                    
            except httpx.HTTPError as e:
                # Fallback to local if API fails
                print(f"HuggingFace API error, falling back to local: {e}")
                return self._embed_local(texts)
        
        return all_embeddings
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model."""
        model = self._get_local_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        # all-MiniLM-L6-v2 produces 384-dimensional embeddings
        return 384
    
    def close(self):
        """Clean up resources."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
