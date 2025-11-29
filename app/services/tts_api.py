"""
API-based Text-to-Speech service using Google Cloud TTS and ElevenLabs.
No local models required - saves ~2-4GB memory.
"""
import os
import httpx
import base64
from typing import Optional
from pathlib import Path

from app.core.config import settings


class GoogleTTSService:
    """Google Cloud Text-to-Speech API service."""
    
    def __init__(self):
        """Initialize Google TTS service."""
        self.api_key = settings.GOOGLE_TTS_API_KEY
        self.project_id = settings.GOOGLE_TTS_PROJECT_ID
        
        if not self.api_key:
            raise ValueError("GOOGLE_TTS_API_KEY not set")
        
        self.base_url = "https://texttospeech.googleapis.com/v1"
        self._client = None
    
    def _get_client(self):
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=60.0)
        return self._client
    
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str = "default_male",
        language: str = "en-US",
    ) -> str:
        """
        Synthesize speech using Google Cloud TTS.
        
        Args:
            text: Text to synthesize
            output_path: Path for output audio file
            voice_id: Voice identifier (maps to Google voice names)
            language: Language code (default: en-US)
            
        Returns:
            Path to generated audio file
        """
        # Map voice_id to Google voice names
        voice_map = {
            "default_male": {
                "name": "en-US-Neural2-D",
                "ssml_gender": "MALE",
            },
            "default_female": {
                "name": "en-US-Neural2-F",
                "ssml_gender": "FEMALE",
            },
        }
        
        voice_config = voice_map.get(voice_id, voice_map["default_male"])
        
        # Prepare request
        # Try API key method first, fallback to OAuth if needed
        url = f"{self.base_url}/text:synthesize"
        
        # Use API key in query parameter
        params = {"key": self.api_key}
        
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": language,
                "name": voice_config["name"],
                "ssmlGender": voice_config["ssml_gender"],
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "sampleRateHertz": 24000,
            },
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        client = self._get_client()
        response = client.post(url, json=payload, params=params, headers=headers)
        
        # If API key fails, try with Authorization header (OAuth2)
        if response.status_code == 401:
            # API key might not work, need OAuth2 token
            # For now, raise error - user should use service account
            raise ValueError(
                "Google TTS API requires OAuth2 authentication. "
                "Please use a service account or set GOOGLE_APPLICATION_CREDENTIALS. "
                "Alternatively, use ElevenLabs TTS API instead."
            )
        
        response.raise_for_status()
        
        result = response.json()
        audio_content = result["audioContent"]
        
        # Decode base64 audio
        audio_data = base64.b64decode(audio_content)
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write to file
        with open(output_path, "wb") as f:
            f.write(audio_data)
        
        return output_path
    
    def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


class ElevenLabsTTSService:
    """ElevenLabs TTS API service."""
    
    def __init__(self):
        """Initialize ElevenLabs TTS service."""
        self.api_key = settings.ELEVENLABS_API_KEY
        
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not set")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self._client = None
    
    def _get_client(self):
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=60.0)
        return self._client
    
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str = "default_male",
        language: str = "en",
    ) -> str:
        """
        Synthesize speech using ElevenLabs TTS.
        
        Args:
            text: Text to synthesize
            output_path: Path for output audio file
            voice_id: Voice identifier (maps to ElevenLabs voice IDs)
            language: Language code (default: en)
            
        Returns:
            Path to generated audio file
        """
        # Map voice_id to ElevenLabs voice IDs
        # Default voices (free tier compatible)
        voice_map = {
            "default_male": "pNInz6obpgDQGcFmaJgB",  # Adam
            "default_female": "EXAVITQu4vr4xnSDxMaL",  # Bella
        }
        
        voice_id_elevenlabs = voice_map.get(voice_id, voice_map["default_male"])
        
        # Prepare request
        url = f"{self.base_url}/text-to-speech/{voice_id_elevenlabs}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
            },
        }
        
        client = self._get_client()
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write audio to file
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        return output_path
    
    def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


class APITTSService:
    """
    Unified API-based TTS service.
    Automatically selects Google TTS or ElevenLabs based on configuration.
    Falls back to local TTS if APIs are unavailable.
    """
    
    def __init__(self):
        """Initialize API TTS service."""
        self.provider = settings.TTS_PROVIDER.lower()
        self._service = None
        self._fallback_service = None
    
    def _get_service(self):
        """Get TTS service instance."""
        if self._service is None:
            if self.provider == "google":
                # Strict: If Google TTS is configured, require API key
                if not settings.GOOGLE_TTS_API_KEY:
                    raise ValueError(
                        "TTS_PROVIDER is set to 'google' but GOOGLE_TTS_API_KEY is not set. "
                        "Please set GOOGLE_TTS_API_KEY or change TTS_PROVIDER to 'local'."
                    )
                try:
                    self._service = GoogleTTSService()
                    print("✅ [TTS] Using Google Cloud TTS API (no local model download)")
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to initialize Google TTS API: {e}. "
                        "Check your GOOGLE_TTS_API_KEY and API configuration."
                    )
            elif self.provider == "elevenlabs":
                # Strict: If ElevenLabs is configured, require API key
                if not settings.ELEVENLABS_API_KEY:
                    raise ValueError(
                        "TTS_PROVIDER is set to 'elevenlabs' but ELEVENLABS_API_KEY is not set. "
                        "Please set ELEVENLABS_API_KEY or change TTS_PROVIDER to 'local'."
                    )
                try:
                    self._service = ElevenLabsTTSService()
                    print("✅ [TTS] Using ElevenLabs TTS API (no local model download)")
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to initialize ElevenLabs TTS API: {e}. "
                        "Check your ELEVENLABS_API_KEY and API configuration."
                    )
            else:
                # Only use local TTS if explicitly set to "local"
                print("⚠️  [TTS] Using local TTS (will download model on first use)")
                from app.services.tts import TTSService
                self._service = TTSService()
        
        return self._service
    
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str = "default_male",
        language: str = None,
        speaker_wav: str = None,
    ) -> str:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            output_path: Path for output audio file
            voice_id: Voice identifier
            language: Language code (optional)
            speaker_wav: Optional reference audio (not used for API)
            
        Returns:
            Path to generated audio file
        """
        service = self._get_service()
        
        # Convert output path to MP3 for API services
        if self.provider in ["google", "elevenlabs"]:
            # APIs return MP3, so change extension
            if not output_path.endswith(".mp3"):
                output_path = str(Path(output_path).with_suffix(".mp3"))
        
        try:
            return service.synthesize(
                text=text,
                output_path=output_path,
                voice_id=voice_id,
                language=language or "en-US",
            )
        except Exception as e:
            # If API is configured, don't fall back to local (saves memory)
            # Only fall back if explicitly set to "local"
            if self.provider in ["google", "elevenlabs"]:
                raise RuntimeError(
                    f"TTS API ({self.provider}) failed: {e}. "
                    "Check your API key and network connection. "
                    "Local TTS fallback disabled to save memory."
                ) from e
            # Only allow fallback if provider is "local" or not set
            raise
    
    def synthesize_segments(
        self,
        segments: list,
        output_dir: str,
        voice_mapping: dict = None,
    ) -> list:
        """
        Synthesize multiple segments.
        
        Args:
            segments: List of {"speaker": "...", "text": "..."}
            output_dir: Directory for output files
            voice_mapping: Map speaker names to voice IDs
            
        Returns:
            Segments with audio_path added
        """
        os.makedirs(output_dir, exist_ok=True)
        voice_mapping = voice_mapping or {}
        results = []
        
        for i, segment in enumerate(segments):
            speaker = segment.get("speaker", "Speaker")
            text = segment.get("text", "")
            
            if not text.strip():
                continue
            
            voice_id = voice_mapping.get(speaker, "default_male")
            output_path = os.path.join(output_dir, f"segment_{i:04d}.mp3")
            
            try:
                self.synthesize(
                    text=text,
                    output_path=output_path,
                    voice_id=voice_id,
                )
                results.append({
                    **segment,
                    "index": i,
                    "audio_path": output_path,
                })
            except Exception as e:
                print(f"Warning: Failed to synthesize segment {i}: {e}")
                results.append({
                    **segment,
                    "index": i,
                    "audio_path": None,
                    "error": str(e),
                })
        
        return results
    
    def unload_model(self):
        """No-op for API service (no model to unload)."""
        if hasattr(self._service, 'close'):
            self._service.close()
        if self._fallback_service:
            if hasattr(self._fallback_service, 'unload_model'):
                self._fallback_service.unload_model()
    
    def close(self):
        """Close service."""
        self.unload_model()

