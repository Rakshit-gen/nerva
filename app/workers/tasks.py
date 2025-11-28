"""
RQ worker tasks for podcast generation pipeline.
"""
import os
from datetime import datetime
from typing import Dict, Any

from rq import get_current_job
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Episode, ContentChunk, GenerationJob, JobStatus


# Sync database connection for worker (RQ doesn't support async)
# Note: asyncpg uses ssl=require, but psycopg2 uses sslmode=require
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("ssl=require", "sslmode=require")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)


def update_job_progress(progress: int, message: str):
    """Update RQ job progress metadata."""
    job = get_current_job()
    if job:
        job.meta["progress"] = progress
        job.meta["message"] = message
        job.save_meta()


def update_episode_status(
    db_session,
    episode_id: str,
    status: JobStatus,
    progress: int,
    message: str,
    error: str = None,
):
    """Update episode status in database."""
    from sqlalchemy.exc import PendingRollbackError, InvalidRequestError
    
    try:
        episode = db_session.query(Episode).filter(Episode.id == episode_id).first()
        if episode:
            episode.status = status
            episode.progress = progress
            episode.status_message = message
            if error:
                episode.error_message = error
            if status == JobStatus.COMPLETED:
                episode.completed_at = datetime.utcnow()
            db_session.commit()
    except (PendingRollbackError, InvalidRequestError) as e:
        # Session is in invalid state - rollback and retry
        try:
            db_session.rollback()
            # Retry the update after rollback
            episode = db_session.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                episode.status = status
                episode.progress = progress
                episode.status_message = message
                if error:
                    episode.error_message = error
                if status == JobStatus.COMPLETED:
                    episode.completed_at = datetime.utcnow()
                db_session.commit()
        except Exception as retry_error:
            # If retry also fails, log and give up
            print(f"Warning: Failed to update episode status after rollback: {retry_error}")
    except Exception as e:
        # Other errors - rollback and log
        try:
            db_session.rollback()
        except Exception:
            pass
        # Log but don't raise - we don't want status updates to crash the job
        print(f"Warning: Failed to update episode status: {e}")


def process_episode_task(episode_id: str, generate_cover: bool = True) -> Dict[str, Any]:
    """
    Main task to process an episode through the full pipeline.
    
    Pipeline:
    1. Extract content from source
    2. Chunk and embed content
    3. Generate script
    4. Synthesize audio
    5. Mix final audio
    6. Generate cover (optional)
    
    Args:
        episode_id: Episode ID to process
        generate_cover: Whether to generate cover image
        
    Returns:
        Result dictionary with output URLs
    """
    db = SessionLocal()
    
    try:
        # Get episode
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if not episode:
            raise ValueError(f"Episode not found: {episode_id}")
        
        # Update status
        update_episode_status(
            db, episode_id, JobStatus.PROCESSING, 0,
            "Starting processing pipeline"
        )
        update_job_progress(0, "Starting processing pipeline")
        
        # Create output directory
        output_dir = os.path.join(settings.OUTPUT_DIR, episode_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: Extract content (10%)
        update_job_progress(5, "Extracting content from source")
        update_episode_status(db, episode_id, JobStatus.PROCESSING, 5, "Extracting content")
        
        content = extract_content_sync(episode)
        
        update_job_progress(10, "Content extracted")
        update_episode_status(db, episode_id, JobStatus.PROCESSING, 10, "Content extracted")
        
        # Step 2: Chunk and embed (30%)
        update_job_progress(15, "Chunking and embedding content")
        update_episode_status(db, episode_id, JobStatus.PROCESSING, 15, "Creating embeddings")
        
        chunk_content_sync(db, episode_id, content, episode.title)
        
        update_job_progress(30, "Embeddings created")
        update_episode_status(db, episode_id, JobStatus.PROCESSING, 30, "Embeddings stored")
        
        # Step 3: Generate script (50%)
        update_job_progress(35, "Generating podcast script")
        update_episode_status(db, episode_id, JobStatus.PROCESSING, 35, "Generating script")
        
        script_result = generate_script_sync(episode, content)
        
        # Update episode with script
        episode.script = script_result["script"]
        episode.word_count = script_result["word_count"]
        db.commit()
        
        update_job_progress(50, "Script generated")
        update_episode_status(db, episode_id, JobStatus.PROCESSING, 50, "Script ready")
        
        # Step 4: Synthesize audio (80%)
        # Audio synthesis using TTS (Coqui XTTS) and pydub for mixing
        audio_available = False
        try:
            update_job_progress(55, "Synthesizing speech")
            update_episode_status(db, episode_id, JobStatus.PROCESSING, 55, "Generating audio")
            
            audio_segments = synthesize_audio_sync(
                script_result["parsed_segments"],
                output_dir,
                episode.personas,
            )
            
            update_job_progress(75, "Speech synthesis complete")
            
            # Step 5: Mix audio (90%)
            update_job_progress(80, "Mixing final audio")
            update_episode_status(db, episode_id, JobStatus.PROCESSING, 80, "Mixing audio")
            
            audio_result = mix_audio_sync(audio_segments, output_dir)
            
            # Update episode with audio info
            episode.audio_url = f"/api/v1/export/{episode_id}/audio"
            episode.duration_seconds = audio_result["duration_seconds"]
            audio_available = True
            
            update_job_progress(90, "Audio mixing complete")
        except Exception as audio_error:
            print(f"Warning: Audio generation failed: {audio_error}")
            print("Continuing without audio - script is still available")
            update_job_progress(90, "Script ready (audio unavailable)")
            update_episode_status(db, episode_id, JobStatus.PROCESSING, 90, "Script ready (audio unavailable)")
        
        # Always save the transcript
        episode.transcript = script_result["script"]
        db.commit()
        
        # Step 6: Generate cover (95%) - Optional, don't fail if it errors
        if generate_cover:
            try:
                update_job_progress(92, "Generating cover image")
                update_episode_status(db, episode_id, JobStatus.PROCESSING, 92, "Creating cover")
                
                cover_path = generate_cover_sync(episode, output_dir)
                
                episode.cover_url = f"/api/v1/export/{episode_id}/cover"
                db.commit()
            except Exception as e:
                # Cover generation failed, but don't fail the whole job
                print(f"Warning: Cover generation failed: {e}")
                update_job_progress(95, "Cover generation skipped")
                # Continue without cover
        
        # Complete
        update_job_progress(100, "Episode complete")
        update_episode_status(
            db, episode_id, JobStatus.COMPLETED, 100,
            "Episode generated successfully"
        )
        
        return {
            "episode_id": episode_id,
            "audio_url": episode.audio_url,
            "cover_url": episode.cover_url,
            "duration_seconds": episode.duration_seconds,
            "word_count": episode.word_count,
        }
        
    except Exception as e:
        # Handle failure - rollback any pending transaction
        try:
            db.rollback()
        except Exception:
            pass
        
        error_msg = str(e)
        print(f"Error processing episode {episode_id}: {error_msg}")
        
        # Try to update status, but use a fresh session if current one is invalid
        try:
            update_episode_status(
                db, episode_id, JobStatus.FAILED, 0,
                "Processing failed", error_msg
            )
        except Exception as status_error:
            # If update fails, try with a fresh session
            print(f"Failed to update status with current session: {status_error}")
            try:
                fresh_db = SessionLocal()
                try:
                    update_episode_status(
                        fresh_db, episode_id, JobStatus.FAILED, 0,
                        "Processing failed", error_msg
                    )
                finally:
                    fresh_db.close()
            except Exception:
                print(f"Failed to update status even with fresh session")
        
        raise
        
    finally:
        try:
            db.close()
        except Exception:
            pass


def extract_content_sync(episode: Episode) -> str:
    """Extract content from episode source (sync version)."""
    import asyncio
    from app.services.content_extractor import ContentExtractor
    
    extractor = ContentExtractor()
    
    # Run async extractor in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        content = loop.run_until_complete(
            extractor.extract(
                source_type=episode.source_type.value,
                source_url=episode.source_url,
                source_content=episode.source_content,
            )
        )
        return content
    finally:
        loop.run_until_complete(extractor.close())
        loop.close()


def chunk_content_sync(
    db,
    episode_id: str,
    content: str,
    title: str,
):
    """Chunk and embed content (sync version)."""
    from app.services.chunker import TextChunker
    from app.services.embeddings import EmbeddingService
    from app.services.vector_store import VectorStore
    
    chunker = TextChunker(chunk_size=512, chunk_overlap=50)
    embedding_service = EmbeddingService(use_local=True)
    vector_store = VectorStore(embedding_service=embedding_service)
    
    # Chunk content
    chunks = chunker.chunk_with_context(
        text=content,
        title=title,
        source=episode_id,
    )
    
    # Prepare for embedding
    texts = [c.content for c in chunks]
    metadatas = [
        {
            "episode_id": episode_id,
            "chunk_index": c.index,
            "title": title,
        }
        for c in chunks
    ]
    
    # Store in vector database (optional - continue if it fails)
    try:
        ids = vector_store.add(texts, metadatas)
    except Exception as vector_error:
        print(f"Warning: Vector store operation failed: {vector_error}")
        print("Continuing without vector storage - chunks will still be saved to database")
        # Generate placeholder IDs if vector store fails
        ids = [f"chunk_{i}" for i in range(len(chunks))]
    
    # Store chunk references in PostgreSQL
    for chunk, embedding_id in zip(chunks, ids):
        db_chunk = ContentChunk(
            episode_id=episode_id,
            content=chunk.content,
            chunk_index=chunk.index,
            embedding_id=embedding_id,
            token_count=chunk.token_count,
            metadata=chunk.metadata,
        )
        db.add(db_chunk)
    
    db.commit()
    
    return len(chunks)


def generate_script_sync(episode: Episode, content: str) -> Dict[str, Any]:
    """Generate podcast script (sync version)."""
    from app.services.script_generator import ScriptGenerator
    
    generator = ScriptGenerator()
    
    result = generator.generate(
        title=episode.title,
        content=content,
        personas=episode.personas or [],
        episode_id=episode.id,
        target_duration_minutes=10,
    )
    
    return result


def synthesize_audio_sync(
    segments: list,
    output_dir: str,
    personas: list,
) -> list:
    """Synthesize audio for script segments."""
    from app.services.tts import TTSService
    
    tts = TTSService()
    
    # Build voice mapping from personas
    voice_mapping = {}
    for i, persona in enumerate(personas or []):
        name = persona.get("name", f"Speaker{i}")
        # Alternate between male and female voices
        voice_id = "default_male" if i % 2 == 0 else "default_female"
        voice_mapping[name] = voice_id
    
    segments_dir = os.path.join(output_dir, "segments")
    
    result = tts.synthesize_segments(
        segments=segments,
        output_dir=segments_dir,
        voice_mapping=voice_mapping,
    )
    
    return result


def mix_audio_sync(segments: list, output_dir: str) -> Dict[str, Any]:
    """Mix audio segments into final podcast."""
    from app.services.audio_mixer import AudioMixer
    
    mixer = AudioMixer()
    
    output_path = os.path.join(output_dir, "podcast.mp3")
    
    result = mixer.mix(
        segments=segments,
        output_path=output_path,
        pause_between_segments=400,
    )
    
    return result


def generate_cover_sync(episode: Episode, output_dir: str) -> str:
    """Generate podcast cover image."""
    from app.services.image_generator import ImageGenerator
    
    generator = ImageGenerator(use_local=False)
    
    output_path = os.path.join(output_dir, "cover.png")
    
    result = generator.generate_podcast_cover(
        title=episode.title,
        description=episode.description,
        style="modern",
        output_path=output_path,
    )
    
    if result is None:
        raise RuntimeError("Image generation returned None (API unavailable)")
    
    return result
