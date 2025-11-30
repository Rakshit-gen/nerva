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
        # Use realistic user-agent to avoid blocking
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.http_client = httpx.AsyncClient(
            timeout=60.0,  # Increased timeout for slow sites
            follow_redirects=True,
            headers=headers,
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
            
            if len(pdf_bytes) == 0:
                raise ValueError("PDF file is empty")
            
            # Use PyMuPDF (fitz) for extraction
            try:
                import fitz
            except ImportError:
                raise ValueError("PyMuPDF (fitz) is not installed. Please install it: pip install PyMuPDF")
            
            print(f"📄 [PDF] Extracting text from PDF ({len(pdf_bytes)} bytes)")
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            
            total_pages = len(doc)
            print(f"📄 [PDF] Processing {total_pages} pages...")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(page_text)
            
            doc.close()
            
            if not text_parts:
                raise ValueError("No text content found in PDF. The PDF may contain only images or be corrupted.")
            
            full_text = "\n\n".join(text_parts)
            cleaned_text = full_text.strip()
            
            if len(cleaned_text) < 50:
                raise ValueError(f"Extracted text is too short ({len(cleaned_text)} characters). The PDF may not contain readable text.")
            
            print(f"✅ [PDF] Successfully extracted {len(cleaned_text)} characters from {total_pages} pages")
            return cleaned_text
            
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            error_msg = str(e)
            if "not a pdf" in error_msg.lower() or "invalid" in error_msg.lower():
                raise ValueError(f"Invalid PDF file: {error_msg}")
            elif "empty" in error_msg.lower():
                raise ValueError("PDF file is empty or corrupted")
            else:
                raise ValueError(f"Failed to extract PDF content: {error_msg}")
    
    async def _extract_youtube(self, url: str) -> str:
        """Extract transcript from YouTube video."""
        if not url:
            raise ValueError("No YouTube URL provided")
        
        # Extract video ID
        video_id = self._extract_youtube_id(url)
        if not video_id:
            raise ValueError(f"Could not extract YouTube video ID from URL: {url}")
        
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            # Import error classes with fallback
            try:
                from youtube_transcript_api._errors import (
                    TranscriptsDisabled,
                    NoTranscriptFound,
                    VideoUnavailable,
                )
            except ImportError:
                # Fallback if error classes aren't available
                TranscriptsDisabled = Exception
                NoTranscriptFound = Exception
                VideoUnavailable = Exception
            
            print(f"📹 [YOUTUBE] Extracting transcript for video ID: {video_id}")
            
            # Try to get transcript with better error handling
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            except VideoUnavailable:
                raise ValueError(f"YouTube video {video_id} is unavailable or private")
            except Exception as e:
                raise ValueError(f"Failed to access YouTube video: {str(e)}")
            
            # Prefer manually created transcripts, then auto-generated
            transcript = None
            transcript_language = None
            
            # Strategy 1: Try manually created English transcript
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
                transcript_language = 'en (manual)'
                print(f"✅ [YOUTUBE] Found manually created English transcript")
            except NoTranscriptFound:
                pass
            except Exception as e:
                print(f"⚠️  [YOUTUBE] Error finding manual transcript: {e}")
            
            # Strategy 2: Try auto-generated English transcript
            if not transcript:
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                    transcript_language = 'en (auto-generated)'
                    print(f"✅ [YOUTUBE] Found auto-generated English transcript")
                except NoTranscriptFound:
                    pass
                except Exception as e:
                    print(f"⚠️  [YOUTUBE] Error finding auto-generated transcript: {e}")
            
            # Strategy 3: Try any available transcript
            if not transcript:
                try:
                    available_transcripts = list(transcript_list)
                    if available_transcripts:
                        transcript = available_transcripts[0]
                        transcript_language = transcript.language_code
                        print(f"✅ [YOUTUBE] Using available transcript in {transcript_language}")
                    else:
                        raise ValueError("No transcripts available for this video")
                except Exception as e:
                    raise ValueError(f"No transcripts found for this video: {str(e)}")
            
            # Strategy 4: Try translating if we have a non-English transcript
            if transcript and transcript_language != 'en':
                try:
                    transcript = transcript.translate('en')
                    print(f"✅ [YOUTUBE] Translated transcript from {transcript_language} to English")
                except Exception as e:
                    print(f"⚠️  [YOUTUBE] Could not translate transcript: {e}")
            
            if not transcript:
                raise ValueError("No transcript available for this video. The video may not have captions enabled.")
            
            # Fetch and combine transcript
            transcript_data = transcript.fetch()
            text_parts = [entry['text'] for entry in transcript_data]
            full_text = " ".join(text_parts)
            
            if not full_text.strip():
                raise ValueError("Transcript is empty")
            
            print(f"✅ [YOUTUBE] Successfully extracted {len(full_text)} characters of transcript")
            return full_text
            
        except TranscriptsDisabled:
            raise ValueError(
                "Transcripts are disabled for this YouTube video. "
                "The video owner has not enabled captions/subtitles. "
                "Please try a different video that has captions enabled, or use a different content source."
            )
        except NoTranscriptFound:
            raise ValueError(
                "No transcript found for this YouTube video. "
                "The video may not have captions enabled. "
                "Please try a different video that has captions, or use a different content source."
            )
        except VideoUnavailable:
            raise ValueError(
                "This YouTube video is unavailable, private, or has been deleted. "
                "Please check the video URL and try again."
            )
        except ValueError as e:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for common error patterns
            if "subtitles are disabled" in error_msg or "transcripts are disabled" in error_msg:
                raise ValueError(
                    "Subtitles are disabled for this YouTube video. "
                    "The video owner has not enabled captions. "
                    "Please try a different video that has captions enabled, or use Text/URL/PDF as your content source instead."
                )
            elif "could not retrieve" in error_msg or "could not be retrieved" in error_msg:
                if "subtitles are disabled" in error_msg:
                    raise ValueError(
                        "Subtitles are disabled for this YouTube video. "
                        "Please try a video that has captions enabled, or use a different content source."
                    )
                else:
                    raise ValueError(
                        "Could not retrieve transcript. The video may be private, unavailable, or have restricted access. "
                        "Please try a different video or use Text/URL/PDF as your content source."
                    )
            elif "transcript" in error_msg:
                if "disabled" in error_msg or "not available" in error_msg:
                    raise ValueError(
                        "Transcripts are not available for this video. "
                        "Please try a video with captions enabled, or use a different content source."
                    )
                else:
                    raise ValueError(f"Transcript error: {str(e)}")
            elif "private" in error_msg or "unavailable" in error_msg:
                raise ValueError(
                    "This YouTube video is private or unavailable. "
                    "Please use a public video or try a different content source."
                )
            else:
                raise ValueError(
                    f"Failed to extract YouTube transcript: {str(e)}. "
                    "This may be because the video doesn't have captions enabled. "
                    "Please try a different video or use Text/URL/PDF as your content source."
                )
    
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
        
        # Validate and normalize URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL format: {url}")
        
        # Add https:// if no scheme provided
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)
        
        print(f"🌐 [URL] Extracting content from: {url}")
        
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "").lower()
            
            # Handle different content types
            if "text/html" in content_type:
                content = self._parse_html(response.text)
                if not content or len(content.strip()) < 100:
                    # Fallback: try to get all text if main content extraction failed
                    print(f"⚠️  [URL] Main content extraction returned minimal text, trying fallback...")
                    content = self._parse_html_fallback(response.text)
                return content
            elif "text/plain" in content_type:
                return response.text.strip()
            elif "application/json" in content_type:
                # Try to extract text from JSON
                import json
                try:
                    data = response.json()
                    # Try to find text fields
                    if isinstance(data, dict):
                        text_fields = [v for k, v in data.items() if isinstance(v, str) and len(v) > 50]
                        if text_fields:
                            return "\n\n".join(text_fields)
                    return str(data)
                except:
                    return response.text.strip()
            else:
                # Try to parse as HTML anyway
                return self._parse_html(response.text)
                
        except httpx.TimeoutException:
            raise ValueError(f"Request timed out while fetching URL: {url}")
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 403:
                raise ValueError(f"Access forbidden (403). The website may be blocking automated requests.")
            elif status_code == 404:
                raise ValueError(f"Page not found (404). The URL may be incorrect or the page has been removed.")
            elif status_code == 429:
                raise ValueError(f"Rate limited (429). Please try again later.")
            else:
                raise ValueError(f"HTTP error {status_code} while fetching URL: {url}")
        except httpx.RequestError as e:
            raise ValueError(f"Network error while fetching URL: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to extract content from URL: {str(e)}")
    
    def _parse_html(self, html: str) -> str:
        """Parse HTML and extract main text content."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 
                            'iframe', 'noscript', 'svg', 'form', 'button', 'input']):
            element.decompose()
        
        # Remove common non-content elements
        for class_name in ['advertisement', 'ad', 'sidebar', 'menu', 'navigation', 
                          'social-share', 'share-buttons', 'comments', 'related-posts']:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
        
        # Try to find main content with multiple strategies
        main_content = None
        
        # Strategy 1: Look for semantic HTML5 elements and common content containers
        selectors = [
            'article',
            'main',
            '[role="main"]',
            '.article',
            '.content',
            '#content',
            '.post',
            '.entry',
            '.entry-content',
            '.post-content',
            '.article-content',
            '.story-body',
            '.article-body',
            '.post-body',
            '[itemprop="articleBody"]',
            '.article-text',
            '.text-content',
        ]
        
        for selector in selectors:
            main_content = soup.select_one(selector)
            if main_content:
                print(f"✅ [URL] Found content using selector: {selector}")
                break
        
        # Strategy 2: Look for divs with high text content
        if not main_content:
            divs = soup.find_all('div', class_=True)
            best_div = None
            max_text_length = 0
            
            for div in divs:
                text_length = len(div.get_text(strip=True))
                if text_length > max_text_length and text_length > 500:
                    max_text_length = text_length
                    best_div = div
            
            if best_div:
                main_content = best_div
                print(f"✅ [URL] Found content in div with {max_text_length} characters")
        
        # Strategy 3: Fallback to body
        if not main_content:
            main_content = soup.find('body') or soup
            print(f"⚠️  [URL] Using body as fallback")
        
        # Get text
        text = main_content.get_text(separator='\n', strip=True)
        
        # Clean up whitespace and remove excessive newlines
        lines = []
        prev_empty = False
        for line in text.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)
                prev_empty = False
            elif not prev_empty:
                lines.append('')  # Keep single blank lines for paragraph breaks
                prev_empty = True
        
        result = '\n'.join(lines)
        
        # Remove excessive blank lines (more than 2 consecutive)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
    
    def _parse_html_fallback(self, html: str) -> str:
        """Fallback HTML parsing method - extracts all text from body."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # Get all text from body
        body = soup.find('body') or soup
        text = body.get_text(separator='\n', strip=True)
        
        # Clean up
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
