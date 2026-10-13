# visualize_audio.py

import os
import wave
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import spectrogram
import customtkinter as ctk
import pyaudio
import threading
import time
from .paths import RUNTIME_DIR


# ─── Offline Analysis: Plot waveform and spectrogram ────────────────────────── #

def load_wav(file_path):
    """Load WAV file and return audio data and frame rate."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ File not found: {file_path}")

    with wave.open(file_path, 'rb') as wf:
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        audio_data = wf.readframes(n_frames)
        signal = np.frombuffer(audio_data, dtype=np.int16)
    return signal, framerate


def plot_waveform(signal, framerate, title="Waveform"):
    """Plot audio waveform."""
    duration = len(signal) / framerate
    time_axis = np.linspace(0, duration, len(signal))
    plt.figure(figsize=(10, 4))
    plt.plot(time_axis, signal, color='steelblue')
    plt.title(title)
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_spectrogram(signal, framerate, title="Spectrogram"):
    """Plot audio spectrogram."""
    f, t, Sxx = spectrogram(signal, framerate)
    plt.figure(figsize=(10, 4))
    plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-9), shading='gouraud', cmap="inferno")
    plt.title(title)
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [s]')
    plt.colorbar(label='dB')
    plt.tight_layout()
    plt.show()


def visualize(file_path="test_voice.wav"):
    """Combined offline visualization function."""
    try:
        print(f"[🎧] Visualizing: {file_path}")
        signal, rate = load_wav(file_path)
        plot_waveform(signal, rate, title=f"Waveform - {os.path.basename(file_path)}")
        plot_spectrogram(signal, rate, title=f"Spectrogram - {os.path.basename(file_path)}")
    except Exception as e:
        print(f"[❌] Visualization error: {e}")


# ─── GUI Widget: Realtime SpectrumVisualizer for FridayGUI ───────────────────── #

class SpectrumVisualizer(ctk.CTkFrame):
    def __init__(self, master, width=800, height=100):
        super().__init__(master)
        self.canvas = ctk.CTkCanvas(self, width=width, height=height, bg="#222222", highlightthickness=0)
        self.canvas.pack()
        self.width = width
        self.height = height
        self.running = False

    def start_visualization(self, input_device_index=None):
        self.running = True
        threading.Thread(target=self._update_loop, args=(input_device_index,), daemon=True).start()

    def stop_visualization(self):
        self.running = False

    def _update_loop(self, input_device_index=None):
        p = pyaudio.PyAudio()
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=1024,
            )
            while self.running:
                try:
                    data = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
                    spectrum = np.abs(np.fft.fft(data)[:50])  # First 50 frequency bins
                    self._draw_bars(spectrum)
                    time.sleep(0.05)
                except Exception as e:
                    print(f"[❌ Visualizer Loop Error] {e}")
        except Exception as e:
            print(f"[❌ Audio Stream Error] {e}")
        finally:
            p.terminate()

    def _draw_bars(self, spectrum):
        self.canvas.delete("all")
        bar_width = max(1, self.width // len(spectrum))
        for i, mag in enumerate(spectrum):
            height = min(self.height, int(mag / 500 * self.height))  # normalize
            x0 = i * bar_width
            y0 = self.height - height
            x1 = x0 + bar_width - 2
            y1 = self.height
            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#00FFAA", outline="")


# ─── Optional CLI Usage ─────────────────────────────────────────────────────── #

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Visualize .wav audio file")
    parser.add_argument("--file", type=str, default=str(RUNTIME_DIR / "test_voice.wav"), help="Path to .wav file")
    args = parser.parse_args()
    visualize(args.file)
