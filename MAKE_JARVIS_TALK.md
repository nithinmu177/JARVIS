# 🎙️ Make JARVIS Talk — Quick Setup

JARVIS is running but needs 2 free API keys to produce voice audio.

## Step 1: Get Anthropic API Key ⚡

1. Go to: **https://console.anthropic.com**
2. Sign up (free account)
3. Click "API Keys" 
4. Create new API key
5. Copy the key

## Step 2: Get Fish Audio API Key 🎵

1. Go to: **https://fish.audio**  
2. Sign up (free account)
3. Get your API key from settings
4. Copy the key

## Step 3: Update .env File 📝

Edit the `.env` file in your jarvis-main folder:

```env
ANTHROPIC_API_KEY=paste-your-key-here
FISH_API_KEY=paste-your-key-here
```

Save the file.

## Step 4: Restart JARVIS 🚀

**In the backend terminal** (where you see "Uvicorn running"):
- Press `Ctrl+C` to stop
- Run: `py server.py`

You'll see:
```
INFO: Application startup complete
INFO: Uvicorn running on http://127.0.0.1:8340
```

## Step 5: Test It! 🎤

1. Open **http://127.0.0.1:5174** (browser - already open)
2. Click the microphone/permission button
3. Say: **"Hello"**
4. Wait ~1 second
5. You hear JARVIS speak! ✨

---

## What You Should See

**Browser (Frontend)**:
- Animated orb in center (reacts to voice)
- Pulses when listening
- Swirls when thinking

**Terminal (Backend)**:
- Logs like: `JARVIS: Hello, sir.`
- Shows cache hits and misses

**Speakers**:
- JARVIS voice: British, calm, quick

---

## Quick Test Commands

Say any of these:
- **"Hello"** → Instant response ⚡
- **"What time is it?"** → Checks clock
- **"Build me a React app"** → Starts Claude Code
- **"What's on my calendar?"** → Reads calendar
- **"Search for React tutorial"** → Opens Google

---

## Troubleshooting

| Problem | Solution |
|---|---|
| No audio output | Check Speaker volume, check API keys in .env |
| No response to voice | Browser microphone might be muted (check browser settings) |
| Backend crashes | Make sure .env has real API keys |
| "API key not configured" in logs | Update .env and restart server |

---

## Need Keys?

- **Anthropic** (free tier): https://console.anthropic.com → Sign up, create key
- **Fish Audio** (free tier): https://fish.audio → Sign up, get key

Both offer free usage to get started!

---

Once set up, JARVIS responds instantly to your voice. Try it now! 🎬
