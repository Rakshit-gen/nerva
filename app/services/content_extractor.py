"""
Content extraction from various sources: PDF, Text, YouTube, URLs.
"""
import base64
import io
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


class ContentExtractor:
    """Extract text content from various sources."""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        )
    
    async def extract(
        self,
        source_type: str,
        source_url: Optional[str] = None,
        source_content: Optional[str] = None,
    ) -> str:
        """
        Extract text from the given source.
        
        Args:
            source_type: One of 'pdf', 'text', 'youtube', 'url'
            source_url: URL for youtube/url sources
            source_content: Raw text or base64 PDF content
            
        Returns:
            Extracted text content
        """
        if source_type == "text":
            return self._extract_text(source_content)
        elif source_type == "pdf":
            return await self._extract_pdf(source_content)
        elif source_type == "youtube":
            return await self._extract_youtube(source_url)
        elif source_type == "url":
            return await self._extract_url(source_url)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
    
    def _extract_text(self, content: str) -> str:
        """Extract from raw text."""
        if not content:
            raise ValueError("No text content provided")
        return content.strip()
    
    async def _extract_pdf(self, content: str) -> str:
        """Extract text from base64-encoded PDF."""
        if not content:
            raise ValueError("No PDF content provided")
        
        try:
            # Decode base64
            pdf_bytes = base64.b64decode(content)
            
            # Use PyMuPDF (fitz) for extraction
            import fitz
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            
            for page in doc:
                text_parts.append(page.get_text())
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            return full_text.strip()
            
        except Exception as e:
            raise ValueError(f"Failed to extract PDF content: {str(e)}")
    
    async def _extract_youtube(self, url: str) -> str:
        """Extract transcript from YouTube video."""
        if not url:
            raise ValueError("No YouTube URL provided")
        
        # Extract video ID
        video_id = self._extract_youtube_id(url)
        if not video_id:
            raise ValueError("Could not extract YouTube video ID")
        
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            # Try to get transcript
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Prefer manually created transcripts, then auto-generated
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                except Exception:
                    # Try any available transcript
                    for t in transcript_list:
                        transcript = t
                        break
            
            if not transcript:
                raise ValueError("No transcript available for this video")
            
            # Fetch and combine transcript
            transcript_data = transcript.fetch()
            text_parts = [entry['text'] for entry in transcript_data]
            
            return " ".join(text_parts)
            
        except Exception as e:
            raise ValueError(f"Failed to extract YouTube transcript: {str(e)}")
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def _extract_url(self, url: str) -> str:
        """Extract text content from a web URL."""
        if not url:
            raise ValueError("No URL provided")
        
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            if "text/html" in content_type:
                return self._parse_html(response.text)
            elif "text/plain" in content_type:
                return response.text.strip()
            else:
                # Try to parse as HTML anyway
                return self._parse_html(response.text)
                
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch URL: {str(e)}")
    
    def _parse_html(self, html: str) -> str:
        """Parse HTML and extract main text content."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # Try to find main content
        main_content = None
        
        # Look for common content containers
        for selector in ['article', 'main', '[role="main"]', '.content', '#content', '.post', '.entry']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.body or soup
        
        # Get text
        text = main_content.get_text(separator='\n', strip=True)
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
