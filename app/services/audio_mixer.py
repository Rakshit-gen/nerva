"""
Audio mixing service for combining TTS segments into final podcast.
"""
import os
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path


class AudioMixer:
    """
    Mix multiple audio segments into a single podcast file.
    Uses pydub for audio processing (free, open-source).
    """
    
    def __init__(self):
        """Initialize audio mixer."""
        self._pydub_available = None
    
    def _check_pydub(self):
        """Check if pydub is available."""
        if self._pydub_available is None:
            try:
                from pydub import AudioSegment
                self._pydub_available = True
            except ImportError:
                self._pydub_available = False
        return self._pydub_available
    
    def mix(
        self,
        segments: List[Dict[str, Any]],
        output_path: str,
        intro_audio: str = None,
        outro_audio: str = None,
        background_music: str = None,
        music_volume: float = 0.1,
        pause_between_segments: int = 500,  # milliseconds
    ) -> Dict[str, Any]:
        """
        Mix audio segments into final podcast.
        
        Args:
            segments: List of segments with audio_path
            output_path: Output MP3 file path
            intro_audio: Optional intro audio file
            outro_audio: Optional outro audio file
            background_music: Optional background music file
            music_volume: Volume for background music (0.0-1.0)
            pause_between_segments: Pause duration in ms
            
        Returns:
            Dictionary with output info
        """
        if not self._check_pydub():
            raise RuntimeError("pydub not installed. Run: pip install pydub")
        
        from pydub import AudioSegment
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Start with empty audio or intro
        if intro_audio and os.path.exists(intro_audio):
            combined = AudioSegment.from_file(intro_audio)
        else:
            combined = AudioSegment.silent(duration=1000)  # 1 second silence
        
        # Create pause segment
        pause = AudioSegment.silent(duration=pause_between_segments)
        
        # Add each segment - process one at a time to minimize memory
        segments_added = 0
        
        for i, segment in enumerate(segments):
            audio_path = segment.get("audio_path")
            if not audio_path or not os.path.exists(audio_path):
                continue
            
            try:
                # Load segment, add to combined, then immediately delete
                segment_audio = AudioSegment.from_file(audio_path)
                combined = combined + pause + segment_audio
                segments_added += 1
                
                # Immediately delete segment from memory after adding
                del segment_audio
                
                # Force garbage collection every 3 segments
                if segments_added % 3 == 0:
                    import gc
                    gc.collect()
                    
            except Exception as e:
                print(f"Warning: Could not add segment: {e}")
        
        # Add outro
        if outro_audio and os.path.exists(outro_audio):
            combined = combined + pause + AudioSegment.from_file(outro_audio)
        else:
            # Add fade out at the end
            combined = combined + AudioSegment.silent(duration=500)
            combined = combined.fade_out(500)
        
        # Add background music if provided
        if background_music and os.path.exists(background_music):
            try:
                music = AudioSegment.from_file(background_music)
                # Adjust music volume
                music = music - (20 * (1 - music_volume))  # Reduce by dB
                # Loop music to match duration
                while len(music) < len(combined):
                    music = music + music
                music = music[:len(combined)]
                # Mix
                combined = combined.overlay(music)
            except Exception as e:
                print(f"Warning: Could not add background music: {e}")
        
        # Export as MP3
        duration_ms = len(combined)
        duration_seconds = duration_ms / 1000
        
        combined.export(
            output_path,
            format="mp3",
            bitrate="192k",
            tags={
                "title": "AI Generated Podcast",
                "artist": "AI Podcast Generator",
            },
        )
        
        # Clear combined audio from memory after export
        del combined
        import gc
        gc.collect()
        
        return {
            "output_path": output_path,
            "duration_ms": duration_ms,
            "duration_seconds": duration_seconds,
            "segments_count": segments_added,
            "file_size_bytes": os.path.getsize(output_path),
        }
    
    def normalize_audio(
        self,
        input_path: str,
        output_path: str = None,
        target_dbfs: float = -20.0,
    ) -> str:
        """
        Normalize audio to target dBFS.
        
        Args:
            input_path: Input audio file
            output_path: Output path (same as input if not provided)
            target_dbfs: Target loudness in dBFS
            
        Returns:
            Path to normalized audio
        """
        if not self._check_pydub():
            return input_path
        
        from pydub import AudioSegment
        
        output_path = output_path or input_path
        
        audio = AudioSegment.from_file(input_path)
        
        # Calculate change needed
        change_in_dbfs = target_dbfs - audio.dBFS
        
        # Apply normalization
        normalized = audio.apply_gain(change_in_dbfs)
        
        # Export
        normalized.export(output_path, format=Path(output_path).suffix[1:])
        
        return output_path
    
    def convert_to_mp3(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k",
    ) -> str:
        """
        Convert audio file to MP3.
        
        Args:
            input_path: Input audio file
            output_path: Output MP3 path
            bitrate: MP3 bitrate
            
        Returns:
            Path to MP3 file
        """
        if not self._check_pydub():
            # Fallback to ffmpeg directly
            return self._convert_ffmpeg(input_path, output_path, bitrate)
        
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="mp3", bitrate=bitrate)
        
        return output_path
    
    def _convert_ffmpeg(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k",
    ) -> str:
        """Convert using ffmpeg directly."""
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            output_path,
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg conversion failed: {e.stderr.decode()}")
    
    def get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """Get information about an audio file."""
        if not os.path.exists(audio_path):
            return {"error": "File not found"}
        
        if not self._check_pydub():
            return {
                "path": audio_path,
                "size_bytes": os.path.getsize(audio_path),
            }
        
        from pydub import AudioSegment
        
        try:
            audio = AudioSegment.from_file(audio_path)
            return {
                "path": audio_path,
                "duration_ms": len(audio),
                "duration_seconds": len(audio) / 1000,
                "channels": audio.channels,
                "sample_rate": audio.frame_rate,
                "sample_width": audio.sample_width,
                "size_bytes": os.path.getsize(audio_path),
            }
        except Exception as e:
            return {
                "path": audio_path,
                "error": str(e),
            }
