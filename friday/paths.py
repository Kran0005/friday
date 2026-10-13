from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PRIVATE_DIR = DATA_DIR / "private"
STATE_DIR = DATA_DIR / "state"
RUNTIME_DIR = DATA_DIR / "runtime"
VOICEPRINTS_DIR = DATA_DIR / "voiceprints"
MUSIC_DIR = DATA_DIR / "music"
WAKEWORD_MODEL_DIR = PROJECT_ROOT / "assets" / "wakewords" / "openwakeword"
WAKEWORD_MODEL = WAKEWORD_MODEL_DIR / "hey_jarvis_v0.1.onnx"
WAKEWORD_MELSPECTROGRAM = WAKEWORD_MODEL_DIR / "melspectrogram.onnx"
WAKEWORD_EMBEDDING = WAKEWORD_MODEL_DIR / "embedding_model.onnx"
NIRCMD_PATH = PROJECT_ROOT / "vendor" / "nircmd" / "nircmd.exe"


def ensure_data_dirs() -> None:
    for directory in (PRIVATE_DIR, STATE_DIR, RUNTIME_DIR, VOICEPRINTS_DIR, MUSIC_DIR):
        directory.mkdir(parents=True, exist_ok=True)
