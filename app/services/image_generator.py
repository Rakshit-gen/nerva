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
            use_local: Use local SDXL model (requires GPU)
        """
        self.use_local = use_local
        self.model_id = settings.SDXL_MODEL
        self.hf_token = settings.HF_API_TOKEN
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        
        self._local_pipe = None
        self._http_client = None
    
    def _get_http_client(self):
        """Get HTTP client for API requests."""
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client(timeout=120.0)
        return self._http_client
    
    def _get_local_pipeline(self):
        """Load local SDXL pipeline."""
        if self._local_pipe is None:
            try:
                from diffusers import StableDiffusionXLPipeline
                import torch
                
                device = "cuda" if torch.cuda.is_available() else "cpu"
                
                self._local_pipe = StableDiffusionXLPipeline.from_pretrained(
                    self.model_id,
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                    use_safetensors=True,
                )
                self._local_pipe.to(device)
                
            except ImportError:
                raise RuntimeError("diffusers not installed")
        
        return self._local_pipe
    
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
        
        if self.use_local:
            return self._generate_local(
                prompt, output_path, negative_prompt,
                width, height, num_inference_steps
            )
        else:
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
