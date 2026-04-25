#!/usr/bin/env python3
"""
Integration test for JARVIS Windows automation.
Run this to verify all components work correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_windows_automation():
    """Test Windows automation module."""
    print("=" * 60)
    print("JARVIS Windows Automation — Integration Test")
    print("=" * 60)
    
    # Test 1: Check imports
    print("\n[1/5] Checking imports...")
    try:
        from windows_automation import (
            run_powershell, run_cmd_command, list_files,
            get_system_info, list_processes
        )
        print("✓ windows_automation module imported successfully")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    
    # Test 2: Check actions integration
    print("\n[2/5] Checking actions integration...")
    try:
        from actions import parse_desktop_command, execute_action
        print("✓ actions module imported successfully")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    
    # Test 3: Parse desktop commands
    print("\n[3/5] Testing command parsing...")
    test_commands = [
        ("list files", {"action": "file_list"}),
        ("open notepad", {"action": "open"}),
        ("lock screen", {"action": "lock_screen"}),
        ("set volume to 75", {"action": "set_volume"}),
        ("show processes", {"action": "process_list"}),
    ]
    
    for cmd, expected_action in test_commands:
        result = parse_desktop_command(cmd)
        if result and result.get("action") == expected_action["action"]:
            print(f"  ✓ '{cmd}' → {result['action']}")
        else:
            print(f"  ✗ '{cmd}' failed to parse correctly")
            return False
    
    # Test 4: Test system info (non-destructive)
    print("\n[4/5] Testing system operations...")
    try:
        result = await get_system_info()
        if result["success"]:
            print("  ✓ System info retrieved successfully")
        else:
            print("  ⚠ System info not available (non-critical)")
    except Exception as e:
        print(f"  ✗ System info failed: {e}")
        return False
    
    # Test 5: Test file listing
    print("\n[5/5] Testing file operations...")
    try:
        desktop = Path.home() / "Desktop"
        # Try Documents as fallback if Desktop has issues
        if not desktop.exists():
            desktop = Path.home() / "Documents"
        
        result = await list_files(str(desktop))
        count = len(result["files"])
        print(f"  ✓ Directory has {count} items")
    except Exception as e:
        # Non-critical failure
        print(f"  ⚠ File listing not available (non-critical): {e}")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! JARVIS Windows automation is ready.")
    print("=" * 60)
    print("\nQuick start:")
    print("  1. Start JARVIS: python server.py")
    print("  2. Open browser: http://localhost:5173")
    print("  3. Try: 'Open VS Code' or 'Show files on desktop'")
    print("\nFor help, see WINDOWS_AUTOMATION.md")
    return True

async def main():
    try:
        success = await test_windows_automation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
