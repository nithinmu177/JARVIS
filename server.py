import asyncio
import base64
import re
import json
import logging
import os
import shutil
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
from mobile_actions import mobile_controller
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
    parallel_response_and_audio, reduce_context_size, ASSISTANT_NAME
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
    "af-ZA": "af-ZA-AdriNeural", "sq-AL": "sq-AL-AnilaNeural", "am-ET": "am-ET-AmehaNeural",
    "ar-DZ": "ar-DZ-AminaNeural", "ar-BH": "ar-BH-AliNeural", "ar-EG": "ar-EG-SalmaNeural",
    "ar-IQ": "ar-IQ-BasselNeural", "ar-JO": "ar-JO-SanaNeural", "ar-KW": "ar-KW-FahedNeural",
    "ar-LB": "ar-LB-LaylaNeural", "ar-LY": "ar-LY-ImanNeural", "ar-MA": "ar-MA-JamalNeural",
    "ar-OM": "ar-OM-AbdullahNeural", "ar-QA": "ar-QA-AmalNeural", "ar-SA": "ar-SA-HamedNeural",
    "ar-SY": "ar-SY-AmanyNeural", "ar-TN": "ar-TN-HediNeural", "ar-AE": "ar-AE-FatimaNeural",
    "ar-YE": "ar-YE-MaryamNeural", "az-AZ": "az-AZ-BabekNeural", "bn-BD": "bn-BD-NabanitaNeural",
    "bn-IN": "bn-IN-TanishaaNeural", "gu-IN": "gu-IN-DhwaniNeural", "hi-IN": "hi-IN-SwaraNeural",
    "kn-IN": "kn-IN-SapnaNeural", "ml-IN": "ml-IN-SobhanaNeural", "mr-IN": "mr-IN-AarohiNeural",
    "ta-IN": "ta-IN-PallaviNeural", "te-IN": "te-IN-ShrutiNeural", "ur-IN": "ur-IN-GulNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural", "zh-TW": "zh-TW-HsiaoChenNeural", "hr-HR": "hr-HR-GabrijelaNeural",
    "cs-CZ": "cs-CZ-AntoninNeural", "da-DK": "da-DK-ChristelNeural", "nl-BE": "nl-BE-ArnaudNeural",
    "nl-NL": "nl-NL-ColetteNeural", "en-AU": "en-AU-WilliamMultilingualNeural", "en-CA": "en-CA-ClaraNeural",
    "en-HK": "en-HK-YanNeural", "en-IN": "en-IN-NeerjaExpressiveNeural", "en-IE": "en-IE-ConnorNeural",
    "en-KE": "en-KE-AsiliaNeural", "en-NZ": "en-NZ-MitchellNeural", "en-NG": "en-NG-AbeoNeural",
    "en-PH": "en-PH-JamesNeural", "en-US": "en-US-EmmaMultilingualNeural", "en-SG": "en-SG-LunaNeural",
    "en-ZA": "en-ZA-LeahNeural", "en-TZ": "en-TZ-ElimuNeural", "en-GB": "en-GB-LibbyNeural",
    "et-EE": "et-EE-AnuNeural", "fil-PH": "fil-PH-AngeloNeural", "fi-FI": "fi-FI-HarriNeural",
    "fr-BE": "fr-BE-CharlineNeural", "fr-CA": "fr-CA-ThierryNeural", "fr-FR": "fr-FR-RemyMultilingualNeural",
    "fr-CH": "fr-CH-ArianeNeural", "gl-ES": "gl-ES-RoiNeural", "ka-GE": "ka-GE-EkaNeural",
    "de-AT": "de-AT-IngridNeural", "de-DE": "de-DE-FlorianMultilingualNeural", "de-CH": "de-CH-JanNeural",
    "el-GR": "el-GR-AthinaNeural", "gu-IN": "gu-IN-DhwaniNeural", "he-IL": "he-IL-AvriNeural",
    "hi-IN": "hi-IN-MadhurNeural", "hu-HU": "hu-HU-NoemiNeural", "is-IS": "is-IS-GudrunNeural",
    "id-ID": "id-ID-ArdiNeural", "ga-IE": "ga-IE-ColmNeural", "it-IT": "it-IT-GiuseppeMultilingualNeural",
    "ja-JP": "ja-JP-KeitaNeural", "jv-ID": "jv-ID-DimasNeural", "kn-IN": "kn-IN-GaganNeural",
    "kk-KZ": "kk-KZ-AigulNeural", "km-KH": "km-KH-PisethNeural", "ko-KR": "ko-KR-HyunsuMultilingualNeural",
    "lo-LA": "lo-LA-ChanthavongNeural", "lv-LV": "lv-LV-EveritaNeural", "lt-LT": "lt-LT-LeonasNeural",
    "mk-MK": "mk-MK-AleksandarNeural", "ms-MY": "ms-MY-OsmanNeural", "ml-IN": "ml-IN-MidhunNeural",
    "mt-MT": "mt-MT-GraceNeural", "mr-IN": "mr-IN-AarohiNeural", "mn-MN": "mn-MN-BataaNeural",
    "ne-NP": "ne-NP-HemkalaNeural", "nb-NO": "nb-NO-FinnNeural", "ps-AF": "ps-AF-GulNawazNeural",
    "fa-IR": "fa-IR-DilaraNeural", "pl-PL": "pl-PL-MarekNeural", "pt-BR": "pt-BR-ThalitaMultilingualNeural",
    "pt-PT": "pt-PT-DuarteNeural", "ro-RO": "ro-RO-AlinaNeural", "ru-RU": "ru-RU-DmitryNeural",
    "sr-RS": "sr-RS-NicholasNeural", "si-LK": "si-LK-SameeraNeural", "sk-SK": "sk-SK-LukasNeural",
    "sl-SI": "sl-SI-PetraNeural", "so-SO": "so-SO-MuuseNeural", "es-AR": "es-AR-ElenaNeural",
    "es-MX": "es-MX-DaliaNeural", "es-ES": "es-ES-XimenaNeural", "sv-SE": "sv-SE-MattiasNeural",
    "ta-IN": "ta-IN-PallaviNeural", "te-IN": "te-IN-MohanNeural", "th-TH": "th-TH-NiwatNeural",
    "tr-TR": "tr-TR-EmelNeural", "uk-UA": "uk-UA-OstapNeural", "ur-IN": "ur-IN-GulNeural",
    "vi-VN": "vi-VN-HoaiMyNeural", "zu-ZA": "zu-ZA-ThandoNeural"
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
SERVER_STARTED_AT = time.time()
ENV_PATH = Path(PROJECT_DIR) / ".env"


class SettingKeyPayload(BaseModel):
    key_name: str
    key_value: str


class PreferencePayload(BaseModel):
    user_name: str = ""
    honorific: str = "sir"
    calendar_accounts: str = "auto"


class KeyTestPayload(BaseModel):
    key_value: str | None = None


def _read_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _write_env_value(key: str, value: str) -> None:
    lines = _read_env_lines()
    new_line = f"{key}={value}"
    replaced = False
    updated_lines: list[str] = []

    for line in lines:
        if line.startswith(f"{key}="):
            updated_lines.append(new_line)
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(new_line)

    ENV_PATH.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def _count_memory_entries() -> int:
    try:
        return len(recall("jarvis memory preference note task project", limit=100))
    except Exception:
        return 0


def _count_open_tasks() -> int:
    try:
        return len(get_open_tasks())
    except Exception:
        return 0


def _settings_status_payload() -> dict:
    return {
        "claude_code_installed": shutil.which("claude") is not None,
        "calendar_accessible": sys.platform == "darwin",
        "mail_accessible": sys.platform == "darwin",
        "notes_accessible": sys.platform == "darwin",
        "memory_count": _count_memory_entries(),
        "task_count": _count_open_tasks(),
        "server_port": int(os.getenv("PORT", "8340")),
        "uptime_seconds": max(0, int(time.time() - SERVER_STARTED_AT)),
        "env_keys_set": {
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "fish_audio": bool(os.getenv("FISH_API_KEY")),
            "fish_voice_id": bool(os.getenv("FISH_VOICE_ID")),
            "user_name": os.getenv("USER_NAME", ""),
        },
        "assistant": {
            "name": ASSISTANT_NAME,
            "llm_provider": LLM_PROVIDER,
            "tts_provider": TTS_PROVIDER,
        },
    }


def _build_runtime_context() -> dict[str, str]:
    access = get_desktop_access_status()
    desktop_context = (
        "Full Windows desktop control is available."
        if access.get("ok")
        else f"Desktop control is limited: {access.get('message', 'Unavailable')}"
    )
    return {
        "weather_info": "Weather data unavailable",
        "screen_context": desktop_context,
        "calendar_context": "Calendar unavailable on Windows",
        "mail_context": "Mail unavailable on Windows",
    }


def apply_speech_corrections(text: str) -> str:
    """Normalize common speech-to-text errors for command routing."""
    corrected = text.strip()
    corrected = re.sub(r"\s+", " ", corrected)
    corrected = re.sub(r"[.?!]+$", "", corrected)

    replacements = {
        r"^\s*hello\s+(jarvis|service|travis|java|javis)\b": r"jarvis",
        r"^\s*hello\s+(aura|ora)\b": r"aura",
        r"^\s*(hey|hi|okay|ok)\s+(jarvis|service|travis|java|javis)\b": r"jarvis",
        r"^\s*(hey|hi|okay|ok)\s+(aura|ora)\b": r"aura",
        r"\bservice\b": "jarvis",
        r"\btravis\b": "jarvis",
        r"\bjavis\b": "jarvis",
        r"\bjava is\b": "jarvis",
        r"\bjarviss\b": "jarvis",
        r"\bora\b": "aura",
        r"\bcloud code\b": "claude code",
        r"\bclock code\b": "claude code",
        r"\bclawed code\b": "claude code",
        r"\bplot code\b": "claude code",
        r"\bnote pad\b": "notepad",
        r"\bpower shell\b": "powershell",
        r"\bpower sell\b": "powershell",
        r"\bcontrol\b": "ctrl",
        r"\bnew line\b": "",
        r"\bfull stop\b": "",
    }
    for pattern, replacement in replacements.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)

    corrected = re.sub(r"\s+", " ", corrected).strip(" ,:-")
    return corrected


def extract_wake_command(text: str) -> str | None:
    """Return the command after an explicit wake word, or None."""
    match = re.match(r"^\s*(?:hello|hey|hi|ok|okay)?\s*(jarvis|aura)\b[\s,:-]*(.+)$", text, re.IGNORECASE)
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
        runtime_context = _build_runtime_context()
        
        system = JARVIS_SYSTEM_PROMPT.format(
            assistant_name=ASSISTANT_NAME,
            user_name=USER_NAME,
            current_time=current_time,
            weather_info=runtime_context["weather_info"],
            project_dir=PROJECT_DIR,
            screen_context=runtime_context["screen_context"],
            calendar_context=runtime_context["calendar_context"],
            mail_context=runtime_context["mail_context"],
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

def resolve_voice_for_language(voice_or_lang: str | None) -> str:
    if not voice_or_lang:
        return EDGE_VOICE
    
    # If it's a language code, map it
    if voice_or_lang in LANGUAGE_VOICE_MAP:
        return LANGUAGE_VOICE_MAP[voice_or_lang]
    
    # If it's already a full Edge voice ID or 'fish-audio', return as is
    if "Neural" in voice_or_lang or voice_or_lang == "fish-audio":
        return voice_or_lang
        
    return EDGE_VOICE


async def synthesize_speech(text: str, voice: str | None = None) -> Optional[bytes]:
    if not text: return None
    
    # Determine provider and voice
    provider = TTS_PROVIDER
    target_voice = voice or EDGE_VOICE
    
    # If voice is specifically set to 'fish-audio', override provider
    if target_voice == "fish-audio":
        provider = "fish"
    
    # --- Fish Audio Path ---
    if provider == "fish":
        fish_key = os.getenv("FISH_API_KEY")
        voice_id = os.getenv("FISH_VOICE_ID", "7efa380916694064a347395034d6932b") # Default: Matthew
        
        if fish_key:
            try:
                log.info(f"Synthesizing with Fish Audio (voice={voice_id})")
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.fish.audio/v1/tts",
                        headers={
                            "Authorization": f"Bearer {fish_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "text": text,
                            "reference_id": voice_id,
                            "format": "mp3",
                            "latency": "normal"
                        },
                        timeout=15.0
                    )
                    if response.status_code == 200:
                        return response.content
                    else:
                        log.error(f"Fish Audio API error ({response.status_code}): {response.text}")
            except Exception as e:
                log.error(f"Fish Audio synthesis failed: {e}")
        else:
            log.warning("Fish Audio requested but FISH_API_KEY is missing. Falling back to Edge.")

    # --- Edge TTS Path (Default / Fallback) ---
    try:
        # If we came here from Fish fallback, use default voice
        if target_voice == "fish-audio":
            target_voice = EDGE_VOICE
            
        import edge_tts
        communicate = edge_tts.Communicate(text, target_voice)
        audio_bytes = b""
        async with asyncio.timeout(10.0): # 10 second timeout for TTS
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
        return audio_bytes if audio_bytes else None
    except Exception as e:
        log.error(f"TTS error: {e}")
        # Final fallback to base default if specific voice failed
        if target_voice != EDGE_VOICE:
            try:
                communicate = edge_tts.Communicate(text, EDGE_VOICE)
                audio_bytes = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes += chunk["data"]
                return audio_bytes
            except: pass
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


@app.get("/api/settings/status")
async def settings_status():
    return _settings_status_payload()


@app.get("/api/settings/preferences")
async def settings_preferences():
    return {
        "user_name": os.getenv("USER_NAME", ""),
        "honorific": os.getenv("HONORIFIC", "sir"),
        "calendar_accounts": os.getenv("CALENDAR_ACCOUNTS", "auto"),
    }


@app.post("/api/settings/preferences")
async def save_settings_preferences(payload: PreferencePayload):
    _write_env_value("USER_NAME", payload.user_name)
    _write_env_value("HONORIFIC", payload.honorific)
    _write_env_value("CALENDAR_ACCOUNTS", payload.calendar_accounts or "auto")
    return {"saved": True}


@app.post("/api/settings/keys")
async def save_settings_key(payload: SettingKeyPayload):
    _write_env_value(payload.key_name, payload.key_value)
    return {"saved": True, "key_name": payload.key_name}


@app.post("/api/settings/test-anthropic")
async def test_anthropic_key(payload: KeyTestPayload):
    key = (payload.key_value or os.getenv("ANTHROPIC_API_KEY", "")).strip()
    valid = key.startswith("sk-ant-") and len(key) > 20
    return {"valid": valid, "error": None if valid else "Anthropic key format looks invalid."}


@app.post("/api/settings/test-fish")
async def test_fish_key(payload: KeyTestPayload):
    key = (payload.key_value or os.getenv("FISH_API_KEY", "")).strip()
    valid = len(key) >= 20
    return {"valid": valid, "error": None if valid else "Fish key format looks invalid."}


@app.post("/api/restart")
async def restart_server():
    return {
        "ok": True,
        "message": "Restart request acknowledged. If you started the server manually, restart that terminal process.",
    }

@app.websocket("/ws/voice")
async def voice_handler(ws: WebSocket):
    await ws.accept()
    log.info("Voice WebSocket connected")
    history = []
    session_language = "en-IN"
    session_voice = resolve_voice_for_language(session_language)

    await ws.send_json({"type": "access_status", "status": get_desktop_access_status()})
    
    # Periodic Mobile Status Update
    async def update_mobile_status():
        while True:
            try:
                mobile_controller.connect() # Try to connect
                status = mobile_controller.get_status()
                await ws.send_json({"type": "mobile_status", "status": status})
            except Exception:
                pass
            await asyncio.sleep(5)

    mobile_task = asyncio.create_task(update_mobile_status())
    
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
                    action_text = extract_wake_command(user_text) or user_text

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
                    runtime_context = _build_runtime_context()
                    system = JARVIS_SYSTEM_PROMPT.format(
                        assistant_name=ASSISTANT_NAME,
                        user_name=USER_NAME,
                        current_time=current_time,
                        weather_info=runtime_context["weather_info"],
                        project_dir=PROJECT_DIR,
                        screen_context=runtime_context["screen_context"],
                        calendar_context=runtime_context["calendar_context"],
                        mail_context=runtime_context["mail_context"],
                        active_tasks="[]",
                        dispatch_context="",
                        known_projects=""
                    )

                    async for chunk in brain.stream_think(user_text, history[:-1], system_prompt=system):
                        full_text += chunk
                        sentence_buffer += chunk
                        
                        # Detect sentence boundaries OR meaningful pauses to generate audio chunks faster
                        if any(term in sentence_buffer for term in [". ", "! ", "? ", "\n", ", ", "; "]):
                            # Split buffer into segments
                            parts = re.split(r'(?<=[.!?\n,;]) ', sentence_buffer)
                            for i in range(len(parts) - 1):
                                segment = parts[i].strip()
                                # Only speak if the segment is long enough to be meaningful (at least 3 words or ends in punctuation)
                                if len(segment.split()) >= 3 or (segment and segment[-1] in ".!?"):
                                    await ws.send_json({"type": "status", "state": "speaking"})
                                    tts_part = strip_markdown_for_tts(segment)
                                    audio_part = await synthesize_speech(tts_part, session_voice)
                                    if audio_part:
                                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio_part).decode(), "text": segment})
                            
                            if len(parts) > 1:
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
        mobile_task.cancel()


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
