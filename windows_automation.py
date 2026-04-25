"""
Windows System Automation — Enhanced automation for JARVIS on Windows.
Provides file operations, system control, PowerShell integration, and process management.
"""

import asyncio
import logging
import subprocess
import sys
import os
import time
import shutil
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

log = logging.getLogger("jarvis.windows")

# =============================================================================
# PowerShell Execution
# =============================================================================

async def run_powershell(script: str, capture_output: bool = True) -> Dict:
    """
    Execute a PowerShell script safely.
    
    Args:
        script: PowerShell code to execute
        capture_output: Whether to capture stdout/stderr
        
    Returns: {"success": bool, "output": str, "error": str}
    """
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command", script
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        
        output = stdout.decode().strip() if stdout else ""
        error = stderr.decode().strip() if stderr else ""
        
        return {
            "success": proc.returncode == 0,
            "output": output,
            "error": error,
            "returncode": proc.returncode
        }
    except asyncio.TimeoutError:
        return {"success": False, "output": "", "error": "PowerShell command timed out"}
    except Exception as e:
        log.error(f"PowerShell execution failed: {e}")
        return {"success": False, "output": "", "error": str(e)}


async def run_cmd_command(command: str, capture_output: bool = True) -> Dict:
    """Execute a CMD command."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "cmd", "/c", command,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        
        output = stdout.decode().strip() if stdout else ""
        error = stderr.decode().strip() if stderr else ""
        
        return {
            "success": proc.returncode == 0,
            "output": output,
            "error": error,
        }
    except asyncio.TimeoutError:
        return {"success": False, "output": "", "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


# =============================================================================
# File Operations
# =============================================================================

async def copy_file(source: str, destination: str) -> Dict:
    """Copy a file or folder."""
    try:
        source_path = Path(source).expanduser()
        dest_path = Path(destination).expanduser()
        
        if not source_path.exists():
            return {"success": False, "confirmation": f"Source '{source}' not found."}
        
        if source_path.is_file():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            action = "file"
        else:
            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            action = "folder"
        
        return {
            "success": True,
            "confirmation": f"Copied {action} to {dest_path.name}."
        }
    except Exception as e:
        log.error(f"copy_file failed: {e}")
        return {"success": False, "confirmation": f"Failed to copy: {e}"}


async def move_file(source: str, destination: str) -> Dict:
    """Move or rename a file or folder."""
    try:
        source_path = Path(source).expanduser()
        dest_path = Path(destination).expanduser()
        
        if not source_path.exists():
            return {"success": False, "confirmation": f"Source '{source}' not found."}
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(dest_path))
        
        return {
            "success": True,
            "confirmation": f"Moved to {dest_path.name}."
        }
    except Exception as e:
        log.error(f"move_file failed: {e}")
        return {"success": False, "confirmation": f"Failed to move: {e}"}


async def delete_file(path: str, confirm: bool = True) -> Dict:
    """Delete a file or folder."""
    try:
        target = Path(path).expanduser()
        
        if not target.exists():
            return {"success": False, "confirmation": f"'{path}' not found."}
        
        if target.is_file():
            target.unlink()
            return {"success": True, "confirmation": f"Deleted file."}
        else:
            shutil.rmtree(target)
            return {"success": True, "confirmation": f"Deleted folder and contents."}
    except Exception as e:
        log.error(f"delete_file failed: {e}")
        return {"success": False, "confirmation": f"Failed to delete: {e}"}


async def list_files(directory: str, pattern: str = "*") -> Dict:
    """List files in a directory."""
    try:
        dir_path = Path(directory).expanduser()
        
        if not dir_path.exists():
            return {"success": False, "files": [], "confirmation": f"Directory not found: {directory}"}
        
        files = []
        for item in sorted(dir_path.glob(pattern))[:50]:  # Limit to 50 items
            files.append({
                "name": item.name,
                "type": "folder" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            })
        
        return {
            "success": True,
            "files": files,
            "confirmation": f"Found {len(files)} items in {dir_path.name}."
        }
    except Exception as e:
        log.error(f"list_files failed: {e}")
        return {"success": False, "files": [], "confirmation": f"Failed to list: {e}"}


async def create_file(path: str, content: str = "") -> Dict:
    """Create a new file with optional content."""
    try:
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path.write_text(content, encoding="utf-8")
        
        return {
            "success": True,
            "confirmation": f"Created {file_path.name}."
        }
    except Exception as e:
        log.error(f"create_file failed: {e}")
        return {"success": False, "confirmation": f"Failed to create: {e}"}


async def read_file_content(path: str, max_lines: int = 100) -> Dict:
    """Read file content (with line limit for large files)."""
    try:
        file_path = Path(path).expanduser()
        
        if not file_path.exists():
            return {"success": False, "content": "", "confirmation": f"File not found: {path}"}
        
        if not file_path.is_file():
            return {"success": False, "content": "", "confirmation": f"Not a file: {path}"}
        
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
        
        return {
            "success": True,
            "content": content,
            "lines": len(lines),
            "confirmation": f"Read {file_path.name}."
        }
    except Exception as e:
        log.error(f"read_file_content failed: {e}")
        return {"success": False, "content": "", "confirmation": f"Failed to read: {e}"}


async def search_files(directory: str, search_term: str) -> Dict:
    """Search for files matching a pattern."""
    try:
        dir_path = Path(directory).expanduser()
        
        if not dir_path.exists():
            return {"success": False, "files": [], "confirmation": f"Directory not found"}
        
        results = []
        search_lower = search_term.lower()
        
        for root, dirs, files in os.walk(dir_path):
            # Limit depth to 3 levels
            depth = root.replace(str(dir_path), "").count(os.sep)
            if depth > 3:
                dirs.clear()
                continue
            
            for file in files:
                if search_lower in file.lower():
                    full_path = Path(root) / file
                    results.append({
                        "path": str(full_path),
                        "name": file,
                        "size": full_path.stat().st_size
                    })
            
            if len(results) >= 20:  # Limit results
                break
        
        return {
            "success": True,
            "files": results[:20],
            "confirmation": f"Found {len(results)} matches."
        }
    except Exception as e:
        log.error(f"search_files failed: {e}")
        return {"success": False, "files": [], "confirmation": f"Search failed: {e}"}


# =============================================================================
# System Control
# =============================================================================

async def get_system_info() -> Dict:
    """Get system information."""
    try:
        info = {}
        
        # OS info
        result = await run_cmd_command("wmic os get caption,version /value")
        if result["success"]:
            info["os"] = result["output"]
        
        # System uptime
        result = await run_powershell("(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | ForEach-Object {$_.Days,'days',$_.Hours,'hours',$_.Minutes,'minutes'}")
        if result["success"]:
            info["uptime"] = result["output"]
        
        # Disk usage
        result = await run_powershell("Get-PSDrive C | Select-Object @{Name='Used';Expression={[math]::Round($_.Used/1GB,2)}},@{Name='Free';Expression={[math]::Round($_.Free/1GB,2)}}")
        if result["success"]:
            info["disk"] = result["output"]
        
        return {
            "success": True,
            "info": info,
            "confirmation": "Retrieved system info."
        }
    except Exception as e:
        return {"success": False, "info": {}, "confirmation": f"Failed to get system info: {e}"}


async def set_volume(level: int) -> Dict:
    """
    Set system volume level (0-100).
    
    Args:
        level: Volume level 0-100
    """
    try:
        if not 0 <= level <= 100:
            return {"success": False, "confirmation": "Volume level must be 0-100."}
        
        # Using nircmd (requires separate installation) or VBScript alternative
        vbscript = f"""
Set objAudio = CreateObject("WMPlayer.OCX.7")
objAudio.settings.volume = {level}
"""
        temp_vbs = Path(os.getenv("TEMP")) / "set_volume.vbs"
        temp_vbs.write_text(vbscript)
        
        result = await run_cmd_command(f'cscript "{temp_vbs}"')
        temp_vbs.unlink(missing_ok=True)
        
        if result["success"]:
            return {"success": True, "confirmation": f"Volume set to {level}%."}
        else:
            return {"success": False, "confirmation": "Could not set volume (nircmd not installed)."}
    except Exception as e:
        log.error(f"set_volume failed: {e}")
        return {"success": False, "confirmation": f"Failed to set volume: {e}"}


async def lock_screen() -> Dict:
    """Lock the Windows screen."""
    try:
        result = await run_cmd_command("rundll32.exe user32.dll,LockWorkStation")
        return {
            "success": result["success"],
            "confirmation": "Screen locked." if result["success"] else "Failed to lock screen."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed to lock: {e}"}


async def shutdown_system(delay_seconds: int = 0) -> Dict:
    """
    Shutdown the system.
    
    Args:
        delay_seconds: Delay before shutdown (0 for immediate)
    """
    try:
        if delay_seconds > 0:
            result = await run_cmd_command(f"shutdown /s /t {delay_seconds}")
            msg = f"System will shutdown in {delay_seconds} seconds."
        else:
            result = await run_cmd_command("shutdown /s /t 1")
            msg = "System shutting down immediately."
        
        return {
            "success": result["success"],
            "confirmation": msg if result["success"] else "Failed to initiate shutdown."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


async def hibernate_system() -> Dict:
    """Put system into hibernation."""
    try:
        result = await run_cmd_command("rundll32.exe powrprof.dll,SetSuspendState 1,1,1")
        return {
            "success": result["success"],
            "confirmation": "System entering hibernation." if result["success"] else "Failed."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


async def sleep_system() -> Dict:
    """Put system to sleep."""
    try:
        result = await run_cmd_command("rundll32.exe powrprof.dll,SetSuspendState 0,1,1")
        return {
            "success": result["success"],
            "confirmation": "System going to sleep." if result["success"] else "Failed."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


# =============================================================================
# Process Management
# =============================================================================

async def list_processes(pattern: str = "") -> Dict:
    """List running processes, optionally filtered by name."""
    try:
        if pattern:
            cmd = f'tasklist /FI "IMAGENAME eq {pattern}*"'
        else:
            cmd = "tasklist"
        
        result = await run_cmd_command(cmd)
        
        if result["success"]:
            lines = result["output"].split("\n")[3:]  # Skip header
            processes = [line.strip() for line in lines if line.strip()]
            return {
                "success": True,
                "processes": processes[:30],  # Limit to 30
                "confirmation": f"Found {len(processes)} processes."
            }
        else:
            return {"success": False, "processes": [], "confirmation": "Failed to list processes."}
    except Exception as e:
        return {"success": False, "processes": [], "confirmation": f"Failed: {e}"}


async def kill_process(process_name: str) -> Dict:
    """Kill a process by name."""
    try:
        result = await run_cmd_command(f"taskkill /IM {process_name} /F")
        return {
            "success": result["success"],
            "confirmation": f"Terminated {process_name}." if result["success"] else f"Could not terminate {process_name}."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


async def launch_application(app_name: str, args: str = "") -> Dict:
    """Launch an application."""
    try:
        cmd = f'start "" "{app_name}"' + (f' {args}' if args else '')
        result = await run_cmd_command(cmd)
        return {
            "success": result["success"],
            "confirmation": f"Launched {app_name}." if result["success"] else f"Failed to launch {app_name}."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


# =============================================================================
# Environment & Settings
# =============================================================================

async def set_environment_variable(name: str, value: str) -> Dict:
    """Set an environment variable permanently."""
    try:
        result = await run_powershell(
            f'[Environment]::SetEnvironmentVariable("{name}", "{value}", "User")'
        )
        return {
            "success": result["success"],
            "confirmation": f"Set {name}={value}." if result["success"] else "Failed to set variable."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


async def get_environment_variable(name: str) -> Dict:
    """Get an environment variable."""
    try:
        value = os.getenv(name)
        if value:
            return {
                "success": True,
                "value": value,
                "confirmation": f"{name} = {value}"
            }
        else:
            return {
                "success": False,
                "value": None,
                "confirmation": f"Variable '{name}' not found."
            }
    except Exception as e:
        return {"success": False, "value": None, "confirmation": f"Failed: {e}"}


# =============================================================================
# Network Operations
# =============================================================================

async def get_network_info() -> Dict:
    """Get network configuration."""
    try:
        result = await run_powershell(
            "Get-NetIPConfiguration -Detailed | Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway"
        )
        return {
            "success": result["success"],
            "info": result["output"],
            "confirmation": "Retrieved network info."
        }
    except Exception as e:
        return {"success": False, "info": "", "confirmation": f"Failed: {e}"}


async def test_connectivity(host: str = "8.8.8.8") -> Dict:
    """Test connectivity to a host."""
    try:
        result = await run_cmd_command(f"ping -n 1 {host}")
        success = "Reply from" in result["output"] or result["success"]
        return {
            "success": success,
            "confirmation": f"Connected to {host}." if success else f"No connection to {host}."
        }
    except Exception as e:
        return {"success": False, "confirmation": f"Failed: {e}"}


# =============================================================================
# Helper Functions
# =============================================================================

def format_confirmation(action: str, success: bool, details: str = "") -> str:
    """Format a confirmation message."""
    if success:
        msg = f"✓ {action} completed."
    else:
        msg = f"✗ {action} failed."
    
    if details:
        msg += f" {details}"
    
    return msg
