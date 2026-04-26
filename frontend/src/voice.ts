/**
 * Voice input (Web Speech API) and audio output (AudioContext) for JARVIS.
 */

export interface VoiceInput {
  start(): void;
  stop(): void;
  pause(): void;
  resume(): void;
  setLanguage(language: string): void;
}

export interface VoiceConfig {
  language: string;
  requireWakeWord: boolean;
  wakeWords: string[];
}

const COMMAND_HINTS = [
  "jarvis",
  "aura",
  "open",
  "close",
  "search",
  "look up",
  "build",
  "create",
  "make",
  "play",
  "stop",
  "call",
  "message",
  "notepad",
  "chrome",
  "powershell",
  "terminal",
];

export function isSpeechRecognitionSupported(): boolean {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SR = (window as any).SpeechRecognition || (typeof webkitSpeechRecognition !== "undefined" ? webkitSpeechRecognition : null);
  return Boolean(SR);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const webkitSpeechRecognition: any;

function startsWithWakeWord(text: string, wakeWords: string[]): boolean {
  const lowered = text.trim().toLowerCase();
  return wakeWords.some((wakeWord) => {
    const normalized = wakeWord.toLowerCase();
    return (
      lowered === normalized ||
      lowered.startsWith(`${normalized} `) ||
      lowered.startsWith(`${normalized},`) ||
      lowered.startsWith(`${normalized}:`) ||
      lowered.startsWith(`hello ${normalized}`) ||
      lowered.startsWith(`hey ${normalized}`) ||
      lowered.startsWith(`hi ${normalized}`)
    );
  });
}

function normalizeTranscript(text: string): string {
  return text
    .trim()
    .replace(/[.?!]+$/g, "")
    .replace(/\s+/g, " ");
}

function scoreTranscriptCandidate(text: string, confidence: number, config: VoiceConfig): number {
  const normalized = normalizeTranscript(text).toLowerCase();
  let score = confidence || 0;

  if (startsWithWakeWord(normalized, config.wakeWords)) {
    score += 3;
  }

  for (const hint of COMMAND_HINTS) {
    if (normalized.includes(hint)) {
      score += 0.5;
    }
  }

  if (normalized.length >= 4) {
    score += 0.2;
  }

  return score;
}

function pickBestTranscript(result: any, config: VoiceConfig): string {
  const candidates: Array<{ text: string; score: number }> = [];

  for (let i = 0; i < result.length; i++) {
    const alternative = result[i];
    const text = normalizeTranscript(String(alternative?.transcript || ""));
    if (!text) continue;
    candidates.push({
      text,
      score: scoreTranscriptCandidate(text, Number(alternative?.confidence || 0), config),
    });
  }

  candidates.sort((a, b) => b.score - a.score);
  return candidates[0]?.text || "";
}

export function createVoiceInput(
  onTranscript: (text: string) => void,
  onError: (msg: string) => void,
  getConfig: () => VoiceConfig
): VoiceInput {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SR = (window as any).SpeechRecognition || (typeof webkitSpeechRecognition !== "undefined" ? webkitSpeechRecognition : null);
  if (!SR) {
    onError("Speech recognition not supported in this browser");
    return { start() {}, stop() {}, pause() {}, resume() {}, setLanguage() {} };
  }

  const recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 5;
  recognition.lang = getConfig().language;

  let shouldListen = false;
  let paused = false;
  let lastAcceptedTranscript = "";
  let lastAcceptedAt = 0;

  recognition.onresult = (event: any) => {
    const config = getConfig();

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      if (!result.isFinal) continue;

      const text = pickBestTranscript(result, config);
      if (!text || text.length < 2) continue;

      const normalized = text.toLowerCase();
      if (normalized === lastAcceptedTranscript && Date.now() - lastAcceptedAt < 2000) {
        continue;
      }

      if (config.requireWakeWord && !startsWithWakeWord(text, config.wakeWords)) {
        continue;
      }

      lastAcceptedTranscript = normalized;
      lastAcceptedAt = Date.now();
      onTranscript(text);
    }
  };

  recognition.onend = () => {
    if (shouldListen && !paused) {
      try {
        recognition.start();
      } catch {
        // Already started
      }
    }
  };

  recognition.onerror = (event: any) => {
    if (event.error === "not-allowed") {
      onError("Microphone access denied. Please allow microphone access.");
      shouldListen = false;
    } else if (event.error === "service-not-allowed") {
      onError("Speech recognition is blocked in this browser. Please use Chrome and allow microphone access.");
      shouldListen = false;
    } else if (event.error === "no-speech") {
      // Normal, just restart
    } else if (event.error === "aborted") {
      // Expected during pause
    } else {
      console.warn("[voice] recognition error:", event.error);
    }
  };

  return {
    start() {
      shouldListen = true;
      paused = false;
      try {
        recognition.lang = getConfig().language;
        recognition.start();
      } catch {
        // Already started
      }
    },
    stop() {
      shouldListen = false;
      paused = false;
      recognition.stop();
    },
    pause() {
      paused = true;
      recognition.stop();
    },
    resume() {
      paused = false;
      if (shouldListen) {
        try {
          recognition.lang = getConfig().language;
          recognition.start();
        } catch {
          // Already started
        }
      }
    },
    setLanguage(language: string) {
      recognition.lang = language;
      if (shouldListen && !paused) {
        recognition.stop();
      }
    },
  };
}

export interface AudioPlayer {
  enqueue(base64: string): Promise<void>;
  stop(): void;
  getAnalyser(): AnalyserNode;
  onFinished(cb: () => void): void;
}

export function createAudioPlayer(): AudioPlayer {
  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.8;
  analyser.connect(audioCtx.destination);

  const queue: AudioBuffer[] = [];
  let isPlaying = false;
  let currentSource: AudioBufferSourceNode | null = null;
  let finishedCallback: (() => void) | null = null;

  function playNext() {
    if (queue.length === 0) {
      isPlaying = false;
      currentSource = null;
      finishedCallback?.();
      return;
    }

    isPlaying = true;
    const buffer = queue.shift()!;
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    currentSource = source;

    source.onended = () => {
      if (currentSource === source) {
        playNext();
      }
    };

    source.start();
  }

  return {
    async enqueue(base64: string) {
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      try {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer.slice(0));
        queue.push(audioBuffer);
        if (!isPlaying) playNext();
      } catch (err) {
        console.error("[audio] decode error:", err);
        if (!isPlaying && queue.length > 0) playNext();
      }
    },

    stop() {
      queue.length = 0;
      if (currentSource) {
        try {
          currentSource.stop();
        } catch {
          // Already stopped
        }
        currentSource = null;
      }
      isPlaying = false;
    },

    getAnalyser() {
      return analyser;
    },

    onFinished(cb: () => void) {
      finishedCallback = cb;
    },
  };
}
