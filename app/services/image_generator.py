"""
Image generation for podcast covers using SDXL (free, open-source).
"""
import os
from typing import Optional
import base64

from app.core.config import settings


class ImageGenerator:
    """
    Generate podcast cover images using Stable Diffusion XL.
    Uses HuggingFace free inference API or local diffusers.
    """
    
    def __init__(self, use_local: bool = False):
        """
        Initialize image generator.
        
        Args:
            use_local: Use local SDXL model (DISABLED - causes OOM crashes)
        """
        # FORCE API usage - local models cause server crashes
        if use_local:
            raise ValueError(
                "Local image generation is disabled to prevent server crashes. "
                "Please use HuggingFace API by setting use_local=False. "
                "Ensure HF_API_TOKEN is set in environment variables."
            )
        
        self.use_local = False  # Force API only
        self.model_id = settings.SDXL_MODEL
        self.hf_token = settings.HF_API_TOKEN
        
        if not self.hf_token:
            raise ValueError(
                "HF_API_TOKEN is required for image generation. "
                "Local models are disabled to prevent server crashes."
            )
        
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        
        self._local_pipe = None
        self._http_client = None
        print("✅ [IMAGE] Using HuggingFace API (no local model)")
    
    def _get_http_client(self):
        """Get HTTP client for API requests."""
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client(timeout=120.0)
        return self._http_client
    
    def _get_local_pipeline(self):
        """Load local SDXL pipeline - DISABLED to save memory."""
        # DISABLED: Local model loading causes OOM crashes
        raise RuntimeError(
            "Local image generation model is disabled to prevent server crashes. "
            "Please use HuggingFace API instead. "
            "Ensure HF_API_TOKEN is set and use_local=False."
        )
    
    def generate(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: str = None,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 30,
    ) -> str:
        """
        Generate a podcast cover image.
        
        Args:
            prompt: Image generation prompt
            output_path: Path to save the image
            negative_prompt: Things to avoid in the image
            width: Image width
            height: Image height
            num_inference_steps: Number of diffusion steps
            
        Returns:
            Path to generated image
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # FORCE API usage - local models disabled to prevent crashes
        if self.use_local:
            raise RuntimeError(
                "Local image generation is disabled to prevent server crashes. "
                "Please use HuggingFace API. Ensure HF_API_TOKEN is set."
            )
        
        return self._generate_api(prompt, output_path, negative_prompt)
    
    def _generate_api(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: str = None,
    ) -> str:
        """Generate using HuggingFace Inference API."""
        client = self._get_http_client()
        
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        
        payload = {
            "inputs": prompt,
        }
        
        if negative_prompt:
            payload["parameters"] = {"negative_prompt": negative_prompt}
        
        try:
            response = client.post(
                self.api_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            # Response is raw image bytes
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            return output_path
            
        except Exception as e:
            # HuggingFace Inference API for images may be unavailable
            # Return None instead of raising to allow graceful degradation
            print(f"Warning: Image generation failed (API may be unavailable): {e}")
            return None
    
    def _generate_local(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: str = None,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 30,
    ) -> str:
        """Generate using local SDXL model."""
        pipe = self._get_local_pipeline()
        
        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
        ).images[0]
        
        image.save(output_path)
        
        return output_path
    
    def generate_podcast_cover(
        self,
        title: str,
        description: str = None,
        style: str = "modern",
        output_path: str = None,
    ) -> str:
        """
        Generate a podcast cover based on title and description.
        
        Args:
            title: Podcast episode title
            description: Episode description for context
            style: Visual style (modern, vintage, minimal, vibrant)
            output_path: Output path for the image
            
        Returns:
            Path to generated cover image
        """
        # Build prompt from title and description
        prompt = self._build_cover_prompt(title, description, style)
        
        # Default output path if not provided
        if not output_path:
            import tempfile
            output_path = os.path.join(tempfile.gettempdir(), "podcast_cover.png")
        
        # Default negative prompt for podcast covers
        negative_prompt = (
            "text, watermark, logo, words, letters, "
            "blurry, low quality, distorted, ugly, "
            "nsfw, violent, disturbing"
        )
        
        return self.generate(
            prompt=prompt,
            output_path=output_path,
            negative_prompt=negative_prompt,
        )
    
    def _build_cover_prompt(
        self,
        title: str,
        description: str = None,
        style: str = "modern",
    ) -> str:
        """Build image prompt from title and description."""
        
        style_prompts = {
            "modern": "modern digital art, clean design, professional",
            "vintage": "vintage retro style, warm colors, nostalgic",
            "minimal": "minimalist design, simple shapes, clean lines",
            "vibrant": "vibrant colors, dynamic, energetic, bold",
            "tech": "futuristic technology, digital, cyberpunk elements",
            "nature": "natural elements, organic, earthy tones",
        }
        
        style_desc = style_prompts.get(style, style_prompts["modern"])
        
        # Extract key themes from title
        prompt = f"Podcast cover art, {style_desc}, abstract representation of '{title}'"
        
        if description:
            # Add first few words of description for context
            desc_words = description.split()[:10]
            prompt += f", themed around {' '.join(desc_words)}"
        
        # Add quality modifiers
        prompt += ", high quality, professional podcast artwork, square format, visually striking"
        
        return prompt
    
    def close(self):
        """Clean up resources."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
