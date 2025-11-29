"""
Text-to-Speech service using Coqui XTTS (free, open-source).
"""
import os
import wave
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.core.config import settings


class TTSService:
    """
    Text-to-Speech using Coqui TTS (XTTS model).
    Completely free and open-source.
    """
    
    def __init__(self):
        """Initialize TTS service."""
        self._tts = None
        self._device = None
        
        # Voice configurations for different speakers
        # For vits model, use speaker IDs (p225, p226, etc.)
        # For XTTS, use speaker_wav files
        self.voice_configs = {
            "default_male": {
                "language": "en",
                "speaker": "p225",  # vits model speaker ID
                "speaker_wav": None,
            },
            "default_female": {
                "language": "en",
                "speaker": "p226",  # vits model speaker ID
                "speaker_wav": None,
            },
        }
    
    def _get_tts(self):
        """Lazy load TTS model."""
        if self._tts is None:
            try:
                from TTS.api import TTS
                import torch
                
                # Check for GPU
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                
                # Load TTS model
                self._tts = TTS(settings.TTS_MODEL).to(self._device)
                
            except ImportError:
                raise RuntimeError(
                    "Coqui TTS not installed. Run: pip install TTS"
                )
        return self._tts
    
    def unload_model(self):
        """Unload TTS model to free memory."""
        if self._tts is not None:
            try:
                # Move model to CPU and delete
                if hasattr(self._tts, 'to'):
                    self._tts = self._tts.to('cpu')
                del self._tts
                self._tts = None
                
                # Force garbage collection
                import gc
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            except Exception as e:
                print(f"Warning: Error unloading TTS model: {e}")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.unload_model()
    
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str = "default_male",
        language: str = None,  # None by default - will be set based on model
        speaker_wav: str = None,
    ) -> str:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            output_path: Path for output WAV file
            voice_id: Voice identifier
            language: Language code
            speaker_wav: Optional reference audio for voice cloning
            
        Returns:
            Path to generated audio file
        """
        import torch
        # Use no_grad to save memory during inference
        with torch.no_grad():
            tts = self._get_tts()
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Get voice config
        voice_config = self.voice_configs.get(voice_id, {})
        
        # Use provided speaker_wav or from config
        ref_audio = speaker_wav or voice_config.get("speaker_wav")
        
        # For vits model, don't use language from config (it's English-only)
        model_name = settings.TTS_MODEL.lower()
        if "vits" in model_name:
            language = None  # Force None for vits - it doesn't support language parameter
        
        try:
            # Check if model uses speaker parameter (vits) or speaker_wav (xtts)
            
            if "vits" in model_name:
                # vits model uses speaker parameter, NO language parameter (English-only)
                speaker = voice_config.get("speaker", "p225")
                # Explicitly do NOT pass language - vits will error if language is provided
                tts.tts_to_file(
                    text=text,
                    file_path=output_path,
                    speaker=speaker,
                )
            elif "xtts" in model_name:
                # XTTS requires speaker_wav and supports language
                if not ref_audio:
                    raise RuntimeError("XTTS model requires speaker_wav parameter")
                tts.tts_to_file(
                    text=text,
                    file_path=output_path,
                    speaker_wav=ref_audio,
                    language=language or "en",
                )
            else:
                # Other models (tacotron2, etc.) - try with language if provided, fallback without
                if language:
                    try:
                        tts.tts_to_file(
                            text=text,
                            file_path=output_path,
                            language=language,
                        )
                    except (TypeError, ValueError) as e:
                        # If language parameter not supported, try without it
                        if "language" in str(e).lower() or "multi-lingual" in str(e).lower():
                            tts.tts_to_file(
                                text=text,
                                file_path=output_path,
                            )
                        else:
                            raise
                else:
                    # No language provided, call without it
                    tts.tts_to_file(
                        text=text,
                        file_path=output_path,
                    )
            
            # Verify file was created
            if not os.path.exists(output_path):
                raise RuntimeError(f"TTS output file was not created: {output_path}")
            
            return output_path
            
        except Exception as e:
            # Provide more detailed error information
            error_msg = str(e)
            if "Model file not found" in error_msg:
                raise RuntimeError(
                    f"TTS model files not found. The model may not be fully downloaded. "
                    f"Try running TTS manually to download: python -c 'from TTS.api import TTS; TTS(\"{settings.TTS_MODEL}\")'"
                )
            raise RuntimeError(f"TTS synthesis failed: {e}")
    
    def synthesize_segments(
        self,
        segments: List[Dict[str, Any]],
        output_dir: str,
        voice_mapping: Dict[str, str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Synthesize multiple segments with different speakers.
        
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
        
        # Process segments in smaller batches to reduce memory usage
        batch_size = 5  # Reduced from 10 to save memory
        import gc
        import torch
        
        for batch_start in range(0, len(segments), batch_size):
            batch = segments[batch_start:batch_start + batch_size]
            
            for i, segment in enumerate(batch):
                actual_index = batch_start + i
                speaker = segment.get("speaker", "Speaker")
                text = segment.get("text", "")
                
                if not text.strip():
                    continue
                
                # Get voice ID for speaker
                voice_id = voice_mapping.get(speaker, "default_male")
                
                # Generate output path
                output_path = os.path.join(output_dir, f"segment_{actual_index:04d}.wav")
                
                try:
                    # For vits model, alternate between different speaker IDs for variety
                    # Map voice_id to actual speaker parameter
                    model_name = settings.TTS_MODEL.lower()
                    if "vits" in model_name:
                        # Use different speaker IDs based on voice_id
                        # p225, p226, p227, p228 are different voices in vctk
                        speaker_map = {
                            "default_male": "p225",
                            "default_female": "p226",
                        }
                        actual_speaker = speaker_map.get(voice_id, "p225")
                        # Update voice config with speaker
                        voice_config = self.voice_configs.get(voice_id, {})
                        voice_config = {**voice_config, "speaker": actual_speaker}
                        self.voice_configs[voice_id] = voice_config
                    
                    self.synthesize(
                        text=text,
                        output_path=output_path,
                        voice_id=voice_id,
                    )
                    
                    results.append({
                        **segment,
                        "index": actual_index,
                        "audio_path": output_path,
                    })
                    
                except Exception as e:
                    print(f"Warning: Failed to synthesize segment {actual_index}: {e}")
                    results.append({
                        **segment,
                        "index": actual_index,
                        "audio_path": None,
                        "error": str(e),
                    })
            
            # Force garbage collection and clear PyTorch cache after each batch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        return results
    
    def get_available_voices(self) -> List[str]:
        """Get list of available voice IDs."""
        return list(self.voice_configs.keys())
    
    def add_voice(
        self,
        voice_id: str,
        speaker_wav: str,
        language: str = "en",
    ):
        """
        Add a custom voice using reference audio.
        
        Args:
            voice_id: Unique identifier for the voice
            speaker_wav: Path to reference audio file
            language: Language code
        """
        if not os.path.exists(speaker_wav):
            raise ValueError(f"Speaker audio file not found: {speaker_wav}")
        
        self.voice_configs[voice_id] = {
            "speaker_wav": speaker_wav,
            "language": language,
        }


class SimpleTTSService:
    """
    Fallback TTS using pyttsx3 (simpler, works offline).
    Use this if XTTS is not available.
    """
    
    def __init__(self):
        """Initialize simple TTS."""
        self._engine = None
    
    def _get_engine(self):
        """Lazy load TTS engine."""
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
            except ImportError:
                raise RuntimeError("pyttsx3 not installed")
        return self._engine
    
    def synthesize(
        self,
        text: str,
        output_path: str,
        rate: int = 150,
    ) -> str:
        """Synthesize speech to file."""
        engine = self._get_engine()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        engine.setProperty('rate', rate)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        
        return output_path
