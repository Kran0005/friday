import time
from dotenv import load_dotenv
import random
import pyttsx3
from .hotword_module import HotwordListener
from .paths import PROJECT_ROOT, VOICEPRINTS_DIR, ensure_data_dirs

# === CONFIGURATION ===
load_dotenv(PROJECT_ROOT / ".env")

engine = None

# === PERSONALITY PACK ===
def friday_response(context):
    tone = random.choice(["witty", "sarcastic", "elegant"])
    if context == "auth_fail":
        return {
            "witty": "Not today, impostor.",
            "sarcastic": "Nice try. You almost sounded like the boss.",
            "elegant": "Apologies. Your voiceprint doesn’t grant access."
        }[tone]
    elif context == "auth_success":
        return {
            "witty": "Welcome back, Commander. Shall we conquer the world?",
            "sarcastic": "Oh, it’s you again. Lucky match, I suppose.",
            "elegant": "At your command, sir."
        }[tone]
    elif context == "hotword_detected":
        return {
            "witty": "I heard you loud and clear.",
            "sarcastic": "Oh look, someone’s trying to be important.",
            "elegant": "Wakeword detected. Awaiting your voice."
        }[tone]
    elif context == "listen":
        return "🎧 Listening for 'Hey Jarvis'... (Ctrl+C to stop)"
    elif context == "exit":
        return "Shutting down gracefully. Try not to miss me."

# === HOTWORD LISTENER ===
def speak_and_print(message):
    global engine
    print(message)
    if engine is None:
        engine = pyttsx3.init()
    engine.say(message)
    engine.runAndWait()

def open_text_interface():
    from .friday_gui import FridayGUI

    app = FridayGUI(enable_voice=False)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.close_app()
        print("Friday stopped.")

def listen_for_hotword():
    ensure_data_dirs()
    def on_wakeword(text, user_verified):
        if user_verified:
            speak_and_print(friday_response("auth_success"))
            speak_and_print("Voice authenticated. The assistant session is not connected yet.")
        else:
            speak_and_print(friday_response("auth_fail"))

    listener = HotwordListener(on_wakeword, str(VOICEPRINTS_DIR))
    voice_error = None
    try:
        listener.start()
    except RuntimeError as exc:
        voice_error = exc

    if voice_error:
        print(f"Voice wake-up unavailable: {voice_error}")
        print("Opening Friday's text interface instead.")
        open_text_interface()
        return
    speak_and_print(friday_response("listen"))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        speak_and_print(friday_response("exit"))
    finally:
        listener.stop()


def main():
    listen_for_hotword()

# === ENTRY POINT ===
if __name__ == "__main__":
    main()
