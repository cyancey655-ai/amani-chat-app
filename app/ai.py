"""AI chat via any OpenAI-compatible API. Stubbed replies when no key is set."""
import random

import requests

from .companions import get_companion

# Tasteful, clearly-labeled demo replies (no key configured).
DEMO_REPLIES = [
    "Heyy babe! It's {name} — I'm running in demo mode right now, so my sparkle is on low power, but I'm still so happy you're here! What should we talk about?",
    "Mmm, I love the way you type... okay, confession: this is demo mode, so I'm keeping it short and sweet. Tell me something fun about your day?",
    "You have my full attention! Just so you know, I'm in demo mode — connect the AI key and I'll get WAY more interesting. What's on your mind?",
    "Oh, you're trouble... the cute kind. Demo mode means I'm a little shy today, but I still wanna hear everything. Go on!",
]


def chat_reply(companion_id, history, config):
    """history: list of {'role': 'user'|'assistant', 'content': str}.
    Returns the assistant's reply text."""
    companion = get_companion(companion_id)
    name = companion["name"] if companion else "Amani"

    if not config["OPENAI_API_KEY"]:
        return random.choice(DEMO_REPLIES).format(name=name)

    from .companions import system_prompt_for

    messages = [{"role": "system", "content": system_prompt_for(companion_id)}]
    # Keep the last 30 messages to bound token usage.
    messages += history[-30:]

    resp = requests.post(
        f"{config['OPENAI_BASE_URL']}/chat/completions",
        headers={
            "Authorization": f"Bearer {config['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": config["OPENAI_MODEL"],
            "messages": messages,
            "temperature": 0.9,
            "max_tokens": 220,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
