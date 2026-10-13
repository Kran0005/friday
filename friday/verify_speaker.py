# verify_speaker.py

from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
import numpy as np
import warnings
from .paths import RUNTIME_DIR, VOICEPRINTS_DIR

warnings.filterwarnings("ignore")  # Optional: suppress numpy and deprecation warnings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two voice embeddings."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def verify_voice(test_path: str, ref_path: str, threshold: float = 0.80) -> bool:
    """
    Verifies if the speaker in test_path matches the reference voiceprint.

    Args:
        test_path (str): Path to test audio (e.g., 'test_voice.wav').
        ref_path (str): Path to saved reference voiceprint (e.g., 'user_voiceprint.wav').
        threshold (float): Cosine similarity threshold (default 0.80).

    Returns:
        bool: True if voice matches, False otherwise.
    """
    try:
        print("[🔊] Loading audio files...")
        ref_wav = preprocess_wav(Path(ref_path))
        test_wav = preprocess_wav(Path(test_path))

        encoder = VoiceEncoder()
        print("[🧠] Encoding voices...")
        ref_embed = encoder.embed_utterance(ref_wav)
        test_embed = encoder.embed_utterance(test_wav)

        similarity = cosine_similarity(ref_embed, test_embed)
        print(f"[🔍] Cosine similarity: {similarity:.4f}")

        if similarity >= threshold:
            print("✅ Same speaker detected. Voice is authenticated.")
            return True
        else:
            print("❌ Different speaker detected. Voice authentication failed.")
            return False

    except Exception as e:
        print(f"[verify_speaker] Error: {e}")
        return False


# Optional CLI testing
if __name__ == "__main__":
    print("[🧪] Running speaker verification test...")
    result = verify_voice(str(RUNTIME_DIR / "test_voice.wav"), str(VOICEPRINTS_DIR / "user_voiceprint.wav"))
    print(f"Match result: {'✅ MATCH' if result else '❌ NO MATCH'}")
