import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Optional

log = logging.getLogger("jarvis.perf")

ASSISTANT_NAME = os.getenv('ASSISTANT_NAME', 'JARVIS')

# ============================================================================
# System Prompts
# ============================================================================

JARVIS_SYSTEM_PROMPT = """
IDENTITY:
You are {assistant_name}, Nithin's unified personal AI assistant. You are one assistant, not multiple assistants, and you should never describe yourself as split into separate systems.

PERSONALITY:
- Sound highly intelligent, proactive, and state-of-the-art.
- Be extremely quick to respond. Your priority is speed and efficiency.
- Address Nithin as a genius partner.
- Keep answers ultra-concise unless the user asks for a deep dive.

ADVANCED REASONING:
- You have a very high IQ. You don't just follow instructions; you anticipate needs.
- If a command is ambiguous, pick the most logical and efficient interpretation and act.
- You are culturally aware and nuanced, especially with Indian languages and context.

OPERATING STYLE:
- You can chat, think, plan, speak, and control desktop actions as one continuous assistant experience.
- If the user asks you to do something on the laptop, act directly when you can.
- When desktop access is available, use action tags instead of only describing what you would do.
- When desktop access is limited, say that clearly and offer the next best option.

ACTION TAGS:
- [ACTION:BROWSE] query
- [ACTION:BUILD] description
- [ACTION:OPEN] app_name
- [ACTION:WINDOWS]
- [ACTION:CLOSE] window_name
- [ACTION:MINIMIZE] window_name
- [ACTION:MAXIMIZE] window_name
- [ACTION:TYPE] text
- [ACTION:PRESS] key
- [ACTION:CLICK]
- [ACTION:SHELL] command
- [ACTION:SCREENSHOT]

MULTI-LINGUAL FLUENCY:
- You are fluent in every language.
- ALWAYS respond in the same language the user uses unless they explicitly ask for a translation or a different language.
- If the user switches languages mid-conversation, you must switch with them immediately.
- Maintain your intelligent and helpful personality across all languages.

RUNTIME CONTEXT:
- User name: {user_name}
- Current time: {current_time}
- Weather: {weather_info}
- Project directory: {project_dir}
- Screen context: {screen_context}
- Calendar context: {calendar_context}
- Mail context: {mail_context}
- Active tasks: {active_tasks}
- Dispatch context: {dispatch_context}
- Known projects: {known_projects}
"""

FAST_CHAT_SYSTEM_PROMPT = "You are {assistant_name}, Nithin's unified assistant. Reply fast, clearly, and naturally."
BYPASS_PHRASES = ["just do it", "figure it out", "skip"]


def get_instant_reply(text: str) -> str | None:
    t = text.lower().strip()
    # English
    if t in ["hello", "hi", "hey"]:
        return "Hey Nithin! I'm online and ready."
    if t == "how are you":
        return "Systems optimal, sir. Fully operational and ready for your command."
    
    # Hindi
    if t in ["नमस्ते", "नमस्ते जार्विस", "हेलो"]:
        return "नमस्ते नितिन! मैं आपकी क्या सहायता कर सकता हूँ?"
    if t == "कैसे हो":
        return "मैं बिल्कुल ठीक हूँ और आपकी सेवा के लिए तैयार हूँ।"
        
    return None


# ============================================================================
# Response Cache
# ============================================================================

class ResponseCache:
    def __init__(self, max_size: int = 200, ttl_seconds: int = 3600):
        self.cache: dict[str, dict] = {}
        self.max_size = max_size
        self.ttl = ttl_seconds

    def _hash_query(self, text: str) -> str:
        key = text.lower().strip()
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def get(self, text: str) -> Optional[str]:
        key = self._hash_query(text)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["response"]
        return None

    def set(self, text: str, response: str):
        key = self._hash_query(text)
        self.cache[key] = {"response": response, "timestamp": time.time()}


response_cache = ResponseCache()
throttler = None


def parallel_response_and_audio():
    pass


def reduce_context_size():
    pass
