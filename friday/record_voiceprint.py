import sounddevice as sd
import wave
from .paths import VOICEPRINTS_DIR, ensure_data_dirs

def main():
    duration = 5  # seconds
    fs = 44100
    ensure_data_dirs()
    output_file = VOICEPRINTS_DIR / "user_voiceprint.wav"

    print("🎙️ Please speak clearly for 5 seconds to record your voiceprint...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="int16")
    sd.wait()

    with wave.open(str(output_file), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(recording.tobytes())

    print(f"✅ Voiceprint saved to {output_file}")


if __name__ == "__main__":
    main()
