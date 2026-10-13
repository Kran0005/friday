import os
import random
import subprocess
from typing import Optional

from livekit.agents import function_tool
from .paths import MUSIC_DIR, NIRCMD_PATH, ensure_data_dirs

# === CONFIGURATION ===
MUSIC_DIRECTORY = MUSIC_DIR

# === TOOL FUNCTIONS ===
@function_tool(name="play_random_music", description="Play a random song from the music directory")
def play_random_music() -> str:
    ensure_data_dirs()
    songs = [f for f in os.listdir(MUSIC_DIRECTORY) if f.endswith(('.mp3', '.wav'))]
    if not songs:
        return "No music files found in the directory."
    song = random.choice(songs)
    full_path = os.path.join(str(MUSIC_DIRECTORY), song)
    os.startfile(full_path)  # Only works on Windows
    return f"Now playing: {song}"

@function_tool(name="pause_or_resume_music", description="Toggle pause/resume for currently playing music")
def pause_or_resume_music() -> str:
    subprocess.run([str(NIRCMD_PATH), "sendkeypress", "space"])
    return "Toggled play/pause."

@function_tool(name="stop_music", description="Stop the music by closing the default media player")
def stop_music() -> str:
    subprocess.run([str(NIRCMD_PATH), "closeprocess", "wmplayer.exe"])
    subprocess.run([str(NIRCMD_PATH), "closeprocess", "vlc.exe"])
    return "Stopped the music."

@function_tool(name="next_track", description="Play the next track")
def next_track() -> str:
    subprocess.run([str(NIRCMD_PATH), "sendkeypress", "ctrl+right"])
    return "Skipped to the next track."

@function_tool(name="previous_track", description="Play the previous track")
def previous_track() -> str:
    subprocess.run([str(NIRCMD_PATH), "sendkeypress", "ctrl+left"])
    return "Went back to the previous track."
