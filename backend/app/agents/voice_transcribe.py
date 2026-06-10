import logging
import subprocess


_model = None
logger = logging.getLogger(__name__)


def get_model():
    global _model
    if _model is None:
        import whisper
        # Downloads model first run (~1GB)
        _model = whisper.load_model("base")
    return _model


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file (.ogg, .mp3, .wav) to text."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=8)
    except Exception as exc:
        logger.warning("ffmpeg_unavailable", extra={"error": str(exc)})
        raise RuntimeError("FFmpeg is required for audio transcription and was not found in PATH.") from exc

    model = get_model()
    try:
        result = model.transcribe(audio_path)
        return result["text"].strip()
    except Exception as exc:
        logger.exception("audio_transcription_failed")
        raise RuntimeError(f"Whisper transcription failed: {exc}") from exc
