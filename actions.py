"""
JARVIS Action Executor — AppleScript-based system actions.

Execute actions IMMEDIATELY, before generating any LLM response.
Each function returns {"success": bool, "confirmation": str}.
"""

import asyncio
import logging
import os
import re
import time
import sys
import webbrowser
import subprocess
from pathlib import Path
from urllib.parse import quote

try:
    import pyautogui
except ImportError:
    pyautogui = None

# Import Windows automation if on Windows
if sys.platform == "win32":
    try:
        from windows_automation import (
            run_powershell, run_cmd_command, copy_file, move_file, delete_file,
            list_files, create_file, read_file_content, search_files,
            get_system_info, set_volume, lock_screen, shutdown_system,
            hibernate_system, sleep_system, list_processes, kill_process,
            launch_application, set_environment_variable, get_environment_variable,
            get_network_info, test_connectivity
        )
        WINDOWS_AUTOMATION_AVAILABLE = True
    except ImportError:
        WINDOWS_AUTOMATION_AVAILABLE = False
else:
    WINDOWS_AUTOMATION_AVAILABLE = False

log = logging.getLogger("jarvis.actions")
CLOUD_DEPLOYMENT = os.getenv("JARVIS_DEPLOYMENT_MODE", "").lower() == "cloud"

DESKTOP_PATH = Path.home() / "Desktop"
APP_ALIASES = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "powershell.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "spotify": "spotify.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
}

if pyautogui is not None:
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05


def desktop_automation_ready() -> bool:
    return not CLOUD_DEPLOYMENT and pyautogui is not None


async def _mark_terminal_as_jarvis(revert_after: float = 5.0):
    """Temporarily set the front Terminal window to Ocean theme, then revert.

    Shows the user JARVIS is active in that terminal. Reverts after revert_after seconds.
    """
    # Save the current profile, switch to Ocean, then revert
    script_save = (
        'tell application "Terminal"\n'
        '    return name of current settings of front window\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_save,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        original_profile = stdout.decode().strip()

        # Switch to Ocean
        script_set = (
            'tell application "Terminal"\n'
            '    set current settings of front window to settings set "Ocean"\n'
            'end tell'
        )
        proc2 = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_set,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        # Schedule revert
        if original_profile and original_profile != "Ocean":
            asyncio.get_event_loop().call_later(
                revert_after,
                lambda: asyncio.ensure_future(_revert_terminal_theme(original_profile))
            )
    except Exception:
        pass


async def _revert_terminal_theme(profile_name: str):
    """Revert a Terminal window back to its original profile."""
    escaped = profile_name.replace('"', '\\"')
    script = (
        'tell application "Terminal"\n'
        f'    set current settings of front window to settings set "{escaped}"\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception:
        pass


async def open_terminal(command: str = "") -> dict:
    """Open Terminal/PowerShell and optionally run a command."""
    try:
        if sys.platform == "win32":
            if command:
                # Use 'start' to launch a new window with the command
                # We use cmd /k to keep it open after the command runs
                subprocess.Popen(["cmd", "/c", f"start cmd /k {command}"], shell=True)
            else:
                subprocess.Popen(["start", "powershell"], shell=True)
        elif sys.platform == "darwin":
            escaped = command.replace('"', '\\"') if command else ""
            script = (
                'tell application "Terminal"\n'
                "    activate\n"
                f'    {"do script " + chr(34) + escaped + chr(34) if command else ""}\n'
                "end tell"
            )
            await asyncio.create_subprocess_exec("osascript", "-e", script)
        else:
            # Linux (fallback to x-terminal-emulator)
            subprocess.Popen(["x-terminal-emulator", "-e", command] if command else ["x-terminal-emulator"])
        
        success = True
    except Exception as e:
        log.error(f"open_terminal failed: {e}")
        success = False

    return {
        "success": success,
        "confirmation": "Terminal is open, sir." if success else "I had trouble opening Terminal, sir.",
    }


async def open_browser(url: str, browser: str = "chrome") -> dict:
    """Open URL in user's browser."""
    try:
        # Use Python's built-in webbrowser module for cross-platform support
        webbrowser.open(url)
        success = True
        app_name = "your browser"
    except Exception as e:
        log.error(f"open_browser failed: {e}")
        success = False
        app_name = "the browser"

    return {
        "success": success,
        "confirmation": f"Pulled that up in {app_name}, sir." if success else f"{app_name} ran into a problem, sir.",
    }


# Keep backward compat
async def open_chrome(url: str) -> dict:
    return await open_browser(url, "chrome")


async def open_claude_in_project(project_dir: str, prompt: str) -> dict:
    """Open Terminal, cd to project dir, run Claude Code interactively."""
    # Write prompt to CLAUDE.md — claude reads this automatically
    claude_md = Path(project_dir) / "CLAUDE.md"
    claude_md.write_text(f"# Task\n\n{prompt}\n\nBuild this completely. If web app, make index.html work standalone.\n")

    try:
        if sys.platform == "win32":
            # On Windows, we open cmd, cd to dir, and run claude
            cmd = f'cd /d "{project_dir}" && claude --dangerously-skip-permissions'
            subprocess.Popen(["cmd", "/c", f"start cmd /k {cmd}"], shell=True)
        elif sys.platform == "darwin":
            script = (
                'tell application "Terminal"\n'
                "    activate\n"
                f'    do script "cd {project_dir} && claude --dangerously-skip-permissions"\n'
                "end tell"
            )
            await asyncio.create_subprocess_exec("osascript", "-e", script)
        else:
            # Linux fallback
            subprocess.Popen(["x-terminal-emulator", "-e", f"bash -c 'cd {project_dir} && claude --dangerously-skip-permissions'"])
        
        success = True
    except Exception as e:
        log.error(f"open_claude_in_project failed: {e}")
        success = False

    return {
        "success": success,
        "confirmation": "Claude Code is running in Terminal, sir. You can watch the progress."
        if success
        else "Had trouble spawning Claude Code, sir.",
    }


async def prompt_existing_terminal(project_name: str, prompt: str) -> dict:
    """Find a Terminal window matching a project name and type a prompt into it.

    Uses System Events keystroke to type into an active Claude Code session
    rather than `do script` which would open a new shell.
    """
    escaped_name = project_name.replace('"', '\\"')
    escaped_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"')

    # Single atomic script: find window, focus it, type into it
    script = f'''
tell application "Terminal"
    set matched to false
    set targetWindow to missing value
    repeat with w in windows
        if name of w contains "{escaped_name}" then
            set targetWindow to w
            set matched to true
            exit repeat
        end if
    end repeat

    if not matched then
        return "NOT_FOUND"
    end if

    -- Bring the matched window to front
    set index of targetWindow to 1
    set selected tab of targetWindow to selected tab of targetWindow
    activate
end tell

-- Wait for window to be fully focused
delay 1

-- Now type into it
tell application "System Events"
    tell process "Terminal"
        set frontmost to true
        delay 0.3
        keystroke "{escaped_prompt}"
        delay 0.2
        keystroke return
    end tell
end tell

return "OK"
'''

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)

        result = stdout.decode().strip()
        if result == "NOT_FOUND":
            return {
                "success": False,
                "confirmation": f"Couldn't find a terminal for {project_name}, sir.",
            }

        success = proc.returncode == 0
        if not success:
            log.error(f"prompt_existing_terminal failed: {stderr.decode()[:200]}")

        if success:
            await _mark_terminal_as_jarvis()

        return {
            "success": success,
            "confirmation": f"Sent that to {project_name}, sir." if success
            else f"Had trouble typing into {project_name}, sir.",
        }

    except asyncio.TimeoutError:
        return {"success": False, "confirmation": "Terminal operation timed out, sir."}
    except Exception as e:
        log.error(f"prompt_existing_terminal failed: {e}")
        return {"success": False, "confirmation": "Something went wrong reaching that terminal, sir."}


async def get_chrome_tab_info() -> dict:
    """Read the current browser tab's title and URL. (Limited on Windows)"""
    # This is extremely difficult to do cross-platform without specialized tools
    # like accessibility APIs. For now, we return empty on non-macOS.
    if sys.platform != "darwin":
        return {}

    script = (
        'tell application "Google Chrome"\n'
        "    set tabTitle to title of active tab of front window\n"
        "    set tabURL to URL of active tab of front window\n"
        '    return tabTitle & "|" & tabURL\n'
        "end tell"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            result = stdout.decode().strip()
            parts = result.split("|", 1)
            if len(parts) == 2:
                return {"title": parts[0], "url": parts[1]}
        return {}
    except Exception as e:
        log.warning(f"get_chrome_tab_info failed: {e}")
        return {}


def _clean_target_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" .!?\"'")).strip()


def _strip_leading_filler(text: str) -> str:
    text = re.sub(r"^(please|jarvis|aura|can you|could you|would you|for me)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_key_name(key: str) -> str:
    key = key.lower().strip()
    replacements = {
        "control": "ctrl",
        "escape": "esc",
        "return": "enter",
        "windows": "win",
        "spacebar": "space",
    }
    return replacements.get(key, key)


def _normalize_hotkey_text(text: str) -> list[str]:
    raw_keys = re.split(r"\s*\+\s*|\s+then\s+|\s+and\s+", text.lower().strip())
    keys = [_normalize_key_name(key) for key in raw_keys if key.strip()]
    return keys


def _looks_like_url_or_path(target: str) -> bool:
    return (
        target.startswith(("http://", "https://"))
        or "\\" in target
        or "/" in target
        or ":" in target
        or target.lower().endswith((".txt", ".docx", ".xlsx", ".pdf", ".png", ".jpg"))
    )


def get_desktop_access_status() -> dict:
    """Check whether desktop automation dependencies appear usable."""
    if CLOUD_DEPLOYMENT:
        return {
            "ok": False,
            "platform": sys.platform,
            "checks": {"deployment": {"ok": False, "mode": "cloud"}},
            "issues": ["Desktop control is disabled in cloud deployment."],
            "message": "Cloud mode is online, but desktop control is unavailable there.",
        }

    status = {
        "ok": True,
        "platform": sys.platform,
        "checks": {},
        "issues": [],
    }

    if pyautogui is None:
        status["ok"] = False
        status["checks"]["screen"] = {"ok": False, "error": "PyAutoGUI is not installed."}
        status["issues"].append("PyAutoGUI is not installed.")
    else:
        try:
            size = pyautogui.size()
            status["checks"]["screen"] = {"ok": size.width > 0 and size.height > 0, "value": [size.width, size.height]}
            if size.width <= 0 or size.height <= 0:
                status["ok"] = False
                status["issues"].append("Screen automation is not available.")
        except Exception as e:
            status["ok"] = False
            status["checks"]["screen"] = {"ok": False, "error": str(e)}
            status["issues"].append(f"PyAutoGUI screen access failed: {e}")

    try:
        import pygetwindow as gw
        titles = [title for title in gw.getAllTitles() if title.strip()]
        status["checks"]["windows"] = {"ok": True, "count": len(titles)}
    except Exception as e:
        status["ok"] = False
        status["checks"]["windows"] = {"ok": False, "error": str(e)}
        status["issues"].append(f"Window automation failed: {e}")

    try:
        _ = APP_ALIASES.get("notepad")
        status["checks"]["launch"] = {"ok": True}
    except Exception as e:
        status["ok"] = False
        status["checks"]["launch"] = {"ok": False, "error": str(e)}
        status["issues"].append(f"App launch setup failed: {e}")

    status["message"] = (
        "Desktop control is ready."
        if status["ok"]
        else "Desktop control is limited. Check the reported issues."
    )
    return status


async def focus_window(target: str) -> dict:
    """Focus a window by exact or partial title match on Windows."""
    try:
        import pygetwindow as gw

        target = target.strip()
        windows = gw.getWindowsWithTitle(target)
        if not windows:
            windows = [w for w in gw.getAllWindows() if w.title and target.lower() in w.title.lower()]
        if not windows:
            return {"success": False, "confirmation": f"I couldn't find a window matching {target}."}

        win = windows[0]
        if win.isMinimized:
            win.restore()
            time.sleep(0.2)
        win.activate()
        return {"success": True, "confirmation": f"Focused {win.title}."}
    except Exception as e:
        log.error(f"focus_window failed: {e}")
        return {"success": False, "confirmation": f"Failed to focus {target}."}


async def save_active_app(target: str = "") -> dict:
    """Save the active document. If a filename is provided, attempt Save As flow."""
    if not desktop_automation_ready():
        return {"success": False, "confirmation": "Desktop save actions are only available on your local Windows app."}

    try:
        destination = _clean_target_text(target)
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.5)

        if destination:
            if not _looks_like_url_or_path(destination):
                destination = str(DESKTOP_PATH / destination)
            pyautogui.write(destination, interval=0.01)
            time.sleep(0.2)
            pyautogui.press("enter")
            time.sleep(0.5)
            return {"success": True, "confirmation": f"Saved it as {Path(destination).name}."}

        return {"success": True, "confirmation": "Saved the active document."}
    except Exception as e:
        log.error(f"save_active_app failed: {e}")
        return {"success": False, "confirmation": "Failed to save the active document."}


def _resolve_open_target(target: str) -> str:
    target = target.strip()
    alias = APP_ALIASES.get(target.lower(), target)
    return alias


async def open_visible_target(target: str) -> dict:
    """Open an app, file, or URL on Windows with a few fallbacks."""
    try:
        open_target = _resolve_open_target(target)
        lowered = open_target.lower()

        if sys.platform == "win32":
            if lowered.startswith(("http://", "https://")):
                os.startfile(open_target)
            elif Path(open_target).exists() or lowered.endswith((".exe", ".lnk", ".bat", ".cmd", ".ps1")):
                # Direct executable or shortcut path
                try:
                    subprocess.Popen([open_target])
                except Exception:
                    subprocess.Popen(f'start "" "{open_target}"', shell=True)
            else:
                # Use Windows shell start for app names and registered apps
                try:
                    subprocess.Popen(f'start "" "{open_target}"', shell=True)
                except Exception:
                    subprocess.Popen(
                        f'powershell -NoProfile -Command Start-Process "{open_target}"',
                        shell=True,
                    )
        else:
            subprocess.Popen(f'start "" "{open_target}"', shell=True)

        return {"success": True, "confirmation": f"Opening {target} on your screen right now."}
    except Exception as e:
        log.error(f"open_visible_target failed: {e}")
        return {"success": False, "confirmation": f"Failed to open {target}: {e}"}


def parse_desktop_command(text: str) -> dict | None:
    """Convert direct desktop-control language into an action dict."""
    original = _clean_target_text(text)
    lowered = _strip_leading_filler(original.lower())

    if not lowered:
        return None

    if lowered in {"check access", "check laptop access", "check desktop access", "jarvis access status"}:
        return {"action": "access_status", "target": ""}

    open_match = re.match(r"^(?:open|launch|start|run)\s+(.+)$", lowered)
    if open_match:
        target = _clean_target_text(open_match.group(1))
        return {"action": "open", "target": target}

    focus_match = re.match(r"^(?:focus|switch to|activate)\s+(.+)$", lowered)
    if focus_match:
        return {"action": "focus", "target": _clean_target_text(focus_match.group(1))}

    write_match = re.match(r"^(?:write|type)\s+(.+?)(?:\s+(?:in|into|on)\s+.+)?$", lowered)
    if write_match:
        return {"action": "type", "target": write_match.group(1).strip()}

    save_as_match = re.match(r"^(?:save|save it|save this|save file|save document)\s+(?:as|to)\s+(.+)$", lowered)
    if save_as_match:
        return {"action": "save", "target": _clean_target_text(save_as_match.group(1))}

    if lowered in {"save", "save it", "save this", "save file", "save document"}:
        return {"action": "save", "target": ""}

    press_match = re.match(r"^(?:press|hit)\s+(.+)$", lowered)
    if press_match:
        return {"action": "press", "target": press_match.group(1).strip()}

    if lowered in {"click", "click mouse"}:
        return {"action": "click", "target": ""}

    if lowered in {"what apps are open", "what windows are open", "list windows", "show windows"}:
        return {"action": "windows", "target": ""}

    close_match = re.match(r"^(?:close|exit)\s+(.+)$", lowered)
    if close_match:
        return {"action": "close", "target": _clean_target_text(close_match.group(1))}

    min_match = re.match(r"^minimi[sz]e\s+(.+)$", lowered)
    if min_match:
        return {"action": "minimize", "target": _clean_target_text(min_match.group(1))}

    max_match = re.match(r"^maximi[sz]e\s+(.+)$", lowered)
    if max_match:
        return {"action": "maximize", "target": _clean_target_text(max_match.group(1))}

    # ============= Windows-Specific Commands =============
    
    # PowerShell & CMD
    if lowered.startswith("powershell "):
        cmd = lowered[11:].strip()
        return {"action": "powershell", "target": cmd}
    
    if lowered.startswith("cmd "):
        cmd = lowered[4:].strip()
        return {"action": "cmd", "target": cmd}
    
    # ============= Process Management (check BEFORE file operations) =============
    if re.match(r"^(?:list|show)\s+processes", lowered) or lowered in {"processes", "ps", "tasklist", "running apps", "open apps"}:
        if re.match(r"^(?:list|show)\s+processes\s+(?:for\s+)(.+)$", lowered):
            process_match = re.match(r"^(?:list|show)\s+processes\s+(?:for\s+)(.+)$", lowered)
            return {"action": "process_list", "target": process_match.group(1)}
        return {"action": "process_list", "target": ""}
    
    kill_match = re.match(r"^(?:kill|close|terminate)\s+(?:process\s+)?(.+)$", lowered)
    if kill_match and "file" not in lowered:
        return {"action": "process_kill", "target": kill_match.group(1)}
    
    # ============= File Operations =============
    # File Operations
    file_copy_match = re.match(r"^(?:copy|cp)\s+(.+?)\s+to\s+(.+)$", lowered)
    if file_copy_match:
        return {"action": "file_copy", "target": f"{file_copy_match.group(1)} to {file_copy_match.group(2)}"}
    
    file_move_match = re.match(r"^(?:move|mv|rename)\s+(.+?)\s+to\s+(.+)$", lowered)
    if file_move_match:
        return {"action": "file_move", "target": f"{file_move_match.group(1)} to {file_move_match.group(2)}"}
    
    file_delete_match = re.match(r"^(?:delete|del|remove)\s+(?:file\s+)?(.+)$", lowered)
    if file_delete_match:
        return {"action": "file_delete", "target": file_delete_match.group(1)}
    
    if lowered in {"list files", "ls", "show files", "show desktop"}:
        return {"action": "file_list", "target": str(DESKTOP_PATH)}
    
    file_list_match = re.match(r"^(?:list|ls|show)\s+(?:files\s+)?(?:in\s+)?(.+)$", lowered)
    if file_list_match:
        return {"action": "file_list", "target": file_list_match.group(1)}
    
    file_create_match = re.match(r"^(?:create|new)\s+(?:file\s+)?(.+?)(?:\s+with\s+(.+))?$", lowered)
    if file_create_match:
        path = file_create_match.group(1)
        content = file_create_match.group(2) if file_create_match.group(2) else ""
        target = f"{path} with {content}" if content else path
        return {"action": "file_create", "target": target}
    
    file_read_match = re.match(r"^(?:read|cat|view|show)\s+(.+)$", lowered)
    if file_read_match:
        return {"action": "file_read", "target": file_read_match.group(1)}
    
    search_match = re.match(r"^(?:search|find)\s+(?:for\s+)?(.+?)\s+in\s+(.+)$", lowered)
    if search_match:
        return {"action": "file_search", "target": f"{search_match.group(1)} in {search_match.group(2)}"}
    
    # System Control
    if lowered in {"system info", "system information", "sysinfo", "check system"}:
        return {"action": "system_info", "target": ""}
    
    volume_match = re.match(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d+)$", lowered)
    if volume_match:
        return {"action": "set_volume", "target": volume_match.group(1)}
    
    if lowered in {"lock", "lock screen", "lock pc", "lock computer"}:
        return {"action": "lock_screen", "target": ""}
    
    if lowered in {"sleep", "sleep mode", "sleep pc", "go to sleep"}:
        return {"action": "sleep_system", "target": ""}
    
    if lowered in {"shutdown", "shut down", "power off", "turn off"}:
        return {"action": "shutdown", "target": "0"}
    
    shutdown_match = re.match(r"^shutdown\s+in\s+(\d+)\s+(?:seconds|second|secs)$", lowered)
    if shutdown_match:
        return {"action": "shutdown", "target": shutdown_match.group(1)}
    
    if lowered in {"hibernate", "hibernation", "deep sleep"}:
        return {"action": "hibernate", "target": ""}
    
    launch_match = re.match(r"^(?:launch|start|run)\s+app\s+(.+?)(?:\s+with\s+(.+))?$", lowered)
    if launch_match:
        app = launch_match.group(1)
        args = launch_match.group(2) if launch_match.group(2) else ""
        target = f"{app} with {args}" if args else app
        return {"action": "launch_app", "target": target}
    
    # Environment Variables
    env_set_match = re.match(r"^(?:set\s+)?(?:env|environment)\s+(.+?)=(.+)$", lowered)
    if env_set_match:
        return {"action": "set_env", "target": f"{env_set_match.group(1)}={env_set_match.group(2)}"}
    
    env_get_match = re.match(r"^(?:get|show)\s+(?:env|environment)\s+(.+)$", lowered)
    if env_get_match:
        return {"action": "get_env", "target": env_get_match.group(1)}
    
    # Network Operations
    if lowered in {"network", "network info", "network status", "connection"}:
        return {"action": "network_info", "target": ""}
    
    ping_match = re.match(r"^(?:ping|test|check)\s+(?:connection\s+)?(?:to\s+)?(.+)$", lowered)
    if ping_match:
        return {"action": "test_connection", "target": ping_match.group(1)}

    return None


async def monitor_build(project_dir: str, ws=None, synthesize_fn=None) -> None:
    """Monitor a Claude Code build for completion. Notify via WebSocket when done."""
    import base64

    output_file = Path(project_dir) / ".jarvis_output.txt"
    start = time.time()
    timeout = 600  # 10 minutes

    while time.time() - start < timeout:
        await asyncio.sleep(5)
        if output_file.exists():
            content = output_file.read_text()
            if "--- JARVIS TASK COMPLETE ---" in content:
                log.info(f"Build complete in {project_dir}")
                if ws and synthesize_fn:
                    try:
                        msg = "The build is complete, sir."
                        audio_bytes = await synthesize_fn(msg)
                        if audio_bytes:
                            encoded = base64.b64encode(audio_bytes).decode()
                            await ws.send_json({"type": "status", "state": "speaking"})
                            await ws.send_json({"type": "audio", "data": encoded, "text": msg})
                            await ws.send_json({"type": "status", "state": "idle"})
                    except Exception as e:
                        log.warning(f"Build notification failed: {e}")
                return

    log.warning(f"Build timed out in {project_dir}")


# ---------------------------------------------------------------------------
# Automation Actions (pyautogui)
# ---------------------------------------------------------------------------

async def type_text(text: str) -> dict:
    """Type text using pyautogui."""
    if not desktop_automation_ready():
        return {"success": False, "confirmation": "Desktop typing is only available on your local Windows app."}

    try:
        pyautogui.write(text, interval=0.01)
        return {"success": True, "confirmation": f"Typed: {text}"}
    except Exception as e:
        log.error(f"type_text failed: {e}")
        return {"success": False, "confirmation": "Failed to type text."}


async def press_hotkey(*keys: str) -> dict:
    """Press a combination of keys."""
    if not desktop_automation_ready():
        return {"success": False, "confirmation": "Hotkeys are only available on your local Windows app."}

    try:
        normalized = [_normalize_key_name(key) for key in keys if key]
        if len(normalized) == 1:
            pyautogui.press(normalized[0])
        else:
            pyautogui.hotkey(*normalized)
        return {"success": True, "confirmation": f"Pressed {'+'.join(keys)}"}
    except Exception as e:
        log.error(f"press_hotkey failed: {e}")
        return {"success": False, "confirmation": f"Failed to press {'+'.join(keys)}"}


async def move_and_click(x: int = None, y: int = None) -> dict:
    """Move mouse and click."""
    if not desktop_automation_ready():
        return {"success": False, "confirmation": "Mouse control is only available on your local Windows app."}

    try:
        if x is not None and y is not None:
            pyautogui.click(x, y)
        else:
            pyautogui.click()
        return {"success": True, "confirmation": "Clicked."}
    except Exception as e:
        log.error(f"move_and_click failed: {e}")
        return {"success": False, "confirmation": "Failed to click."}


async def screen_shot(name: str = "screenshot.png") -> dict:
    """Take a screenshot."""
    if not desktop_automation_ready():
        return {"success": False, "confirmation": "Desktop screenshots are only available on your local Windows app."}

    try:
        path = DESKTOP_PATH / name
        pyautogui.screenshot(str(path))
        return {"success": True, "confirmation": f"Screenshot saved to Desktop as {name}"}
    except Exception as e:
        log.error(f"screen_shot failed: {e}")
        return {"success": False, "confirmation": "Failed to take screenshot."}


async def execute_action(intent: dict, projects: list = None) -> dict:
    """Route a classified intent to the right action function.

    Args:
        intent: {"action": str, "target": str} from classify_intent()
        projects: list of known project dicts for resolving working dirs

    Returns: {"success": bool, "confirmation": str, "project_dir": str | None}
    """
    action = intent.get("action", "chat")
    target = intent.get("target", "")

    if action == "open_terminal":
        result = await open_terminal("claude --dangerously-skip-permissions")
        result["project_dir"] = None
        return result

    elif action == "browse":
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        else:
            url = f"https://www.google.com/search?q={quote(target)}"

        # Detect which browser user wants
        target_lower = target.lower()
        if "firefox" in target_lower:
            browser = "firefox"
        else:
            browser = "chrome"

        result = await open_browser(url, browser)
        result["project_dir"] = None
        return result

    elif action == "build":
        # Create project folder on Desktop, spawn Claude Code
        project_name = _generate_project_name(target)
        project_dir = str(DESKTOP_PATH / project_name)
        os.makedirs(project_dir, exist_ok=True)
        result = await open_claude_in_project(project_dir, target)
        result["project_dir"] = project_dir
        return result

    elif action == "type":
        return await type_text(target)

    elif action == "press":
        # target could be "ctrl+n", "control s", or "enter"
        keys = _normalize_hotkey_text(target)
        return await press_hotkey(*keys)

    elif action == "click":
        return await move_and_click()

    elif action == "save":
        return await save_active_app(target)

    elif action == "focus":
        return await focus_window(target)

    elif action == "screenshot":
        return await screen_shot(target if target else "jarvis_shot.png")

    elif action == "open":
        return await open_visible_target(target)

    elif action == "access_status":
        status = get_desktop_access_status()
        return {
            "success": status["ok"],
            "confirmation": status["message"] if status["ok"] else " | ".join(status["issues"]),
            "details": status,
        }

    elif action == "windows":
        try:
            import pygetwindow as gw
            titles = [t for t in gw.getAllTitles() if t.strip()]
            return {"success": True, "confirmation": f"Open windows: {', '.join(titles[:15])}"}
        except Exception as e:
            return {"success": False, "confirmation": f"Failed to list windows: {e}"}

    elif action in ["close", "minimize", "maximize"]:
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(target)
            if not windows:
                # Try partial match
                windows = [w for w in gw.getWindowsWithTitle('') if target.lower() in w.title.lower()]
                
            if windows:
                win = windows[0]
                if action == "close": win.close()
                elif action == "minimize": win.minimize()
                elif action == "maximize": win.maximize()
                return {"success": True, "confirmation": f"Action {action} performed on {win.title}"}
            else:
                return {"success": False, "confirmation": f"Could not find window matching {target}"}
        except Exception as e:
            return {"success": False, "confirmation": f"Window action failed: {e}"}

    elif action == "shell":
        # Execute shell command visibly on screen
        import subprocess
        try:
            log.info(f"Executing shell visibly: {target}")
            # This opens a visible command prompt and runs the target command
            subprocess.Popen(f'start cmd /k "{target}"', shell=True)
            return {"success": True, "confirmation": f"I've opened a terminal window on your screen to run that."}
        except Exception as e:
            return {"success": False, "confirmation": f"Command failed: {e}"}

    # ============= Windows-Specific Actions =============
    elif WINDOWS_AUTOMATION_AVAILABLE and action == "powershell":
        result = await run_powershell(target)
        return {
            "success": result["success"],
            "confirmation": result["output"][:200] if result["output"] else ("Command executed." if result["success"] else result["error"][:200])
        }

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "cmd":
        result = await run_cmd_command(target)
        return {
            "success": result["success"],
            "confirmation": result["output"][:200] if result["output"] else ("Command executed." if result["success"] else result["error"][:200])
        }

    # File Operations
    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_copy":
        parts = target.split(" to ")
        if len(parts) == 2:
            result = await copy_file(parts[0].strip(), parts[1].strip())
            return result
        return {"success": False, "confirmation": "Usage: copy <source> to <destination>"}

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_move":
        parts = target.split(" to ")
        if len(parts) == 2:
            result = await move_file(parts[0].strip(), parts[1].strip())
            return result
        return {"success": False, "confirmation": "Usage: move <source> to <destination>"}

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_delete":
        result = await delete_file(target)
        return result

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_list":
        result = await list_files(target if target else str(Path.home() / "Desktop"))
        files_text = ", ".join([f["name"] for f in result["files"][:10]])
        return {
            "success": result["success"],
            "confirmation": files_text if files_text else "No files found.",
            "files": result["files"]
        }

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_create":
        parts = target.split(" with ")
        path = parts[0].strip() if parts else target
        content = parts[1].strip() if len(parts) > 1 else ""
        result = await create_file(path, content)
        return result

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_read":
        result = await read_file_content(target)
        return result

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "file_search":
        parts = target.split(" in ")
        if len(parts) == 2:
            search_term = parts[0].strip()
            directory = parts[1].strip()
        else:
            search_term = target
            directory = str(Path.home())
        result = await search_files(directory, search_term)
        files_text = ", ".join([f["name"] for f in result["files"][:5]])
        return {
            "success": result["success"],
            "confirmation": files_text if files_text else "No matches found.",
            "files": result["files"]
        }

    # System Control
    elif WINDOWS_AUTOMATION_AVAILABLE and action == "system_info":
        result = await get_system_info()
        info_text = "\n".join([f"{k}: {v}" for k, v in result["info"].items()])
        return {
            "success": result["success"],
            "confirmation": info_text[:300] if info_text else "Could not retrieve system info.",
            "info": result["info"]
        }

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "set_volume":
        try:
            level = int(target) if target else 50
            result = await set_volume(level)
            return result
        except ValueError:
            return {"success": False, "confirmation": "Volume level must be a number 0-100."}

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "lock_screen":
        result = await lock_screen()
        return result

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "sleep_system":
        result = await sleep_system()
        return result

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "shutdown":
        try:
            delay = int(target) if target else 0
            result = await shutdown_system(delay)
            return result
        except ValueError:
            return {"success": False, "confirmation": "Delay must be in seconds."}

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "hibernate":
        result = await hibernate_system()
        return result

    # Process Management
    elif WINDOWS_AUTOMATION_AVAILABLE and action == "process_list":
        result = await list_processes(target)
        processes_text = "\n".join(result["processes"][:10])
        return {
            "success": result["success"],
            "confirmation": processes_text if processes_text else "No processes found.",
            "processes": result["processes"]
        }

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "process_kill":
        result = await kill_process(target)
        return result

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "launch_app":
        parts = target.split(" with ")
        app = parts[0].strip()
        args = parts[1].strip() if len(parts) > 1 else ""
        result = await launch_application(app, args)
        return result

    # Environment Variables
    elif WINDOWS_AUTOMATION_AVAILABLE and action == "set_env":
        parts = target.split("=")
        if len(parts) == 2:
            result = await set_environment_variable(parts[0].strip(), parts[1].strip())
            return result
        return {"success": False, "confirmation": "Usage: set_env NAME=value"}

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "get_env":
        result = await get_environment_variable(target)
        return result

    # Network Operations
    elif WINDOWS_AUTOMATION_AVAILABLE and action == "network_info":
        result = await get_network_info()
        return {
            "success": result["success"],
            "confirmation": result["info"][:300] if result["info"] else "Could not retrieve network info.",
            "info": result["info"]
        }

    elif WINDOWS_AUTOMATION_AVAILABLE and action == "test_connection":
        host = target if target else "8.8.8.8"
        result = await test_connectivity(host)
        return result

    else:
        return {"success": False, "confirmation": "", "project_dir": None}



def _generate_project_name(prompt: str) -> str:
    """Generate a kebab-case project folder name from the prompt."""
    # First: check for a quoted name like "tiktok-analytics-dashboard"
    quoted = re.search(r'"([^"]+)"', prompt)
    if quoted:
        name = quoted.group(1).strip()
        # Already kebab-case or close to it
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip()
        if name:
            return re.sub(r"[\s]+", "-", name.lower())

    # Second: check for "called X" or "named X" pattern
    called = re.search(r'(?:called|named)\s+(\S+(?:[-_]\S+)*)', prompt, re.IGNORECASE)
    if called:
        name = re.sub(r"[^a-zA-Z0-9-]", "", called.group(1))
        if len(name) > 3:
            return name.lower()

    # Fallback: extract meaningful words
    words = re.sub(r"[^a-zA-Z0-9\s]", "", prompt.lower()).split()
    skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and",
            "to", "of", "i", "want", "need", "new", "project", "directory", "called",
            "on", "desktop", "that", "application", "app", "full", "stack", "simple",
            "web", "page", "site", "named"}
    meaningful = [w for w in words if w not in skip and len(w) > 2][:4]
    return "-".join(meaningful) if meaningful else "jarvis-project"
