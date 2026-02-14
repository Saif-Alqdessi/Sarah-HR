"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createSupabaseClient } from "@/lib/supabase/client";
import { toast } from "sonner";

interface RegistrationForm {
  full_name_ar?: string;
  years_of_experience?: string;
  expected_salary?: string;
  has_field_experience?: string;
  proximity_to_branch?: string;
  academic_status?: string;
  can_start_immediately?: string;
  prayer_regularity?: string;
  is_smoker?: string;
  registration_form_data?: any;
}

interface Inconsistency {
  type: string;
  form_value: string;
  interview_value: string;
  severity: string;
  description: string;
}

interface Candidate {
  id: string;
  full_name: string;
  phone_number: string;
  email?: string;
  target_role: string;
  registration_form?: RegistrationForm;
}

export default function InterviewPage() {
  const params = useParams();
  const router = useRouter();
  const candidateId = params?.candidateId as string;
  const interviewIdRef = useRef<string | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [callStatus, setCallStatus] = useState<
    "ready" | "recording" | "processing" | "completed" | "analyzing"
  >("ready");
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>(
    []
  );
  const [error, setError] = useState<string | null>(null);
  const [interviewId, setInterviewId] = useState<string | null>(null);
  const [detectedInconsistencies, setDetectedInconsistencies] = useState<Inconsistency[]>([]);
  const [showInconsistencyAlert, setShowInconsistencyAlert] = useState(false);
  
  // Audio recording refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Fetch candidate from Supabase
  useEffect(() => {
    async function fetchCandidate() {
      if (!candidateId) return;
      try {
        const supabase = createSupabaseClient();
        const { data, error } = await supabase
          .from("candidates")
          .select(
            "id, full_name, phone_number, email, target_role, " +
            "full_name_ar, years_of_experience, expected_salary, " +
            "has_field_experience, proximity_to_branch, academic_status, " +
            "can_start_immediately, prayer_regularity, is_smoker, registration_form_data"
          )
          .eq("id", candidateId)
          .single();

        if (error) throw error;
        if (!data) throw new Error("Candidate not found");
        setCandidate(data as Candidate);
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Failed to load candidate";
        setError(msg);
        toast.error(msg);
      } finally {
        setIsLoading(false);
      }
    }
    fetchCandidate();
  }, [candidateId]);

  // Initialize audio context (client-side only)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    
    return () => {
      // Clean up any active recording on unmount
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const startRecording = async () => {
    if (!candidate) return;
    setError(null);
    
    try {
      // Request microphone access
      let micStream: MediaStream | null = null;
      try {
        micStream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true
          } 
        });
      } catch (micErr) {
        const msg = micErr instanceof Error ? micErr.message : "Microphone access denied";
        setCallStatus("ready");
        setError("Microphone access is required. Please allow the microphone and try again.");
        toast.error("Please allow microphone access");
        return;
      }
      
      // Initialize the interview session
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const startRes = await fetch(`${apiUrl}/api/interview/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidate.id }),
      });
      const startData = await startRes.json();
      if (startData.interview_id) {
        setInterviewId(startData.interview_id);
        interviewIdRef.current = startData.interview_id;
      }
      
      // Start recording
      mediaRecorderRef.current = new MediaRecorder(micStream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await processAudio(audioBlob);
      };
      
      mediaRecorderRef.current.start();
      setCallStatus("recording");
      toast.success("Recording started");
      
      // Auto-stop after 10 seconds (or add manual stop button)
      setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          stopRecording();
        }
      }, 10000);
      
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start recording";
      setCallStatus("ready");
      setError(msg);
      toast.error(msg);
    }
  };
  
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      setCallStatus("processing");
      toast.info("Processing audio...");
    }
  };
  
  const processAudio = async (audioBlob: Blob) => {
    try {
      // Step 1: Transcribe with Groq Whisper
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const transcribeResponse = await fetch(`${apiUrl}/api/transcribe`, {
        method: 'POST',
        body: formData
      });
      
      const transcribeData = await transcribeResponse.json();
      const userText = transcribeData.text;
      
      console.log('✅ Transcription:', userText);
      setTranscript(prev => [...prev, { role: "You", text: userText }]);
      
      // Step 2: Get intelligent response from agent
      const agentResponse = await fetch(`${apiUrl}/api/agent-response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: {
            type: 'conversation-update',
            call: {
              assistantOverrides: {
                variableValues: {
                  candidate_name: candidate.full_name,
                  target_role: candidate.target_role,
                  candidate_id: candidate.id
                }
              }
            },
            transcript: [
              ...transcript.map(t => ({ role: t.role === "You" ? "user" : "assistant", content: t.text })),
              { role: "user", content: userText }
            ]
          }
        })
      });
      
      const agentData = await agentResponse.json();
      const sarahResponse = agentData.assistant?.say || "I'm sorry, I didn't catch that.";
      
      // Check for inconsistencies
      if (agentData.detected_inconsistencies && agentData.detected_inconsistencies.length > 0) {
        const newInconsistency = agentData.detected_inconsistencies[agentData.detected_inconsistencies.length - 1];
        setDetectedInconsistencies(prev => [...prev, newInconsistency]);
        setShowInconsistencyAlert(true);
        
        // Auto-hide the alert after 5 seconds
        setTimeout(() => {
          setShowInconsistencyAlert(false);
        }, 5000);
      }
      
      console.log('✅ Sarah:', sarahResponse);
      setTranscript(prev => [...prev, { role: "Sara", text: sarahResponse }]);
      
      // Step 3: Convert to speech with ElevenLabs
      await speakText(sarahResponse);
      
      setCallStatus("ready");
      
    } catch (error) {
      console.error('Error processing audio:', error);
      setCallStatus("ready");
      setError("Failed to process audio. Please try again.");
      toast.error("Processing failed");
    }
  };
  
  const speakText = async (text: string) => {
    try {
      const elevenlabsApiKey = process.env.NEXT_PUBLIC_ELEVENLABS_API_KEY;
      if (!elevenlabsApiKey) {
        console.error("Missing ElevenLabs API key");
        return;
      }
      
      const response = await fetch('https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB', {
        method: 'POST',
        headers: {
          'xi-api-key': elevenlabsApiKey,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: text,
          model_id: 'eleven_multilingual_v2',
          voice_settings: {
            stability: 0.65,
            similarity_boost: 0.85
          }
        })
      });
      
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      
      const audio = new Audio(audioUrl);
      await audio.play();
      
    } catch (error) {
      console.error('Error playing audio:', error);
    }
  };
  
  const endInterview = () => {
    setCallStatus("analyzing");
    toast.success("Interview completed. Thank you!");
    const ANALYSIS_DELAY_MS = 7000;
    setTimeout(() => router.push("/interview/complete"), ANALYSIS_DELAY_MS);
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-amber-50 to-white flex items-center justify-center p-8">
        <div className="animate-pulse text-amber-700">Loading...</div>
      </main>
    );
  }

  if (error && !candidate) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-amber-50 to-white flex items-center justify-center p-8">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => router.push("/apply")}
            className="text-amber-600 hover:underline"
          >
            Return to application
          </button>
        </div>
      </main>
    );
  }

  // Registration Context Panel Component
  const RegistrationContextPanel = ({ registrationForm }: { registrationForm?: RegistrationForm }) => {
    if (!registrationForm) return null;
    
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <h3 className="text-sm font-semibold text-blue-800 mb-3 flex items-center">
          <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2-1a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V4a1 1 0 00-1-1H6z" clipRule="evenodd" />
          </svg>
          📋 بيانات الطلب الإلكتروني
        </h3>
        
        <div className="grid grid-cols-2 gap-3 text-sm">
          {registrationForm.years_of_experience && (
            <div>
              <span className="text-gray-600">الخبرة:</span>{' '}
              <span className="font-medium">{registrationForm.years_of_experience}</span>
            </div>
          )}
          
          {registrationForm.expected_salary && (
            <div>
              <span className="text-gray-600">الراتب المتوقع:</span>{' '}
              <span className="font-medium">{registrationForm.expected_salary}</span>
            </div>
          )}
          
          {registrationForm.proximity_to_branch && (
            <div className="col-span-2">
              <span className="text-gray-600">قرب السكن:</span>{' '}
              <span className="font-medium">{registrationForm.proximity_to_branch}</span>
            </div>
          )}
          
          {registrationForm.has_field_experience && (
            <div>
              <span className="text-gray-600">خبرة بالمجال:</span>{' '}
              <span className="font-medium">{registrationForm.has_field_experience}</span>
            </div>
          )}
          
          {registrationForm.can_start_immediately && (
            <div>
              <span className="text-gray-600">البدء فوراً:</span>{' '}
              <span className="font-medium">{registrationForm.can_start_immediately}</span>
            </div>
          )}
        </div>
        
        <div className="mt-3 text-xs text-blue-700">
          💡 سارة ستشير لهذه البيانات أثناء المقابلة
        </div>
      </div>
    );
  };
  
  // Inconsistency Alert Component
  const InconsistencyAlert = ({ inconsistency }: { inconsistency?: Inconsistency }) => {
    if (!inconsistency || !showInconsistencyAlert) return null;
    
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-4 animate-pulse">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="mr-3">
            <p className="text-sm text-red-700">
              <span className="font-bold">تناقض محتمل:</span> {inconsistency.description}
            </p>
            <p className="text-xs text-red-600 mt-1">
              في الطلب: {inconsistency.form_value} | في المقابلة: {inconsistency.interview_value}
            </p>
          </div>
        </div>
      </div>
    );
  };
  
  return (
    <main className="min-h-screen bg-gradient-to-b from-amber-50 to-white">
      <div className="mx-auto max-w-2xl px-6 py-8 sm:py-12">
        <div className="rounded-2xl bg-white p-6 shadow-lg ring-1 ring-amber-100 sm:p-8">
          <h1 className="text-2xl font-bold text-amber-900">
            Voice AI Interview
          </h1>
          <p className="mt-2 text-amber-700/80">
            Hi{candidate ? `, ${candidate.full_name}` : ""}! Ready for your{" "}
            {candidate?.target_role?.replace("_", " ") || "position"} interview
            with Sara.
          </p>
          
          {/* Registration Context Panel */}
          <div className="mt-6">
            <RegistrationContextPanel registrationForm={candidate?.registration_form} />
          </div>
          
          {/* Inconsistency Alert */}
          {detectedInconsistencies.length > 0 && (
            <InconsistencyAlert inconsistency={detectedInconsistencies[detectedInconsistencies.length - 1]} />
          )}

          {/* Call controls */}
          <div className="mt-8 flex flex-col items-center gap-4">
            {callStatus === "ready" && (
              <button
                onClick={startRecording}
                className="flex h-20 w-20 items-center justify-center rounded-full bg-green-500 text-white shadow-lg transition hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50"
                aria-label="Start recording"
              >
                <svg
                  className="h-10 w-10"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z" />
                </svg>
              </button>
            )}
            {callStatus === "recording" && (
              <button
                onClick={stopRecording}
                className="flex h-20 w-20 items-center justify-center rounded-full bg-red-500 text-white shadow-lg transition hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50"
                aria-label="Stop recording"
              >
                <svg
                  className="h-10 w-10"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M6 6h12v12H6z" />
                </svg>
              </button>
            )}
            {transcript.length > 0 && callStatus === "ready" && (
              <button
                onClick={endInterview}
                className="mt-4 rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
              >
                End Interview
              </button>
            )}
            {callStatus === "analyzing" && (
              <div className="flex flex-col items-center gap-3">
                <div className="h-12 w-12 animate-spin rounded-full border-4 border-amber-200 border-t-amber-600" aria-hidden />
                <p className="text-sm font-medium text-amber-800">AI Analysis in progress</p>
                <p className="text-xs text-amber-600/80">Saving your results… redirecting in a few seconds</p>
              </div>
            )}
            <p className="text-sm text-amber-600/80">
              {callStatus === "ready" && transcript.length === 0 && "Ready to Start — Tap to begin"}
              {callStatus === "ready" && transcript.length > 0 && "Ready for next question — Tap to speak"}
              {callStatus === "recording" && "Recording... (auto-stops after 10s)"}
              {callStatus === "processing" && "Processing your response..."}
              {callStatus === "analyzing" && ""}
              {callStatus === "completed" && "Completed — Redirecting..."}
            </p>
          </div>

          {/* Transcript */}
          {transcript.length > 0 && (
            <div className="mt-8 border-t border-amber-200 pt-6">
              <h2 className="text-sm font-semibold text-amber-900">
                Live transcript
              </h2>
              <div className="mt-3 max-h-60 space-y-2 overflow-y-auto">
                {transcript.map((line, i) => (
                  <div
                    key={i}
                    className={`rounded-lg px-3 py-2 text-sm ${
                      line.role === "You"
                        ? "ml-4 bg-amber-100 text-amber-900"
                        : "mr-4 bg-amber-50 text-amber-800"
                    }`}
                  >
                    <span className="font-medium">{line.role}:</span> {line.text}
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && callStatus === "ready" && (
            <p className="mt-4 text-center text-sm text-red-600">{error}</p>
          )}
        </div>

        <p className="mt-6 text-center text-sm text-amber-600/70">
          Allow microphone access when prompted. The interview is about 3–5
          minutes.
        </p>
      </div>
    </main>
  );
}
