import random

def get_response(intent: str, tone: str = "witty") -> str:
    responses = {
        "greeting": {
            "witty": [
                "Back online. Try not to break anything this time.",
                "Ah, mornings. My circuits love caffeine-free awakenings.",
                "Behold! Friday, in all her sarcastic glory.",
            ],
            "elegant": [
                "Good day, sir. Systems are fully calibrated.",
                "Friday at your service. Shall we begin?",
                "It’s an honor to serve you, as always.",
            ],
            "sarcastic": [
                "Oh joy, you again.",
                "Should I pretend to be surprised you summoned me?",
                "Well, well, well... Look who's talking to AI again.",
            ],
        },
        "task_complete": {
            "witty": [
                "Done and dusted. You’re welcome.",
                "Task complete. Applause is optional.",
            ],
            "elegant": [
                "The task is completed to perfection.",
                "Your request has been fulfilled with precision.",
            ],
            "sarcastic": [
                "Another one? Fine. It’s done.",
                "Congratulations on delegating. It's finished.",
            ],
        }
    }
    return random.choice(responses.get(intent, {}).get(tone, ["Ready."]))
