# JARVIS Windows Automation Guide

JARVIS now has comprehensive Windows laptop control capabilities! You can control applications, files, system settings, and more entirely through voice commands.

## Quick Commands by Category

### 🎯 Opening & Running Apps
- "Open VS Code"
- "Launch Chrome"
- "Open Notepad"
- "Run PowerShell"

### 📁 File Operations
- "List files on desktop" / "Show files in C:\Users\Umesh\Documents"
- "Create file myfile.txt with hello world"
- "Copy C:\source\file.txt to C:\destination"
- "Move file.txt to Documents"
- "Delete oldfile.txt"
- "Read file.txt"
- "Search for *.log files in C:\Users\Umesh"

### 💻 System Control
- "Lock my screen"
- "Put system to sleep"
- "Set volume to 75"
- "Check system info"
- "Shutdown" (immediate)
- "Shutdown in 60 seconds"
- "Hibernate"

### ⚡ Process Management
- "List processes"
- "Show processes for chrome"
- "Kill process notepad.exe"

### 🌐 Network & Environment
- "Show network info"
- "Test connection to 8.8.8.8"
- "Set environment variable MY_VAR=value"
- "Get environment variable PATH"

### 🖥️ Direct Terminal Commands
- "PowerShell Get-Process"
- "CMD dir C:\"

### 🎮 Window Management
- "Focus VS Code"
- "Minimize this window"
- "Close Chrome"
- "Maximize Explorer"
- "Show windows" / "List windows"

### ⌨️ Keyboard & Mouse
- "Press Ctrl+S"
- "Type Hello World"
- "Click"
- "Save file as myfile.txt"

## Technical Details

### File Paths
JARVIS understands:
- Relative paths: `file.txt`, `Desktop\folder`
- Absolute paths: `C:\Users\Umesh\Documents`
- Tilde expansion: `~\Desktop` (expands to home directory)

### PowerShell Commands
For complex operations, use PowerShell directly:
- `"PowerShell Get-ChildItem -Path C:\ -Recurse"`
- `"PowerShell Get-Service | Where-Object {$_.Status -eq 'Stopped'}"`

### System Commands
Windows automation is disabled if:
- PyAutoGUI can't access screen (headless/RDP limitation)
- Window automation libraries missing
- Insufficient permissions

Check status with: **"Check access"** or **"Check desktop access"**

## Safety Notes

⚠️ **Important Commands Require Confirmation**
- Shutdown/Hibernate commands execute after a brief delay
- Delete operations are permanent
- Process termination may affect system stability

🔐 **Privacy & Security**
- All operations are local to your Windows machine
- No data is sent to remote servers
- File operations respect system permissions
- Logging is available in JARVIS terminal

## Troubleshooting

### "Automation not available" error
**Solution:** Install missing dependencies
```bash
pip install pyautogui pygetwindow
```

### Volume control doesn't work
**Solution:** Some systems require alternative tools
- Try: `"PowerShell (Get-Volume | Set-Volume -Mute:$false).Volume = 0.5"`

### Process killing fails
**Solution:** Run JARVIS terminal as Administrator
- Right-click Terminal → Run as Administrator

### File operations fail on Network drives
**Solution:** Use absolute UNC paths: `\\servername\share\file.txt`

## Examples in Conversation

**You:** "Show me what's on the desktop"
**JARVIS:** Lists all desktop files and folders

**You:** "Create a new project folder called my-app"
**JARVIS:** Creates C:\Users\Umesh\Desktop\my-app directory

**You:** "Check my network connection"
**JARVIS:** Tests connectivity and shows network configuration

**You:** "Find all Python files in my Documents"
**JARVIS:** Searches and lists all .py files

**You:** "Set the volume to 50 and lock the screen"
**JARVIS:** Adjusts volume, then locks your screen

## Advanced: Integration with Voice

These commands work seamlessly with JARVIS voice mode:

1. **Say the command naturally** - JARVIS understands context
2. **Get audio confirmation** - JARVIS speaks the result
3. **Chain commands** - "Open VS Code and create a new file"
4. **Conditional logic** - "If Chrome is running, close it"

## Error Handling

JARVIS provides clear feedback:
- ✓ Success: "Done, sir."
- ✗ Failure: Clear explanation of what went wrong
- ⚠ Warning: "This requires administrator access"

## Environment Variables

Store persistent configuration:
```bash
"Set environment variable JARVIS_THEME=dark"
"Get environment variable JARVIS_THEME"
```

These persist across system restarts when set through JARVIS.

---

**Need more features?** You can extend JARVIS by editing `windows_automation.py` and `parse_desktop_command()` in `actions.py`.
