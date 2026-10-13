import datetime
from dotenv import load_dotenv
from livekit.agents import Agent
from livekit.plugins import google
from .prompts import AGENT_INSTRUCTION
from .tools import (
    get_weather,
    search_web,
    send_email,
    save_note,
    recall_note,
    create_reminder,
    list_reminders,
    cancel_reminder,
    remember_user_info,
    list_saved_memory,
    forget_saved_memory,
    clear_saved_memory,
    summarize_text,
    search_local_files,
    play_sound,
    journal_today,
    log_mood,
    generate_affirmation,
    control_music,
    set_volume,
    list_calendar_events,
    create_calendar_event,
    delete_calendar_event,
)
from .paths import PROJECT_ROOT
from .memory_store import memory_instructions

load_dotenv(PROJECT_ROOT / ".env")

def get_agent_instructions() -> str:
    return AGENT_INSTRUCTION + memory_instructions()

def get_dynamic_greeting() -> str:
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning, sir."
    elif 12 <= hour < 17:
        return "Good afternoon, sir."
    else:
        return "Good evening, sir."

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=get_agent_instructions(),
            llm=google.LLM(
                model="gemini-3.5-flash-lite",
                temperature=0.8,
            ),
            tools=[
                get_weather,
                search_web,
                send_email,
                save_note,
                recall_note,
                create_reminder,
                list_reminders,
                cancel_reminder,
                remember_user_info,
                list_saved_memory,
                forget_saved_memory,
                clear_saved_memory,
                summarize_text,
                search_local_files,
                play_sound,
                journal_today,
                log_mood,
                generate_affirmation,
                control_music,
                set_volume,
                list_calendar_events,
                create_calendar_event,
                delete_calendar_event,
            ],
        )
if __name__ == "__main__":
    # Create an instance of your Assistant
    assistant = Assistant()

    # Optional: show greeting
    print(get_dynamic_greeting())

    # Start the agent — check the LiveKit Agent API for the right method
    # If Agent has a run() or serve() method, call it here.
    # For now, let's just keep the script alive as a placeholder:
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Assistant: Goodbye!")
            break
        # Here you would send the input to your assistant and get a response
        # For demo purposes:
        print(f"Assistant: I heard you say '{user_input}'")
