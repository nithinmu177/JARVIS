import asyncio
import base64
import re
import json
import logging
import os
import sys
import time
import uuid
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import anthropic
import httpx
import google.generativeai as genai
from openai import AsyncOpenAI
import edge_tts
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel

# Internal imports
from actions import (
    execute_action, monitor_build, open_terminal, open_browser, 
    open_claude_in_project, _generate_project_name, prompt_existing_terminal,
    parse_desktop_command, get_desktop_access_status
)
from brain import brain
from work_mode import WorkSession, is_casual_question
from screen import get_active_windows, take_screenshot, describe_screen, format_windows_for_context
from calendar_access import (
    get_todays_events, get_upcoming_events, get_next_event, 
    format_events_for_context, format_schedule_summary, refresh_cache as refresh_calendar_cache
)
from mail_access import (
    get_unread_count, get_unread_messages, get_recent_messages, search_mail, 
    read_message, format_unread_summary, format_messages_for_context, format_messages_for_voice
)
from memory import (
    remember, recall, get_open_tasks, create_task, complete_task, search_tasks,
    create_note, search_notes, get_tasks_for_date, build_memory_context,
    format_tasks_for_voice, extract_memories, get_important_memories,
)
from notes_access import get_recent_notes, read_note, search_notes_apple, create_apple_note
from dispatch_registry import DispatchRegistry
from planner import TaskPlanner, detect_planning_mode, BYPASS_PHRASES
from performance import (
    JARVIS_SYSTEM_PROMPT, FAST_CHAT_SYSTEM_PROMPT, 
    BYPASS_PHRASES, response_cache, throttler, get_instant_reply, 
    parallel_response_and_audio, reduce_context_size
)

# -- Configuration -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("jarvis")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# App Constants
USER_NAME = os.getenv("USER_NAME", "Nithin")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = Path(PROJECT_DIR) / "frontend" / "dist"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google").lower()
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").lower()
EDGE_VOICE = os.getenv("EDGE_VOICE", "en-GB-RyanNeural")
LANGUAGE_VOICE_MAP = {
    "en-IN": "en-IN-NeerjaExpressiveNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "bn-IN": "bn-IN-TanishaaNeural",
    "gu-IN": "gu-IN-DhwaniNeural",
    "kn-IN": "kn-IN-SapnaNeural",
    "ml-IN": "ml-IN-SobhanaNeural",
    "mr-IN": "mr-IN-AarohiNeural",
    "pa-IN": "pa-IN-GurleenNeural",
    "ta-IN": "ta-IN-PallaviNeural",
    "te-IN": "te-IN-ShrutiNeural",
    "ur-IN": "ur-IN-GulNeural",
}

# ---------------------------------------------------------------------------
# Task Manager
# ---------------------------------------------------------------------------

class ClaudeTaskManager:
    """Manages background tasks (mock for now to satisfy imports)."""
    def __init__(self, max_concurrent=3):
        self.websockets = []
    def register_websocket(self, ws):
        self.websockets.append(ws)
    def unregister_websocket(self, ws):
        if ws in self.websockets: self.websockets.remove(ws)
    def get_active_tasks_summary(self):
        return "No active background tasks."

task_manager = ClaudeTaskManager()
_last_greeting_time = 0


def apply_speech_corrections(text: str) -> str:
    """Normalize common speech-to-text errors for command routing."""
    corrected = text.strip()
    replacements = {
        r"\bcloud code\b": "claude code",
        r"\bclock code\b": "claude code",
        r"\bnote pad\b": "notepad",
        r"\bpower shell\b": "powershell",
        r"\bcontrol\b": "ctrl",
    }
    for pattern, replacement in replacements.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    return corrected


def extract_wake_command(text: str) -> str | None:
    """Return the command after an explicit wake word, or None."""
    match = re.match(r"^\s*(jarvis|aura)\b[\s,:-]*(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    command = match.group(2).strip()
    return command or None


async def classify_intent(text: str, client: Any = None) -> Dict[str, str]:
    """Lightweight deterministic classifier for voice commands."""
    corrected = apply_speech_corrections(text)
    lower = corrected.lower().strip()

    if any(phrase in lower for phrase in ["open terminal", "open the terminal", "claude code", "launch terminal"]):
        return {"action": "open_terminal", "target": ""}

    if any(phrase in lower for phrase in ["search for", "google ", "look up", "go to ", "pull up "]):
        return {"action": "browse", "target": corrected}

    build_starters = ("build", "create", "make")
    if lower.startswith(build_starters):
        return {"action": "build", "target": corrected}

    direct_action = parse_desktop_command(corrected)
    if direct_action:
        return direct_action

    return {"action": "chat", "target": corrected}

# ---------------------------------------------------------------------------
# Core Brain Interface
# ---------------------------------------------------------------------------

async def generate_response(
    text: str,
    client: Any,
    task_mgr: Optional[ClaudeTaskManager],
    projects: List[str],
    conversation_history: List[Dict[str, str]],
    last_response: str = "",
    session_summary: str = "",
) -> str:
    """Generate JARVIS response using the unified JarvisBrain."""
    try:
        current_time = datetime.now().strftime("%I:%M %p")
        weather = "Weather data unavailable"
        
        system = JARVIS_SYSTEM_PROMPT.format(
            user_name=USER_NAME,
            current_time=current_time,
            weather_info=weather,
            project_dir=PROJECT_DIR,
            screen_context="Screen context limited on Windows",
            calendar_context="Calendar unavailable on Windows",
            mail_context="Mail unavailable on Windows",
            active_tasks=task_mgr.get_active_tasks_summary() if task_mgr else "[]",
            dispatch_context="",
            known_projects=", ".join(projects)
        )
        
        return await brain.think(
            prompt=text,
            history=conversation_history,
            system_prompt=system
        )
    except Exception as e:
        log.error(f"Brain failure: {e}")
        return "I'm having trouble reaching my internal brain components, sir."

# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def resolve_voice_for_language(language: str | None) -> str:
    if not language:
        return EDGE_VOICE
    return LANGUAGE_VOICE_MAP.get(language, EDGE_VOICE)


async def synthesize_speech(text: str, voice: str | None = None) -> Optional[bytes]:
    if not text: return None
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice or EDGE_VOICE)
        audio_bytes = b""
        async with asyncio.timeout(10.0): # 10 second timeout for TTS
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
        return audio_bytes if audio_bytes else None
    except Exception as e:
        if voice and voice != EDGE_VOICE:
            log.warning(f"TTS voice {voice} failed, falling back to default voice: {e}")
            try:
                import edge_tts
                communicate = edge_tts.Communicate(text, EDGE_VOICE)
                audio_bytes = b""
                async with asyncio.timeout(10.0):
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_bytes += chunk["data"]
                return audio_bytes if audio_bytes else None
            except Exception as fallback_error:
                log.error(f"TTS fallback error: {fallback_error}")
        else:
            log.error(f"TTS error: {e}")
    return None

def strip_markdown_for_tts(text: str) -> str:
    import re
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = text.replace('**', '').replace('*', '').replace('`', '')
    text = re.sub(r'^#+ ', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    log.info("JARVIS server starting")
    yield

app = FastAPI(title="JARVIS Server", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

@app.get("/api/health")
async def health():
    return {"status": "online", "brain": "unified"}


@app.get("/api/access-status")
async def access_status():
    return get_desktop_access_status()

@app.websocket("/ws/voice")
async def voice_handler(ws: WebSocket):
    await ws.accept()
    log.info("Voice WebSocket connected")
    history = []
    session_language = "en-IN"
    session_voice = resolve_voice_for_language(session_language)

    await ws.send_json({"type": "access_status", "status": get_desktop_access_status()})
    
    # Send Greeting
    greeting = "Systems online, sir."
    audio = await synthesize_speech(greeting, session_voice)
    if audio:
        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": greeting})
    
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "transcript" and msg.get("isFinal"):
                user_text = apply_speech_corrections(msg.get("text", "").strip())
                source = str(msg.get("source", "unknown")).lower()
                session_language = str(msg.get("language", session_language))
                session_voice = resolve_voice_for_language(session_language)
                log.info(f"User: {user_text}")
                
                await ws.send_json({"type": "status", "state": "thinking"})

                action_text = user_text
                if source == "voice":
                    action_text = extract_wake_command(user_text) or ""

                direct_action = parse_desktop_command(action_text) if action_text else None
                if direct_action:
                    result = await execute_action(direct_action)
                    confirmation = result.get("confirmation") or "Done."
                    if result.get("details"):
                        await ws.send_json({"type": "access_status", "status": result["details"]})
                    conf_audio = await synthesize_speech(confirmation, session_voice)
                    await ws.send_json({"type": "status", "state": "speaking"})
                    if conf_audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(conf_audio).decode(), "text": confirmation})
                    else:
                        await ws.send_json({"type": "text", "text": confirmation})
                    await ws.send_json({"type": "status", "state": "idle"})
                    continue

                if source == "voice" and parse_desktop_command(user_text):
                    warning = "For laptop control by voice, start with Jarvis. Example: Jarvis open notepad."
                    warn_audio = await synthesize_speech(warning, session_voice)
                    await ws.send_json({"type": "status", "state": "speaking"})
                    if warn_audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(warn_audio).decode(), "text": warning})
                    else:
                        await ws.send_json({"type": "text", "text": warning})
                    await ws.send_json({"type": "status", "state": "idle"})
                    continue
                
                # Check for instant cached reply for zero latency
                response_text = get_instant_reply(user_text)
                
                if response_text:
                    history.append({"role": "user", "content": user_text})
                    history.append({"role": "assistant", "content": response_text})
                    tts_text = strip_markdown_for_tts(response_text)
                    audio_data = await synthesize_speech(tts_text, session_voice)
                    await ws.send_json({"type": "status", "state": "speaking"})
                    if audio_data:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio_data).decode(), "text": response_text})
                    else:
                        await ws.send_json({"type": "text", "text": response_text})
                else:
                    # Streaming path for complex answers
                    full_text = ""
                    sentence_buffer = ""
                    history.append({"role": "user", "content": user_text})
                    
                    # Prepare system prompt
                    current_time = datetime.now().strftime("%I:%M %p")
                    system = JARVIS_SYSTEM_PROMPT.format(
                        user_name=USER_NAME,
                        current_time=current_time,
                        weather_info="Optimal conditions",
                        project_dir=PROJECT_DIR,
                        screen_context="Windows 11 System Access",
                        calendar_context="Ready",
                        mail_context="Ready",
                        active_tasks="[]",
                        dispatch_context="",
                        known_projects=""
                    )

                    async for chunk in brain.stream_think(user_text, history[:-1], system_prompt=system):
                        full_text += chunk
                        sentence_buffer += chunk
                        
                        # Detect sentence boundaries to generate audio chunks
                        if any(term in sentence_buffer for term in [". ", "! ", "? ", "\n"]):
                            # Split buffer into sentences
                            parts = re.split(r'(?<=[.!?\n]) ', sentence_buffer)
                            for i in range(len(parts) - 1):
                                sentence = parts[i].strip()
                                if sentence:
                                    # Send partial text immediately
                                    await ws.send_json({"type": "status", "state": "speaking"})
                                    tts_part = strip_markdown_for_tts(sentence)
                                    audio_part = await synthesize_speech(tts_part, session_voice)
                                    if audio_part:
                                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio_part).decode(), "text": sentence})
                            sentence_buffer = parts[-1]
                    
                    # Send remaining buffer
                    if sentence_buffer.strip():
                        await ws.send_json({"type": "status", "state": "speaking"})
                        tts_part = strip_markdown_for_tts(sentence_buffer)
                        audio_part = await synthesize_speech(tts_part, session_voice)
                        if audio_part:
                            await ws.send_json({"type": "audio", "data": base64.b64encode(audio_part).decode(), "text": sentence_buffer})
                    
                    history.append({"role": "assistant", "content": full_text})

                    # ACTION DETECTION
                    # Check for [ACTION:TYPE] or similar tags in the full response
                    action_match = re.search(r'\[ACTION:(\w+)\]\s*(.*)', full_text, re.IGNORECASE)
                    if action_match:
                        action_name = action_match.group(1).lower()
                        target = action_match.group(2).strip()
                        log.info(f"ACTION DETECTED: {action_name} -> {target}")
                        
                        # Execute the action
                        result = await execute_action({"action": action_name, "target": target})
                        if result.get("confirmation"):
                            # Optionally speak the confirmation
                            conf_audio = await synthesize_speech(result["confirmation"], session_voice)
                            if conf_audio:
                                await ws.send_json({"type": "audio", "data": base64.b64encode(conf_audio).decode(), "text": result["confirmation"]})
                
                await ws.send_json({"type": "status", "state": "idle"})
                
    except WebSocketDisconnect:
        log.info("Voice WebSocket disconnected")


@app.get("/")
async def frontend_index():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {
            "status": "online",
            "message": "Frontend build not found. Run 'npm run build' in the frontend directory.",
        },
        status_code=503,
    )


@app.get("/{full_path:path}")
async def frontend_assets(full_path: str):
    if full_path.startswith(("api/", "ws/")):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    target = FRONTEND_DIST / full_path
    if target.exists() and target.is_file():
        return FileResponse(target)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse({"detail": "Not found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8340")))
