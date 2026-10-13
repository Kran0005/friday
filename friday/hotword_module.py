from openwakeword.model import Model
import pyaudio
import threading
import speech_recognition as sr
import wave
import os
import numpy as np
from dotenv import load_dotenv
from .verify_speaker import verify_voice
from .audio_devices import get_input_device_index
from .paths import (
    PROJECT_ROOT,
    RUNTIME_DIR,
    WAKEWORD_MODEL,
    WAKEWORD_MELSPECTROGRAM,
    WAKEWORD_EMBEDDING,
    ensure_data_dirs,
)

load_dotenv(PROJECT_ROOT / ".env")

class HotwordListener:
    SAMPLE_RATE = 16000
    FRAME_LENGTH = 1280  # openWakeWord expects 80 ms frames at 16 kHz.
    WAKEWORD_KEY = "hey_jarvis_v0.1"
    THRESHOLD = 0.5

    def __init__(self, on_detect_callback, voiceprints_dir=None, gui_callback=None):
        missing = [
            path for path in (WAKEWORD_MODEL, WAKEWORD_MELSPECTROGRAM, WAKEWORD_EMBEDDING)
            if not path.is_file()
        ]
        if missing:
            paths = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(
                "openWakeWord model files are missing. Download them using the setup "
                f"instructions in README.md. Missing: {paths}"
            )

        self.model = Model(
            wakeword_models=[str(WAKEWORD_MODEL)],
            inference_framework="onnx",
            melspec_model_path=str(WAKEWORD_MELSPECTROGRAM),
            embedding_model_path=str(WAKEWORD_EMBEDDING),
        )
        self.pa = None
        self.audio_stream = None
        self.running = False
        self.callback = on_detect_callback
        self.voiceprints_dir = voiceprints_dir
        self.gui_callback = gui_callback
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.voice_auth_enabled = True

    def start(self):
        if self.running:
            return
        try:
            self._open_audio_stream()
        except Exception as exc:
            if self.pa:
                self.pa.terminate()
                self.pa = None
            raise RuntimeError(
                "No usable microphone is connected or enabled. Connect a microphone, "
                "or set FRIDAY_MIC_DEVICE to an available input device. "
                f"Audio error: {exc}"
            ) from exc
        self.running = True
        self.thread.start()

    def _open_audio_stream(self):
        if self.pa is None:
            self.pa = pyaudio.PyAudio()
        self.input_device_index = get_input_device_index(self.pa)
        device_name = self.pa.get_device_info_by_index(self.input_device_index)["name"]
        print(f"[HotwordListener] Using microphone: {device_name}")
        self.audio_stream = self.pa.open(
            rate=self.SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=self.FRAME_LENGTH,
        )

    def stop(self):
        self.running = False
        if self.audio_stream:
            try:
                if self.audio_stream.is_active():
                    self.audio_stream.stop_stream()
            except Exception as exc:
                print(f"[HotwordListener] Could not stop microphone cleanly: {exc}")
            try:
                self.audio_stream.close()
            except Exception as exc:
                print(f"[HotwordListener] Could not close microphone cleanly: {exc}")
            self.audio_stream = None
        if self.pa:
            self.pa.terminate()
            self.pa = None

    def set_auth_enabled(self, enabled: bool):
        self.voice_auth_enabled = enabled

    def _run(self):
        try:
            print("[HotwordListener] Listening for wakeword...")
            if self.gui_callback:
                self.gui_callback("🎤 Listening")

            while self.running:
                pcm = self.audio_stream.read(self.FRAME_LENGTH, exception_on_overflow=False)
                samples = np.frombuffer(pcm, dtype=np.int16)
                prediction = self.model.predict(samples)
                if prediction.get(self.WAKEWORD_KEY, 0.0) >= self.THRESHOLD:
                    print("[HotwordListener] Wakeword detected!")
                    if self.gui_callback:
                        self.gui_callback("✅ Wakeword")
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                    self.audio_stream = None
                    self._listen_command()
                    self.model.reset()
                    if self.running:
                        self._open_audio_stream()
        except Exception as exc:
            if self.running:
                print(f"[HotwordListener] Listener stopped after an error: {exc}")
        finally:
            self.running = False
            if self.audio_stream:
                try:
                    if self.audio_stream.is_active():
                        self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except Exception as exc:
                    print(f"[HotwordListener] Microphone cleanup error: {exc}")
                self.audio_stream = None
            if self.pa:
                self.pa.terminate()
                self.pa = None

    def _listen_command(self):
        recognizer = sr.Recognizer()
        mic = sr.Microphone(device_index=self.input_device_index, sample_rate=self.SAMPLE_RATE)

        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
            print("[HotwordListener] Listening for your command...")
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)

                # Save command to temporary file for verification
                ensure_data_dirs()
                test_audio = RUNTIME_DIR / "live_test.wav"
                with wave.open(str(test_audio), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(audio.get_raw_data())

                # Transcribe command
                text = recognizer.recognize_google(audio)
                print(f"[HotwordListener] Transcription: {text}")

                # Voice verification
                user_verified = False
                if self.voice_auth_enabled and self.voiceprints_dir:
                    print("[HotwordListener] Authenticating voice...")
                    if self.gui_callback:
                        self.gui_callback("🔐 Authenticating...")

                    for file in os.listdir(self.voiceprints_dir):
                        if file.endswith(".wav"):
                            ref_path = os.path.join(self.voiceprints_dir, file)
                            if verify_voice(str(test_audio), ref_path):
                                user_verified = True
                                matched_user = os.path.splitext(file)[0]
                                print(f"[HotwordListener] ✅ Voice matched: {matched_user}")
                                break

                self.callback(text, user_verified)

            except sr.WaitTimeoutError:
                print("[HotwordListener] Timeout: No speech detected.")
            except sr.UnknownValueError:
                print("[HotwordListener] Could not understand audio.")
            except Exception as e:
                print(f"[HotwordListener] Error: {e}")
