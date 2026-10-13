from resemblyzer import VoiceEncoder, preprocess_wav
import numpy as np
import sounddevice as sd
import time
import os

REFERENCE_FILE = "user_voiceprint.wav"
TEST_FILE = "test_voice.wav"
DURATION = 3
FS = 44100

def record_voice(filename, duration):
    print("🎙️ Speak now...")
    recording = sd.rec(int(duration * FS), samplerate=FS, channels=1, dtype='int16')
    sd.wait()
    from scipy.io.wavfile import write
    write(filename, FS, recording)
    print(f"✅ Saved: {filename}")

def compare_voices(reference_path, test_path, threshold=0.75):
    encoder = VoiceEncoder()
    ref_wav = preprocess_wav(reference_path)
    test_wav = preprocess_wav(test_path)

    ref_embed = encoder.embed_utterance(ref_wav)
    test_embed = encoder.embed_utterance(test_wav)

    similarity = np.dot(ref_embed, test_embed) / (np.linalg.norm(ref_embed) * np.linalg.norm(test_embed))
    return similarity

# Step 1: Record live test
record_voice(TEST_FILE, DURATION)

# Step 2: Compare
score = compare_voices(REFERENCE_FILE, TEST_FILE)
print(f"🧠 Similarity score: {score:.2f}")

if score > 0.75:
    print("🔓 Voice match! Launching Friday...")
    os.system("python agent.py console")
else:
    print("⛔ Voice not recognized.")
