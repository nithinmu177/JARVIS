# ✨ JARVIS Windows Automation — Setup & Quick Start

Your JARVIS voice assistant now has **full Windows laptop control**! Here's what was added:

## 🎯 What's New

**New File:** `windows_automation.py` — Complete Windows automation module with:
- ✅ File operations (copy, move, delete, list, search, read, create)
- ✅ System control (volume, lock, sleep, shutdown, hibernate)
- ✅ Process management (list, kill, launch)
- ✅ PowerShell & CMD execution
- ✅ Environment variables
- ✅ Network diagnostics

**Modified Files:**
- `actions.py` — Integrated Windows automation into main action system
- Added 40+ new voice commands via `parse_desktop_command()`

## 🚀 Quick Start (3 Steps)

### 1. Install Dependencies (if needed)
```bash
pip install pyautogui pygetwindow
```

### 2. Start JARVIS
```bash
python server.py
```

### 3. Try These Voice Commands
- "Open VS Code"
- "Create a new file called test.txt"
- "Show me the files on my desktop"
- "Lock my screen"
- "Set volume to 75"

## 🎤 Voice Command Examples

### File Management
```
"Create a file called myapp.py with print('hello')"
"Copy C:\Users\Umesh\Desktop\file.txt to Documents"
"Search for *.log files in my Documents"
"Show files in C:\Users\Umesh\Downloads"
"Delete C:\temp\oldfile.txt"
```

### System Control
```
"Set the volume to 50"
"Lock my laptop"
"Put the system to sleep"
"Check my system info"
"Shutdown in 120 seconds"
```

### Process & App Management
```
"Show me all running processes"
"Kill Chrome"
"Launch VS Code"
"Launch Spotify"
"Close Notepad"
```

### Network & Diagnostics
```
"Check my network connection"
"Show network info"
"Test connection to Google" (ping 8.8.8.8)
"Get my network status"
```

### Advanced (PowerShell/CMD)
```
"PowerShell Get-Process | Select-Object Name, Memory"
"CMD dir C:\ /s"
"Run ipconfig in PowerShell"
```

## 📋 Full Command Reference

See `WINDOWS_AUTOMATION.md` for comprehensive documentation including:
- All supported commands
- Command syntax
- Error handling
- Troubleshooting
- Advanced usage

## 🔧 How It Works

1. **Voice Input** → JARVIS transcribes your words
2. **Intent Detection** → `parse_desktop_command()` recognizes action
3. **Action Routing** → `execute_action()` dispatches to handler
4. **Execution** → `windows_automation.py` performs operation
5. **Voice Response** → JARVIS confirms result

### Example Flow
```
You:    "Open VS Code"
↓
Parser: {"action": "open", "target": "VS Code"}
↓
Router: open_visible_target("VS Code")
↓
Execute: subprocess launches code.exe
↓
JARVIS: "Opening VS Code on your screen right now."
```

## ⚙️ Configuration

No additional configuration needed! The system auto-detects:
- Windows OS
- Available applications
- System permissions
- Desktop automation capabilities

Check availability with: **"Check access"** or **"Check laptop access"**

## 🛡️ Safety Features

- ✅ Read-only file operations by default
- ✅ Confirmation messages before destructive actions
- ✅ Proper error handling
- ✅ Timeout protection on long-running operations
- ✅ Access status monitoring

## 🐛 Troubleshooting

### "Module not found" error
```bash
# Install missing dependencies
pip install pyautogui pygetwindow
```

### "Automation not available"
- Ensure running Python script (not in restricted environment)
- Check that screen is accessible (not RDP/headless)
- Verify permissions in your Windows account

### Commands not recognized
- Check exact command syntax in `WINDOWS_AUTOMATION.md`
- Some apps need full paths (e.g., `C:\Program Files\...`)
- Natural language variation is supported!

## 📚 Examples

### Create a Project Directory
```
You: "Create a folder called my-react-app on desktop"
JARVIS: Creates C:\Users\Umesh\Desktop\my-react-app
```

### Batch File Operations
```
You: "Copy all files from Desktop to Documents"
JARVIS: Uses copy and paste operations
```

### System Maintenance
```
You: "List all processes using more than 100MB"
JARVIS: Shows process list (via PowerShell)
```

## 🔄 Integration Points

The new automation integrates with existing JARVIS features:
- **Calendar & Mail:** Get events, then open related apps
- **Notes:** Create notes as files on disk
- **Terminal:** Spawn terminals and run commands
- **Browser:** Open URLs and web apps
- **Claude Code:** Launch projects in VS Code

## 📈 Next Steps

1. **Try basic commands** - Get comfortable with voice control
2. **Explore file operations** - Organize your laptop by voice
3. **Automate workflows** - Chain commands for productivity
4. **Customize commands** - Edit `parse_desktop_command()` to add your own

## 🎓 Learning

Start simple:
1. "Open [app name]"
2. "List files"
3. "Lock screen"
4. Then progress to more complex commands

JARVIS learns your patterns and adapts!

---

**Questions?** Check `WINDOWS_AUTOMATION.md` or examine `windows_automation.py` for implementation details.

**Happy commanding!** 🚀
