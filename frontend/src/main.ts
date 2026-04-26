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
let voiceBootstrapAttempted = false;
let replyPreviewTimeout: number | null = null;
let selectedLanguage = localStorage.getItem("jarvis.language") || "en-GB-RyanNeural";
let deferredInstallPrompt: BeforeInstallPromptEvent | null = null;

const statusEl = document.getElementById("status-text")!;
const errorEl = document.getElementById("error-text")!;
const commandFeedEl = document.getElementById("command-feed")!;
const commandFormEl = document.getElementById("command-form") as HTMLFormElement;
const commandInputEl = document.getElementById("command-input") as HTMLInputElement;
const languageSelectEl = document.getElementById("language-select") as HTMLSelectElement;
const installAppEl = document.getElementById("install-app") as HTMLButtonElement;
const accessPillEl = document.getElementById("access-pill")!;
const accessDetailEl = document.getElementById("access-detail")!;
const activityListEl = document.getElementById("activity-list")!;

type NoticeTone = "neutral" | "active" | "success" | "error";

const ongoingNotices = new Map<string, { tone: NoticeTone; text: string }>();

function updateMobileStatus(status: string) {
  const el = document.getElementById("mobile-status");
  const detail = document.getElementById("mobile-detail");
  const btnAnswer = document.getElementById("btn-answer-call");
  const btnOpen = document.getElementById("btn-open-mobile-app");

  if (el && detail) {
    el.textContent = status;
    if (status.includes("Connected")) {
      el.className = "live-pill success";
      detail.textContent = "Device connected and ready for control.";
      if (btnAnswer) btnAnswer.style.display = "block";
      if (btnOpen) btnOpen.style.display = "block";
    } else {
      el.className = "live-pill neutral";
      detail.textContent = "Connect your phone via USB for direct control.";
      if (btnAnswer) btnAnswer.style.display = "none";
      if (btnOpen) btnOpen.style.display = "none";
    }
  }
}

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

function renderNotices() {
  activityListEl.innerHTML = "";

  if (ongoingNotices.size === 0) {
    const empty = document.createElement("div");
    empty.className = "activity-empty";
    empty.textContent = "No ongoing actions.";
    activityListEl.append(empty);
    return;
  }

  for (const [key, notice] of ongoingNotices.entries()) {
    const row = document.createElement("div");
    row.className = `activity-item ${notice.tone}`;
    row.dataset.noticeId = key;
    row.textContent = notice.text;
    activityListEl.append(row);
  }
}

function setNotice(id: string, text: string, tone: NoticeTone = "neutral") {
  ongoingNotices.set(id, { text, tone });
  renderNotices();
}

function clearNotice(id: string) {
  ongoingNotices.delete(id);
  renderNotices();
}

function renderAccessStatus(status: Record<string, unknown>) {
  const ok = Boolean(status.ok);
  const message = String(status.message || (ok ? "Desktop control is ready." : "Desktop control is limited."));
  appendCommandEntry("system", `${ok ? "Access ready" : "Access limited"}: ${message}`);
  accessPillEl.textContent = ok ? "ready" : "limited";
  accessPillEl.className = `live-pill ${ok ? "success" : "error"}`;
  accessDetailEl.textContent = message;
  setNotice("access", ok ? "Laptop access is online." : `Laptop access limited: ${message}`, ok ? "success" : "error");
}

function getLanguageLabel(language: string): string {
  const option = Array.from(languageSelectEl.options).find((entry) => entry.value === language);
  return option?.text || language;
}

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setNotice("error", msg, "error");
  setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 5000);
}

function updateInstallButton() {
  if (deferredInstallPrompt) {
    installAppEl.hidden = false;
    installAppEl.textContent = "Install App";
  } else {
    // If not supported/ready, we show it as a 'How to Install' button on mobile
    if (window.innerWidth < 768) {
      installAppEl.hidden = false;
      installAppEl.textContent = "How to Install";
    } else {
      installAppEl.hidden = true;
    }
  }
}

function updateStatus(state: State) {
  if (!voiceBootstrapped) {
    statusEl.textContent = "voice standby...";
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
      clearNotice("state");
      if (!isMuted) voiceInput.resume();
      break;
    case "listening":
      setNotice("state", "Listening for your next command.", "active");
      if (!isMuted) voiceInput.resume();
      break;
    case "thinking":
      setNotice("state", "Thinking and planning the next action.", "active");
      voiceInput.pause();
      break;
    case "speaking":
      setNotice("state", "Speaking the response out loud.", "active");
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
  setNotice("command", `Running command: ${clean}`, "active");
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
  clearNotice("command");
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
      setNotice("command", "Working on your command.", "active");
    } else if (state === "idle") {
      clearNotice("command");
      transition("idle");
    }
  } else if (type === "text") {
    showReplyPreview(String(msg.text || ""));
    setNotice("last-response", "Latest response received.", "success");
    console.log("[JARVIS]", msg.text);
  } else if (type === "task_spawned") {
    appendCommandEntry("system", `Task started: ${String(msg.prompt || "background task")}`);
    setNotice("task", `Task started: ${String(msg.prompt || "background task")}`, "active");
    console.log("[task]", "spawned:", msg.task_id, msg.prompt);
  } else if (type === "task_complete") {
    appendCommandEntry("system", `Task complete: ${String(msg.summary || msg.status || "done")}`);
    setNotice("task", `Task complete: ${String(msg.summary || msg.status || "done")}`, "success");
    console.log("[task]", "complete:", msg.task_id, msg.status, msg.summary);
  } else if (type === "access_status") {
    renderAccessStatus((msg.status || {}) as Record<string, unknown>);
  } else if (type === "mobile_status") {
    updateMobileStatus(String(msg.status || ""));
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
  if (voiceBootstrapAttempted) return;
  voiceBootstrapAttempted = true;
  ensureAudioContext();

  if (!isSpeechRecognitionSupported()) {
    showError("Voice input needs Google Chrome on this setup.");
    updateStatus("idle");
    return;
  }

  try {
    await primeMicrophonePermission();
  } catch {
    showError("Allow microphone access in Chrome so JARVIS can respond to hello jarvis.");
    setNotice("voice-permission", "Microphone permission is still needed for hands-free voice access.", "error");
    voiceBootstrapAttempted = false;
    updateStatus("idle");
    return;
  }

  voiceBootstrapped = true;
  clearNotice("voice-permission");
  voiceInput.start();
  transition("listening");
}

function handleFirstInteraction() {
  bootstrapVoice();
}

window.addEventListener("load", () => {
  bootstrapVoice();
});

window.addEventListener("focus", () => {
  if (!voiceBootstrapped) {
    bootstrapVoice();
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && !voiceBootstrapped) {
    bootstrapVoice();
  }
});

document.addEventListener("click", handleFirstInteraction);
document.addEventListener("touchstart", handleFirstInteraction);
document.addEventListener("keydown", handleFirstInteraction);

installAppEl.addEventListener("click", async () => {
  if (deferredInstallPrompt) {
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
  } else {
    // Show manual instructions
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream;
    if (isIOS) {
      alert("To install on iPhone:\n1. Tap the 'Share' icon (square with arrow) at the bottom.\n2. Scroll down and tap 'Add to Home Screen'.");
    } else {
      alert("To install on Android:\n1. Tap the three dots (⋮) in the top right.\n2. Tap 'Install app' or 'Add to Home screen'.");
    }
  }
});

// Force check for install button after load
setTimeout(updateInstallButton, 3000);

// Installation Overlay Logic
const installOverlay = document.getElementById("mobile-install-overlay");
const btnInstallNow = document.getElementById("btn-install-now");
const btnSkipInstall = document.getElementById("btn-skip-install");

function checkShowInstallOverlay() {
  const isMobile = window.innerWidth < 768;
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone;
  
  if (isMobile && !isStandalone) {
    if (installOverlay) installOverlay.style.display = "flex";
  }
}

btnInstallNow?.addEventListener("click", () => {
  // Trigger the actual install logic
  installAppEl.click();
});

btnSkipInstall?.addEventListener("click", () => {
  if (installOverlay) installOverlay.style.display = "none";
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.warn("[pwa] service worker registration failed", error);
    });
    // Check for install overlay after load
    setTimeout(checkShowInstallOverlay, 1500);
  });
}

ensureAudioContext();
updateStatus("idle");
updateInstallButton();
renderNotices();
languageSelectEl.value = selectedLanguage;
appendCommandEntry("system", "Manual command mode is ready. Type or speak a command.");
appendCommandEntry("system", `Voice input is set to ${getLanguageLabel(selectedLanguage)}.`);
appendCommandEntry("system", "Voice startup is automatic. Say hello jarvis to wake it.");
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
  
  // Extract base language (e.g., 'en-US' from 'en-US-GuyNeural')
  let baseLang = selectedLanguage;
  if (selectedLanguage === "fish-audio") {
    baseLang = "en-US"; // Default recognition for Fish
  } else {
    const parts = selectedLanguage.split("-");
    if (parts.length >= 2) {
      baseLang = `${parts[0]}-${parts[1]}`;
    }
  }
  
  voiceInput.setLanguage(baseLang);
  appendCommandEntry("system", `Voice changed to ${getLanguageLabel(selectedLanguage)}.`);
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

document.getElementById("btn-answer-call")?.addEventListener("click", (e) => {
  e.stopPropagation();
  socket.send({ type: "transcript", text: "mobile_answer", isFinal: true, source: "ui", language: selectedLanguage });
});

document.getElementById("btn-open-mobile-app")?.addEventListener("click", (e) => {
  e.stopPropagation();
  const pkg = prompt("Enter mobile app package name (e.g., com.android.chrome):");
  if (pkg) {
    socket.send({ type: "transcript", text: `mobile_open ${pkg}`, isFinal: true, source: "ui", language: selectedLanguage });
  }
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
