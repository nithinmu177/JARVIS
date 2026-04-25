/**
 * JARVIS - Main entry point.
 *
 * Wires together the orb visualization, WebSocket communication,
 * speech recognition, manual commands, and audio playback.
 */

import { createOrb, type OrbState } from "./orb";
import { createVoiceInput, createAudioPlayer, isSpeechRecognitionSupported } from "./voice";
import { createSocket } from "./ws";
import { openSettings, checkFirstTimeSetup } from "./settings";
import "./style.css";

type State = "idle" | "listening" | "thinking" | "speaking";
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

let currentState: State = "idle";
let isMuted = false;
let voiceBootstrapped = false;
let replyPreviewTimeout: number | null = null;
let selectedLanguage = localStorage.getItem("jarvis.language") || "en-IN";
let deferredInstallPrompt: BeforeInstallPromptEvent | null = null;

const statusEl = document.getElementById("status-text")!;
const errorEl = document.getElementById("error-text")!;
const commandFeedEl = document.getElementById("command-feed")!;
const commandFormEl = document.getElementById("command-form") as HTMLFormElement;
const commandInputEl = document.getElementById("command-input") as HTMLInputElement;
const languageSelectEl = document.getElementById("language-select") as HTMLSelectElement;
const installAppEl = document.getElementById("install-app") as HTMLButtonElement;

function appendCommandEntry(role: "user" | "jarvis" | "system", text: string) {
  const row = document.createElement("div");
  row.className = `command-entry ${role}`;

  const label = document.createElement("span");
  label.className = "command-role";
  label.textContent = role === "user" ? "you" : role === "jarvis" ? "jarvis" : "system";

  const content = document.createElement("span");
  content.className = "command-content";
  content.textContent = text;

  row.append(label, content);
  commandFeedEl.prepend(row);

  while (commandFeedEl.childElementCount > 8) {
    commandFeedEl.removeChild(commandFeedEl.lastElementChild!);
  }
}

function renderAccessStatus(status: Record<string, unknown>) {
  const ok = Boolean(status.ok);
  const message = String(status.message || (ok ? "Desktop control is ready." : "Desktop control is limited."));
  appendCommandEntry("system", `${ok ? "Access ready" : "Access limited"}: ${message}`);
}

function getLanguageLabel(language: string): string {
  const option = Array.from(languageSelectEl.options).find((entry) => entry.value === language);
  return option?.text || language;
}

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 5000);
}

function updateInstallButton() {
  installAppEl.hidden = deferredInstallPrompt === null;
}

function updateStatus(state: State) {
  if (!voiceBootstrapped) {
    statusEl.textContent = "click anywhere to enable voice";
    return;
  }

  const labels: Record<State, string> = {
    idle: "",
    listening: "listening...",
    thinking: "thinking...",
    speaking: "",
  };
  statusEl.textContent = labels[state];
}

function showReplyPreview(text: string) {
  if (replyPreviewTimeout) {
    window.clearTimeout(replyPreviewTimeout);
  }

  statusEl.textContent = text;
  appendCommandEntry("jarvis", text);

  replyPreviewTimeout = window.setTimeout(() => {
    if (currentState === "idle" || currentState === "listening") {
      updateStatus(currentState);
    }
  }, 5000);
}

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const orb = createOrb(canvas);

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const WS_URL = `${wsProto}//${window.location.host}/ws/voice`;
const socket = createSocket(WS_URL);

const audioPlayer = createAudioPlayer();
orb.setAnalyser(audioPlayer.getAnalyser());

function transition(newState: State) {
  if (newState === currentState) return;

  currentState = newState;
  orb.setState(newState as OrbState);
  updateStatus(newState);

  switch (newState) {
    case "idle":
      if (!isMuted) voiceInput.resume();
      break;
    case "listening":
      if (!isMuted) voiceInput.resume();
      break;
    case "thinking":
      voiceInput.pause();
      break;
    case "speaking":
      voiceInput.pause();
      break;
  }
}

function sendCommand(text: string, source: "manual" | "voice" = "manual") {
  const clean = text.trim();
  if (!clean) return;

  if (!socket.isConnected()) {
    showError("JARVIS is still connecting to the server. Try again in a moment.");
    updateStatus("idle");
    return;
  }

  appendCommandEntry("user", clean);
  statusEl.textContent = `command: ${clean}`;
  audioPlayer.stop();
  socket.send({ type: "transcript", text: clean, isFinal: true, source, language: selectedLanguage });
  transition("thinking");
}

const voiceInput = createVoiceInput(
  (text: string) => {
    sendCommand(text, "voice");
  },
  (msg: string) => {
    showError(msg);
  },
  () => ({
    language: selectedLanguage,
    requireWakeWord: false,
    wakeWords: ["jarvis", "aura"],
  })
);

audioPlayer.onFinished(() => {
  transition("idle");
});

socket.onMessage((msg) => {
  const type = msg.type as string;

  if (type === "audio") {
    const audioData = msg.data as string;
    console.log("[audio] received", audioData ? `${audioData.length} chars` : "EMPTY", "state:", currentState);

    if (audioData) {
      if (currentState !== "speaking") {
        transition("speaking");
      }
      audioPlayer.enqueue(audioData);
    } else {
      console.warn("[audio] no data received, returning to idle");
      transition("idle");
    }

    if (msg.text) {
      appendCommandEntry("jarvis", String(msg.text));
      console.log("[JARVIS]", msg.text);
    }
  } else if (type === "status") {
    const state = msg.state as string;
    if (state === "thinking" && currentState !== "thinking") {
      transition("thinking");
    } else if (state === "working") {
      transition("thinking");
      statusEl.textContent = "working...";
      appendCommandEntry("system", "Jarvis is working on your command.");
    } else if (state === "idle") {
      transition("idle");
    }
  } else if (type === "text") {
    showReplyPreview(String(msg.text || ""));
    console.log("[JARVIS]", msg.text);
  } else if (type === "task_spawned") {
    appendCommandEntry("system", `Task started: ${String(msg.prompt || "background task")}`);
    console.log("[task]", "spawned:", msg.task_id, msg.prompt);
  } else if (type === "task_complete") {
    appendCommandEntry("system", `Task complete: ${String(msg.summary || msg.status || "done")}`);
    console.log("[task]", "complete:", msg.task_id, msg.status, msg.summary);
  } else if (type === "access_status") {
    renderAccessStatus((msg.status || {}) as Record<string, unknown>);
  }
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event as BeforeInstallPromptEvent;
  updateInstallButton();
  appendCommandEntry("system", "Install is ready. Tap Install to add JARVIS to your home screen.");
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  updateInstallButton();
  appendCommandEntry("system", "JARVIS was installed successfully.");
});

function ensureAudioContext() {
  const ctx = audioPlayer.getAnalyser().context as AudioContext;
  if (ctx.state === "suspended") {
    ctx.resume().then(() => console.log("[audio] context resumed"));
  }
}

async function primeMicrophonePermission() {
  if (!navigator.mediaDevices?.getUserMedia) return;
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  stream.getTracks().forEach((track) => track.stop());
}

async function bootstrapVoice() {
  if (voiceBootstrapped) return;
  ensureAudioContext();

  if (!isSpeechRecognitionSupported()) {
    showError("Voice input needs Google Chrome on this setup.");
    updateStatus("idle");
    return;
  }

  try {
    await primeMicrophonePermission();
  } catch {
    showError("Allow microphone access in the browser to talk with JARVIS.");
    updateStatus("idle");
    return;
  }

  voiceBootstrapped = true;
  voiceInput.start();
  transition("listening");
}

function handleFirstInteraction() {
  bootstrapVoice();
}

document.addEventListener("click", handleFirstInteraction, { once: true });
document.addEventListener("touchstart", handleFirstInteraction, { once: true });
document.addEventListener("keydown", handleFirstInteraction, { once: true });

installAppEl.addEventListener("click", async () => {
  if (!deferredInstallPrompt) return;

  await deferredInstallPrompt.prompt();
  const choice = await deferredInstallPrompt.userChoice;
  appendCommandEntry(
    "system",
    choice.outcome === "accepted"
      ? "Install accepted."
      : "Install dismissed. You can try again later from the browser menu."
  );
  deferredInstallPrompt = null;
  updateInstallButton();
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.warn("[pwa] service worker registration failed", error);
    });
  });
}

ensureAudioContext();
updateStatus("idle");
updateInstallButton();
languageSelectEl.value = selectedLanguage;
appendCommandEntry("system", "Manual command mode is ready. Type or speak a command.");
appendCommandEntry("system", `Voice input is set to ${getLanguageLabel(selectedLanguage)}.`);
appendCommandEntry("system", "Voice control is on. Laptop actions by voice still require Jarvis or Aura at the start.");
fetch("/api/access-status")
  .then((response) => response.json())
  .then((status) => renderAccessStatus(status))
  .catch(() => appendCommandEntry("system", "Could not verify desktop access yet."));

commandFormEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = commandInputEl.value.trim();
  if (!value) return;
  sendCommand(value, "manual");
  commandInputEl.value = "";
});

languageSelectEl.addEventListener("change", () => {
  selectedLanguage = languageSelectEl.value;
  localStorage.setItem("jarvis.language", selectedLanguage);
  voiceInput.setLanguage(selectedLanguage);
  appendCommandEntry("system", `Language changed to ${getLanguageLabel(selectedLanguage)}.`);
});

const btnMute = document.getElementById("btn-mute")!;
const btnMenu = document.getElementById("btn-menu")!;
const menuDropdown = document.getElementById("menu-dropdown")!;
const btnRestart = document.getElementById("btn-restart")!;
const btnFixSelf = document.getElementById("btn-fix-self")!;

btnMute.addEventListener("click", (e) => {
  e.stopPropagation();
  if (!voiceBootstrapped) {
    bootstrapVoice();
  }
  isMuted = !isMuted;
  btnMute.classList.toggle("muted", isMuted);
  if (isMuted) {
    voiceInput.pause();
    transition("idle");
  } else {
    voiceInput.resume();
    transition("listening");
  }
});

btnMenu.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = menuDropdown.style.display === "none" ? "block" : "none";
});

document.addEventListener("click", () => {
  menuDropdown.style.display = "none";
});

btnRestart.addEventListener("click", async (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  statusEl.textContent = "restarting...";
  try {
    await fetch("/api/restart", { method: "POST" });
    setTimeout(() => window.location.reload(), 4000);
  } catch {
    statusEl.textContent = "restart failed";
  }
});

btnFixSelf.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  socket.send({ type: "fix_self" });
  statusEl.textContent = "entering work mode...";
});

const btnSettings = document.getElementById("btn-settings")!;
btnSettings.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  openSettings();
});

setTimeout(() => {
  checkFirstTimeSetup();
}, 2000);
