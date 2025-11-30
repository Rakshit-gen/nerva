"""
Podcast script generator with multi-persona support.
"""
from typing import List, Dict, Any, Optional
import re

from app.services.llm import LLMService
from app.services.vector_store import VectorStore


class ScriptGenerator:
    """
    Generate podcast scripts from source content using RAG.
    Supports multi-persona dialogue format.
    """
    
    def __init__(
        self,
        llm_service: LLMService = None,
        vector_store: VectorStore = None,
    ):
        """
        Initialize script generator.
        
        Args:
            llm_service: LLM service for generation
            vector_store: Vector store for RAG retrieval
        """
        # Auto-detect LLM: use Ollama if available and configured, otherwise use HuggingFace
        from app.core.config import settings
        use_ollama = settings.USE_OLLAMA
        if use_ollama:
            # Try to connect to Ollama, fallback to HF if unavailable
            try:
                import httpx
                client = httpx.Client(timeout=2.0)
                response = client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    use_ollama = True
                else:
                    use_ollama = False
            except:
                use_ollama = False
        
        self.llm = llm_service or LLMService(use_ollama=use_ollama)
        self.vector_store = vector_store or VectorStore()
    
    def generate(
        self,
        title: str,
        content: str,
        personas: List[Dict[str, Any]],
        episode_id: str = None,
        target_duration_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        Generate a podcast script.
        
        MEMORY CAP: Maximum duration is 10 minutes to prevent OOM crashes.
        
        Args:
            title: Episode title
            content: Source content (full text)
            personas: List of persona configurations
            episode_id: Episode ID for RAG retrieval
            target_duration_minutes: Target duration in minutes
            
        Returns:
            Dictionary with script and metadata
        """
        # Hard cap on duration to prevent memory issues
        MAX_DURATION_MINUTES = 10
        if target_duration_minutes > MAX_DURATION_MINUTES:
            print(f"⚠️  [SCRIPT] Duration capped at {MAX_DURATION_MINUTES} minutes (requested {target_duration_minutes})")
            target_duration_minutes = MAX_DURATION_MINUTES
        # Get relevant chunks if episode has embeddings
        context_chunks = []
        if episode_id:
            try:
                chunks = self.vector_store.get_episode_chunks(episode_id, limit=20)
                context_chunks = [c["text"] for c in chunks]
            except Exception:
                pass
        
        # If no chunks, use raw content (truncated)
        if not context_chunks:
            # Split content into rough chunks for context
            words = content.split()
            chunk_size = 500
            context_chunks = [
                " ".join(words[i:i + chunk_size])
                for i in range(0, min(len(words), 5000), chunk_size)
            ]
        
        # Build context
        context = "\n\n---\n\n".join(context_chunks[:15])  # Limit context size
        
        # Build persona descriptions
        persona_desc = self._format_personas(personas)
        
        # Calculate target word count (avg speaking rate ~150 wpm)
        target_words = target_duration_minutes * 150
        
        # Generate script
        script = self._generate_script(
            title=title,
            context=context,
            persona_desc=persona_desc,
            personas=personas,
            target_words=target_words,
        )
        
        # Parse and validate script
        parsed_script = self._parse_script(script, personas)
        
        return {
            "script": script,
            "parsed_segments": parsed_script,
            "word_count": len(script.split()),
            "estimated_duration_minutes": len(script.split()) / 150,
            "personas": personas,
        }
    
    def _format_personas(self, personas: List[Dict[str, Any]]) -> str:
        """Format personas for the prompt."""
        lines = []
        for p in personas:
            name = p.get("name", "Speaker")
            role = p.get("role", "host")
            personality = p.get("personality", "friendly and engaging")
            lines.append(f"- {name} ({role}): {personality}")
        return "\n".join(lines)
    
    def _generate_script(
        self,
        title: str,
        context: str,
        persona_desc: str,
        personas: List[Dict[str, Any]],
        target_words: int,
    ) -> str:
        """Generate the podcast script using LLM."""
        
        persona_names = [p.get("name", f"Speaker{i}") for i, p in enumerate(personas)]
        
        system_prompt = """You are an expert podcast script writer. Your job is to create engaging, natural-sounding podcast dialogue based on provided content.

Guidelines:
- Write natural, conversational dialogue
- Include smooth transitions between topics
- Add personality through natural speech patterns
- Include occasional interruptions, agreements, and reactions
- Avoid being dry or overly formal
- Make complex topics accessible
- Include brief introductions and conclusions

Format each line as:
SPEAKER_NAME: Dialogue text here.

Always start with an introduction and end with a conclusion/outro."""

        user_prompt = f"""Create a podcast script for an episode titled "{title}".

SPEAKERS:
{persona_desc}

SOURCE CONTENT:
{context}

TARGET LENGTH: Approximately {target_words} words

Write an engaging podcast script where the speakers discuss the key points from the source content. Make it conversational and interesting.

Remember to format as:
{persona_names[0]}: [dialogue]
{persona_names[1] if len(persona_names) > 1 else persona_names[0]}: [dialogue]
etc.

Begin the script now:"""

        # Reduce max_tokens to speed up generation and reduce memory usage
        # 3000 tokens ≈ 2250 words, which is enough for a 10-minute podcast
        # This also reduces API call time and memory footprint
        max_tokens = min(3000, target_words + 500)  # Cap at 3000, but allow some flexibility
        
        print(f"📝 [SCRIPT] Generating script with max_tokens={max_tokens} (target_words={target_words})")
        
        try:
            script = self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.8,
            )
        except Exception as e:
            error_msg = str(e)
            print(f"❌ [SCRIPT] LLM generation failed: {error_msg}")
            # Provide more helpful error message
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                raise RuntimeError(
                    f"Script generation timed out. The HuggingFace API took too long to respond. "
                    f"This might be due to high API load. Please try again in a few minutes. "
                    f"Original error: {error_msg}"
                )
            elif "rate limit" in error_msg.lower() or "429" in error_msg:
                raise RuntimeError(
                    f"Script generation rate limited. HuggingFace API is currently busy. "
                    f"Please try again in a few minutes. Original error: {error_msg}"
                )
            elif "401" in error_msg or "unauthorized" in error_msg.lower() or "token" in error_msg.lower():
                raise RuntimeError(
                    f"Script generation authentication failed. Please check your HuggingFace API token. "
                    f"Original error: {error_msg}"
                )
            else:
                raise RuntimeError(f"Script generation failed: {error_msg}")
        
        return script.strip()
    
    def _parse_script(
        self,
        script: str,
        personas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Parse script into segments by speaker.
        
        Args:
            script: Raw script text
            personas: Persona configurations
            
        Returns:
            List of segments with speaker and text
        """
        persona_names = {p.get("name", "").upper(): p for p in personas}
        
        segments = []
        current_speaker = None
        current_text = []
        
        for line in script.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Check if line starts with a speaker name
            match = re.match(r'^([A-Z][A-Za-z]+):\s*(.*)$', line)
            
            if match:
                # Save previous segment
                if current_speaker and current_text:
                    segments.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_text),
                        "persona": persona_names.get(current_speaker.upper(), {}),
                    })
                
                current_speaker = match.group(1)
                current_text = [match.group(2)] if match.group(2) else []
            else:
                # Continue current speaker's text
                if current_speaker:
                    current_text.append(line)
        
        # Don't forget last segment
        if current_speaker and current_text:
            segments.append({
                "speaker": current_speaker,
                "text": " ".join(current_text),
                "persona": persona_names.get(current_speaker.upper(), {}),
            })
        
        return segments
    
    def enhance_segment(
        self,
        segment: Dict[str, Any],
        style: str = "conversational",
    ) -> str:
        """
        Enhance a single segment with better phrasing.
        
        Args:
            segment: Segment dictionary
            style: Speech style
            
        Returns:
            Enhanced text
        """
        speaker = segment.get("speaker", "Speaker")
        text = segment.get("text", "")
        personality = segment.get("persona", {}).get("personality", "friendly")
        
        prompt = f"""Rewrite this podcast dialogue line to sound more {style} and match the speaker's personality ({personality}):

Original: {text}

Keep the same meaning but make it more natural and engaging. Only output the rewritten line, nothing else."""

        enhanced = self.llm.generate(
            prompt=prompt,
            max_tokens=256,
            temperature=0.7,
        )
        
        return enhanced.strip()
