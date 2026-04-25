#!/usr/bin/env python3
"""
Quick setup wizard for JARVIS to start talking.
Run this to configure your API keys interactively.
"""

import os
from pathlib import Path

def setup_keys():
    print("\n" + "="*60)
    print("🎙️  JARVIS VOICE SETUP")
    print("="*60)
    print("\nTo make JARVIS talk, you need 2 free API keys:\n")
    
    print("1️⃣  ANTHROPIC API KEY (for Claude AI)")
    print("   → Get it FREE from: https://console.anthropic.com")
    print("   → Sign up, go to API Keys, create a new key")
    print("   → Paste it below:\n")
    
    anthropic_key = input("Enter ANTHROPIC_API_KEY: ").strip()
    
    print("\n2️⃣  FISH AUDIO API KEY (for voice/TTS)")
    print("   → Get it FREE from: https://fish.audio")
    print("   → Sign up, create API key")
    print("   → Paste it below:\n")
    
    fish_key = input("Enter FISH_API_KEY: ").strip()
    
    # Update .env file
    env_file = Path(__file__).parent / ".env"
    
    env_content = env_file.read_text()
    env_content = env_content.replace(
        "ANTHROPIC_API_KEY=your-anthropic-api-key-here",
        f"ANTHROPIC_API_KEY={anthropic_key}"
    )
    env_content = env_content.replace(
        "FISH_API_KEY=your-fish-audio-api-key-here",
        f"FISH_API_KEY={fish_key}"
    )
    
    env_file.write_text(env_content)
    
    print("\n" + "="*60)
    print("✅ Keys configured successfully!")
    print("="*60)
    print("\nNow restart JARVIS:")
    print("1. Kill the backend: Press Ctrl+C in the server terminal")
    print("2. Restart: py server.py")
    print("3. Say anything in the browser - JARVIS will speak!")
    print("\nKeep both terminals running:")
    print("  - Backend: py server.py (shows activity logs)")
    print("  - Frontend: npm run dev (shows visual orb)")
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    setup_keys()
