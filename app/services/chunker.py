"""
Text chunking for embedding and retrieval.
"""
import re
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class Chunk:
    """Represents a text chunk."""
    content: str
    index: int
    token_count: int
    metadata: Dict[str, Any]


class TextChunker:
    """
    Split text into chunks for embedding and retrieval.
    Uses semantic-aware chunking with overlap.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target token count per chunk
            chunk_overlap: Number of tokens to overlap between chunks
            min_chunk_size: Minimum chunk size to keep
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Split text into chunks.
        
        Args:
            text: Input text to chunk
            metadata: Optional metadata to attach to chunks
            
        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        
        # Clean text
        text = self._clean_text(text)
        
        # Split into sentences first
        sentences = self._split_sentences(text)
        
        # Group sentences into chunks
        chunks = self._group_sentences(sentences)
        
        # Create Chunk objects
        result = []
        for i, chunk_text in enumerate(chunks):
            token_count = self._estimate_tokens(chunk_text)
            if token_count >= self.min_chunk_size:
                result.append(Chunk(
                    content=chunk_text,
                    index=i,
                    token_count=token_count,
                    metadata={
                        **metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                ))
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?;:\'"()-]', '', text)
        return text.strip()
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting that handles abbreviations
        # First, protect common abbreviations by replacing them temporarily
        abbreviations = ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'Sr.', 'Jr.', 'vs.', 'etc.', 'Inc.', 'Ltd.', 'Corp.']
        protected = text
        for abbr in abbreviations:
            protected = protected.replace(abbr, abbr.replace('.', '<DOT>'))
        
        # Split on sentence-ending punctuation followed by space
        sentences = re.split(r'[.!?]+\s+', protected)
        
        # Restore abbreviations and clean up
        result = []
        for s in sentences:
            restored = s.replace('<DOT>', '.')
            if restored.strip():
                result.append(restored.strip())
        return result
    
    def _group_sentences(self, sentences: List[str]) -> List[str]:
        """Group sentences into chunks of target size."""
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            
            # If single sentence exceeds chunk size, split it
            if sentence_tokens > self.chunk_size:
                # Flush current chunk
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # Split long sentence into smaller pieces
                words = sentence.split()
                temp_chunk = []
                temp_tokens = 0
                
                for word in words:
                    word_tokens = self._estimate_tokens(word) + 1  # +1 for space
                    if temp_tokens + word_tokens > self.chunk_size:
                        if temp_chunk:
                            chunks.append(' '.join(temp_chunk))
                        temp_chunk = [word]
                        temp_tokens = word_tokens
                    else:
                        temp_chunk.append(word)
                        temp_tokens += word_tokens
                
                if temp_chunk:
                    current_chunk = temp_chunk
                    current_tokens = temp_tokens
                continue
            
            # Check if adding sentence would exceed chunk size
            if current_tokens + sentence_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                
                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk)
                current_chunk = overlap_sentences + [sentence]
                current_tokens = sum(self._estimate_tokens(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Don't forget last chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _get_overlap_sentences(self, sentences: List[str]) -> List[str]:
        """Get sentences for overlap from previous chunk."""
        if not sentences:
            return []
        
        overlap_tokens = 0
        overlap_sentences = []
        
        # Take sentences from end until we reach overlap target
        for sentence in reversed(sentences):
            sentence_tokens = self._estimate_tokens(sentence)
            if overlap_tokens + sentence_tokens > self.chunk_overlap:
                break
            overlap_sentences.insert(0, sentence)
            overlap_tokens += sentence_tokens
        
        return overlap_sentences
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count.
        Rough approximation: ~4 characters per token for English.
        """
        if not text:
            return 0
        return max(1, len(text) // 4)
    
    def chunk_with_context(
        self,
        text: str,
        title: str = None,
        source: str = None,
    ) -> List[Chunk]:
        """
        Chunk text with additional context in metadata.
        
        Args:
            text: Input text
            title: Document title
            source: Source URL or identifier
            
        Returns:
            List of chunks with context
        """
        metadata = {
            "title": title,
            "source": source,
        }
        return self.chunk(text, metadata)
