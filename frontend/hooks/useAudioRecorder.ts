/**
 * useAudioRecorder
 *
 * Full-session audio recorder for interview sessions.
 * Records the entire interview as a single continuous .webm file,
 * then uploads it to Supabase Storage on completion.
 *
 * This is SEPARATE from the per-chunk recorder in useVoiceInterview.
 * That recorder sends chunks to the WebSocket for STT.
 * This recorder captures everything for persistent storage.
 */

"use client";

import { useCallback, useRef, useState } from "react";
import { createSupabaseClient } from "@/lib/supabase/client";

// ─── Types ─────────────────────────────────────────────────────────────

export interface AudioRecorderState {
  isRecording: boolean;
  hasAudio: boolean;       // true after stop (blob exists)
  isUploading: boolean;
  uploadProgress: number;  // 0–100
  audioUrl: string | null; // Supabase public URL after upload
  error: string | null;
}

export interface AudioRecorderActions {
  startFullSession: (stream: MediaStream) => void;
  stopFullSession: () => void;
  uploadToSupabase: (interviewId: string) => Promise<string | null>;
  getBlob: () => Blob | null;
}

// ─── Constants ─────────────────────────────────────────────────────────

const STORAGE_BUCKET = "interview-audios";
const CHUNK_INTERVAL_MS = 1000; // Collect data every second

// ─── Hook ──────────────────────────────────────────────────────────────

export function useAudioRecorder(): AudioRecorderState & AudioRecorderActions {
  const [isRecording, setIsRecording] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const blobRef = useRef<Blob | null>(null);

  // ── Start full-session recording ─────────────────────────────────────

  const startFullSession = useCallback((stream: MediaStream) => {
    if (mediaRecorderRef.current) return; // Already recording

    try {
      // Pick best supported format
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      blobRef.current = null;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        if (chunksRef.current.length > 0) {
          const blob = new Blob(chunksRef.current, { type: mimeType });
          blobRef.current = blob;
          setHasAudio(true);
          console.log(
            `🎤 Full session recorded: ${(blob.size / 1024 / 1024).toFixed(2)} MB`
          );
        }
        mediaRecorderRef.current = null;
      };

      recorder.onerror = (e) => {
        console.error("❌ MediaRecorder error:", e);
        setError("Recording error occurred");
      };

      recorder.start(CHUNK_INTERVAL_MS);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setError(null);
      console.log("🎤 Full-session recording started");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start recording";
      console.error("❌ Failed to start full-session recording:", err);
      setError(msg);
    }
  }, []);

  // ── Stop full-session recording ──────────────────────────────────────

  const stopFullSession = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      console.log("🛑 Full-session recording stopped");
    }
  }, []);

  // ── Upload to Supabase Storage ───────────────────────────────────────

  const uploadToSupabase = useCallback(
    async (interviewId: string): Promise<string | null> => {
      // Wait for MediaRecorder onstop to finalize the blob (up to 3s)
      let waitAttempts = 0;
      const MAX_WAIT_ATTEMPTS = 15; // 15 × 200ms = 3s
      while (!blobRef.current && waitAttempts < MAX_WAIT_ATTEMPTS) {
        console.log(`⏳ Waiting for audio blob to finalize (${waitAttempts + 1}/${MAX_WAIT_ATTEMPTS})...`);
        await new Promise((resolve) => setTimeout(resolve, 200));
        waitAttempts++;
      }

      const blob = blobRef.current;
      if (!blob) {
        console.warn("⚠️ No audio blob to upload after waiting");
        return null;
      }

      if (blob.size < 1000) {
        console.warn("⚠️ Audio blob too small to upload:", blob.size, "bytes");
        return null;
      }

      setIsUploading(true);
      setUploadProgress(10);
      setError(null);

      try {
        const supabase = createSupabaseClient();
        const fileName = `interview_${interviewId}_${Date.now()}.webm`;
        const filePath = `interviews/${fileName}`;

        console.log(`📤 Uploading ${(blob.size / 1024 / 1024).toFixed(2)} MB to Supabase Storage...`);
        setUploadProgress(30);

        // Upload to Supabase Storage
        const { data: uploadData, error: uploadError } = await supabase.storage
          .from(STORAGE_BUCKET)
          .upload(filePath, blob, {
            contentType: "audio/webm",
            upsert: false,
          });

        if (uploadError) {
          throw new Error(`Storage upload failed: ${uploadError.message}`);
        }

        setUploadProgress(70);

        // Get public URL
        const { data: urlData } = supabase.storage
          .from(STORAGE_BUCKET)
          .getPublicUrl(filePath);

        const publicUrl = urlData.publicUrl;
        console.log("✅ Audio uploaded:", publicUrl);

        setUploadProgress(85);

        // Update interview record with audio metadata
        const { error: updateError } = await supabase
          .from("interviews")
          .update({
            audio_storage_path: filePath,
            audio_public_url: publicUrl,
            audio_file_size_bytes: blob.size,
            audio_duration_seconds: Math.round(chunksRef.current.length), // ~1 chunk/sec
            recording_stopped_at: new Date().toISOString(),
          })
          .eq("id", interviewId);

        if (updateError) {
          console.warn("⚠️ Failed to update interview record with audio URL:", updateError);
          // Non-fatal — the audio is still in storage
        }

        setUploadProgress(100);
        setAudioUrl(publicUrl);
        return publicUrl;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        console.error("❌ Audio upload failed:", err);
        setError(msg);
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    []
  );

  // ── Get raw blob ─────────────────────────────────────────────────────

  const getBlob = useCallback((): Blob | null => {
    return blobRef.current;
  }, []);

  // ── Return ───────────────────────────────────────────────────────────

  return {
    // State
    isRecording,
    hasAudio,
    isUploading,
    uploadProgress,
    audioUrl,
    error,
    // Actions
    startFullSession,
    stopFullSession,
    uploadToSupabase,
    getBlob,
  };
}
