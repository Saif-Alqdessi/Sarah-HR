/**
 * useVoiceInterview
 *
 * Full-duplex voice interview hook for the Sarah AI HR system.
 *
 * Pipeline (per turn):
 *   Browser mic → MediaRecorder → base64 → WebSocket →
 *   Groq STT → LangGraph → ElevenLabs TTS →
 *   WebSocket → base64 → AudioContext queue → Speaker
 *
 * Exposed state:
 *   isConnecting  — WebSocket handshake in progress
 *   isConnected   — WebSocket is open
 *   isSpeaking    — Sarah's audio is playing right now
 *   isListening   — User's mic is active (above VAD threshold)
 *   transcript    — Ordered array of {role, text} turns
 *   currentStage  — Interview stage from server metadata
 *   turnCount     — How many turns have completed
 *   error         — Last error string (or null)
 *
 * Exposed actions:
 *   start(candidateId)  — Open WebSocket + request mic
 *   stop()              — Send {type:"end"}, close everything
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface TranscriptLine {
  role: "Sarah" | "You";
  text: string;
  timestamp: number;
}

export type InterviewStage =
  | "opening"
  | "experience_probe"
  | "credibility_check"
  | "closing"
  | "unknown";

export interface VoiceInterviewState {
  isConnecting: boolean;
  isConnected: boolean;
  isSpeaking: boolean;   // Sarah is currently playing audio
  isListening: boolean;  // Mic is recording (user is speaking)
  isCompleted: boolean;  // Server sent interview_complete signal
  transcript: TranscriptLine[];
  currentStage: InterviewStage;
  turnCount: number;
  error: string | null;
}

export interface VoiceInterviewActions {
  start: (candidateId: string) => Promise<void>;
  stop: () => void;
  getStream: () => MediaStream | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  process.env.NEXT_PUBLIC_API_URL?.replace(/^http/, "ws") ||
  "ws://localhost:8001";

/** RMS amplitude below this value = silence */
const VAD_SILENCE_THRESHOLD = 18;

/** ms of continuous silence before we stop the current recording chunk */
const VAD_SILENCE_DURATION_MS = 1200;

/** Minimum ms a recording chunk must be before we bother sending it */
const MIN_CHUNK_DURATION_MS = 400;

/** FFT size for the AnalyserNode (power of 2) */
const ANALYSER_FFT_SIZE = 512;

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useVoiceInterview(): VoiceInterviewState & VoiceInterviewActions {
  // ── UI State ──────────────────────────────────────────────────────────────
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [currentStage, setCurrentStage] = useState<InterviewStage>("opening");
  const [turnCount, setTurnCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState(false);

  // ── Refs (survive re-renders, no re-render on change) ────────────────────
  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const vadAnalyserRef = useRef<AnalyserNode | null>(null);
  const vadAudioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);  // requestAnimationFrame ID
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chunkStartRef = useRef<number>(0);
  const isRecordingRef = useRef(false);
  const isSpeakingRef = useRef(false);  // mirrors isSpeaking without stale closure

  // ── Audio Playback Queue ──────────────────────────────────────────────────
  // Each Sarah response becomes one entry. We play them serially.
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);

  // ─── Audio Queue Player ─────────────────────────────────────────────────────

  const playNextInQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;
    isSpeakingRef.current = true;
    setIsSpeaking(true);

    const buffer = audioQueueRef.current.shift()!;

    try {
      // Lazily create AudioContext (browser requires user gesture first)
      if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
        audioCtxRef.current = new (window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext })
            .webkitAudioContext)();
      }

      const ctx = audioCtxRef.current;

      // Resume if suspended (autoplay policy)
      if (ctx.state === "suspended") {
        await ctx.resume();
      }

      const decoded = await ctx.decodeAudioData(buffer);
      const source = ctx.createBufferSource();
      source.buffer = decoded;
      source.connect(ctx.destination);

      source.onended = () => {
        isPlayingRef.current = false;
        isSpeakingRef.current = false;
        setIsSpeaking(false);
        // Play next item if any
        playNextInQueue();
      };

      source.start(0);
    } catch (err) {
      console.error("❌ Audio playback error:", err);
      isPlayingRef.current = false;
      isSpeakingRef.current = false;
      setIsSpeaking(false);
      // Still try the next one
      playNextInQueue();
    }
  }, []);

  /**
   * Decode a base64 audio string and enqueue it for playback.
   * Keeps playback in order even if multiple packets arrive quickly.
   */
  const enqueueAudio = useCallback(
    (base64: string) => {
      try {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        audioQueueRef.current.push(bytes.buffer);
        playNextInQueue();
      } catch (err) {
        console.error("❌ Failed to decode audio:", err);
      }
    },
    [playNextInQueue]
  );

  // ─── Recording Helpers ──────────────────────────────────────────────────────

  const startRecording = useCallback(() => {
    // Guard BEFORE creating the recorder so we don't create a new instance
    // while already recording.
    if (isRecordingRef.current || !streamRef.current) return;

    mediaRecorderRef.current = new MediaRecorder(streamRef.current, {
      mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm",
    });

    const chunks: BlobPart[] = [];
    chunkStartRef.current = Date.now();

    mediaRecorderRef.current.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    mediaRecorderRef.current.onstop = async () => {
      const duration = Date.now() - chunkStartRef.current;
      if (duration < MIN_CHUNK_DURATION_MS || chunks.length === 0) {
        return; // Too short — likely noise, skip
      }

      const blob = new Blob(chunks, { type: "audio/webm" });

      // Convert to base64
      const reader = new FileReader();
      reader.onloadend = () => {
        const dataUrl = reader.result as string;
        const base64 = dataUrl.split(",")[1];

        if (
          wsRef.current &&
          wsRef.current.readyState === WebSocket.OPEN
        ) {
          wsRef.current.send(
            JSON.stringify({ type: "audio", data: base64 })
          );
          console.log("📤 Audio chunk sent to server");

          // Optimistic placeholder for user speech
          setTranscript((prev) => [
            ...prev,
            { role: "You", text: "…", timestamp: Date.now() },
          ]);
        }
      };
      reader.readAsDataURL(blob);
    };

    mediaRecorderRef.current.start();
    isRecordingRef.current = true;
    setIsListening(true);
    console.log("🎙️ Recording started");
  }, []);

  const stopRecording = useCallback(() => {
    if (!isRecordingRef.current || !mediaRecorderRef.current) return;
    if (mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    isRecordingRef.current = false;
    setIsListening(false);
    console.log("🛑 Recording stopped");
  }, []);

  // ─── Voice Activity Detection ───────────────────────────────────────────────

  const setupVAD = useCallback(
    (stream: MediaStream) => {
      // Use a dedicated AudioContext for VAD so it doesn't conflict with playback
      const vadCtx = new AudioContext();
      vadAudioCtxRef.current = vadCtx;

      const analyser = vadCtx.createAnalyser();
      analyser.fftSize = ANALYSER_FFT_SIZE;
      vadAnalyserRef.current = analyser;

      const source = vadCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const buffer = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        // Don't record while Sarah is speaking (echo prevention)
        if (isSpeakingRef.current) {
          if (isRecordingRef.current) stopRecording();
          rafRef.current = requestAnimationFrame(tick);
          return;
        }

        analyser.getByteFrequencyData(buffer);
        const rms =
          buffer.reduce((sum, v) => sum + v, 0) / buffer.length;

        if (!isRecordingRef.current) {
          // Start recording when voice detected
          if (rms > VAD_SILENCE_THRESHOLD) {
            startRecording();
          }
        } else {
          // Silence detected → start/reset the silence timer
          if (rms <= VAD_SILENCE_THRESHOLD) {
            if (!silenceTimerRef.current) {
              silenceTimerRef.current = setTimeout(() => {
                stopRecording();
                silenceTimerRef.current = null;
              }, VAD_SILENCE_DURATION_MS);
            }
          } else {
            // Sound resumed — cancel silence timer
            if (silenceTimerRef.current) {
              clearTimeout(silenceTimerRef.current);
              silenceTimerRef.current = null;
            }
          }
        }

        rafRef.current = requestAnimationFrame(tick);
      };

      rafRef.current = requestAnimationFrame(tick);
    },
    [startRecording, stopRecording]
  );

  // ─── WebSocket Message Handler ──────────────────────────────────────────────

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        // Guard: skip binary messages (raw audio chunks)
        if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
          return;
        }

        const msg = JSON.parse(event.data as string);
        console.log("📥 WS message:", msg.type, msg.metadata || "");

        switch (msg.type) {
          case "audio": {
            // Play Sarah's response — validate data is a base64 string
            if (msg.data && typeof msg.data === "string" && msg.data.length > 100) {
              enqueueAudio(msg.data as string);
            }
            // Update transcript and stage metadata
            if (msg.metadata?.text) {
              setTranscript((prev) => [
                ...prev,
                {
                  role: "Sarah",
                  text: msg.metadata.text as string,
                  timestamp: Date.now(),
                },
              ]);
            }
            if (msg.metadata?.stage) {
              setCurrentStage(msg.metadata.stage as InterviewStage);
            }
            if (typeof msg.metadata?.turn === "number") {
              setTurnCount(msg.metadata.turn);
            }
            break;
          }

          case "transcript": {
            // Server confirmed user transcript — replace the "…" placeholder
            if (msg.text) {
              setTranscript((prev) => {
                const updated = [...prev];
                // Find the last "You" placeholder and replace
                for (let i = updated.length - 1; i >= 0; i--) {
                  if (updated[i].role === "You" && updated[i].text === "…") {
                    updated[i] = {
                      ...updated[i],
                      text: msg.text as string,
                    };
                    break;
                  }
                }
                return updated;
              });
            }
            break;
          }

          case "status": {
            if (msg.status === "completed") {
              console.log("✅ Interview marked completed by server");
            }
            break;
          }

          case "interview_complete": {
            console.log("🏁 Interview completed by server:", msg);
            setIsCompleted(true);
            setCurrentStage("closing");
            if (typeof msg.total_turns === "number") {
              setTurnCount(msg.total_turns);
            }
            // Auto-stop mic/VAD/WS (server will close WS in 2s anyway)
            // We delay slightly so the last TTS can finish playing
            setTimeout(() => {
              stop();
            }, 3000);
            break;
          }

          case "text_fallback": {
            // TTS failed on server — display text only
            if (msg.text) {
              setTranscript((prev) => [
                ...prev,
                { role: "Sarah", text: msg.text as string, timestamp: Date.now() },
              ]);
            }
            break;
          }

          case "error": {
            const errMsg = (msg.message as string) || "Server error";
            console.error("❌ Server error:", errMsg);
            setError(errMsg);
            break;
          }

          default:
            console.log("ℹ️ Unknown message type:", msg.type);
        }
      } catch (err) {
        console.error("❌ Failed to parse WebSocket message:", err);
      }
    },
    [enqueueAudio]
  );

  // ─── Main Actions ───────────────────────────────────────────────────────────

  const start = useCallback(
    async (candidateId: string) => {
      if (wsRef.current) return; // Already connected
      setError(null);
      setIsConnecting(true);
      setTranscript([]);
      setTurnCount(0);
      setCurrentStage("opening");

      // 1. Request microphone access first (so we fail fast if denied)
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 16000,
          },
        });
        streamRef.current = stream;
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Microphone access denied";
        setError(msg);
        setIsConnecting(false);
        console.error("❌ Mic error:", err);
        return;
      }

      // 2. Open WebSocket
      const url = `${WS_BASE_URL}/ws/interview/${candidateId}`;
      console.log("🔌 Connecting to:", url);

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("✅ WebSocket open");
        setIsConnecting(false);
        setIsConnected(true);
        // Start VAD — Sarah's opening message will arrive and play automatically
        setupVAD(stream);
      };

      ws.onmessage = handleMessage;

      ws.onerror = (evt) => {
        console.error("❌ WebSocket error:", evt);
        setError("WebSocket connection error. Is the backend running?");
        setIsConnecting(false);
        setIsConnected(false);
      };

      ws.onclose = (evt) => {
        console.log(
          `🔌 WebSocket closed. Code: ${evt.code} Reason: ${evt.reason || "none"}`
        );
        wsRef.current = null;
        setIsConnected(false);
        setIsListening(false);
        setIsSpeaking(false);
      };
    },
    [handleMessage, setupVAD]
  );

  const stop = useCallback(() => {
    // 1. Tell server we're done
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end" }));
      wsRef.current.close();
    }
    wsRef.current = null;

    // 2. Stop VAD loop
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }

    // 3. Stop recording
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current?.stop();
    }
    isRecordingRef.current = false;

    // 4. Stop microphone tracks
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    // 5. Close audio contexts
    vadAudioCtxRef.current?.close();
    vadAudioCtxRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;

    // 6. Clear queue
    audioQueueRef.current = [];
    isPlayingRef.current = false;

    // 7. Reset UI state
    setIsConnected(false);
    setIsConnecting(false);
    setIsListening(false);
    setIsSpeaking(false);
  }, []);

  // ─── Cleanup on unmount ─────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      // Only send 'end' + close if we actually have an open session.
      // React Strict Mode mounts → unmounts → remounts every component in dev;
      // without this guard the synthetic unmount fires stop() immediately and
      // the server receives {type:"end"} before any audio is sent.
      if (wsRef.current) {
        stop();
      }
    };
  }, [stop]);

  // ─── Return ─────────────────────────────────────────────────────────────────

  return {
    // State
    isConnecting,
    isConnected,
    isSpeaking,
    isListening,
    isCompleted,
    transcript,
    currentStage,
    turnCount,
    error,
    // Actions
    start,
    stop,
    getStream: useCallback(() => streamRef.current, []),
  };
}
