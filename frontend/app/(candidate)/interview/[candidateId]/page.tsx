"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createSupabaseClient } from "@/lib/supabase/client";
import { toast } from "sonner";
import Vapi from "@vapi-ai/web";



interface RegistrationForm {
  full_name?: string;
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
    "ready" | "live" | "processing" | "completed" | "analyzing"
  >("ready");
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>(
    []
  );
  const [error, setError] = useState<string | null>(null);
  const [interviewId, setInterviewId] = useState<string | null>(null);
  const [detectedInconsistencies, setDetectedInconsistencies] = useState<Inconsistency[]>([]);
  const [showInconsistencyAlert, setShowInconsistencyAlert] = useState(false);
  const [registrationForm, setRegistrationForm] = useState<any>(null);
  const [loadingContext, setLoadingContext] = useState(true);
  
  // Vapi refs
  const vapiCallRef = useRef<any>(null);
  const vapiAssistantIdRef = useRef<string>(process.env.NEXT_PUBLIC_VAPI_ASSISTANT_ID || "");
  const vapiApiKeyRef = useRef<string>(process.env.NEXT_PUBLIC_VAPI_PUBLIC_KEY || "");
  const vapiContainerRef = useRef<HTMLDivElement>(null);

  // Fetch registration context from the new endpoint
  useEffect(() => {
    const fetchRegistrationContext = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
        const response = await fetch(`${apiUrl}/api/candidates/${params.candidateId}/registration-context`);
        if (response.ok) {
          const data = await response.json();
          setRegistrationForm(data);
          console.log('✅ Loaded registration context:', data);
        }
      } catch (error) {
        console.error('Error loading registration context:', error);
      } finally {
        setLoadingContext(false);
      }
    };

    fetchRegistrationContext();
  }, [params.candidateId]);

  // Fetch candidate from backend API instead of direct Supabase query
  useEffect(() => {
    async function fetchCandidate() {
      if (!candidateId) return;
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
        const response = await fetch(`${apiUrl}/api/candidates/${candidateId}`, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Candidate not found");
          } else if (response.status === 504) {
            throw new Error("Request timed out. Please try again.");
          } else {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Error ${response.status}: Failed to load candidate`);
          }
        }
        
        const data = await response.json();
        
        // Map registration form fields to the expected structure
        const candidate = {
          ...data,
          registration_form: {
            full_name: data.full_name,
            years_of_experience: data.years_of_experience,
            expected_salary: data.expected_salary,
            has_field_experience: data.has_field_experience,
            proximity_to_branch: data.proximity_to_branch,
            academic_status: data.academic_status,
            can_start_immediately: data.can_start_immediately,
            prayer_regularity: data.prayer_regularity,
            is_smoker: data.is_smoker,
            registration_form_data: data.registration_form_data
          }
        };
        
        setCandidate(candidate as Candidate);
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

  // Clean up Vapi call on unmount
  useEffect(() => {
    return () => {
      // Clean up any active call on unmount
      if (vapiCallRef.current && typeof vapiCallRef.current.destroy === 'function') {
        vapiCallRef.current.destroy();
      }
    };
  }, []);

  const startInterview = async () => {
    if (!candidate) return;
    setError(null);
    
    try {
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
      } else {
        throw new Error("Failed to initialize interview session");
      }
      
      // Initialize Vapi call
      const assistantId = vapiAssistantIdRef.current;
      if (!assistantId) {
        throw new Error("Missing Vapi Assistant ID");
      }
      
      // Clear previous transcript
      setTranscript([]);
      
      try {
        // Initialize Vapi exactly as specified in the requirements
        const vapi = new Vapi(process.env.NEXT_PUBLIC_VAPI_PUBLIC_KEY!);
        
        // Start the call with the assistant ID
        const call = await vapi.start(assistantId);
        
        // Save call reference
        vapiCallRef.current = call;
        
        // Update UI
        setCallStatus("live");
        toast.success("Live call started");
      } catch (err) {
        console.error("Error starting Vapi call:", err);
        setError("Failed to start call: " + (err instanceof Error ? err.message : String(err)));
        setCallStatus("ready");
        toast.error("Failed to start call");
      }
      
      // Note: The actual call reference and status updates are handled in the setTimeout callback
      
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start interview";
      setCallStatus("ready");
      setError(msg);
      toast.error(msg);
    }
  };
  
  const stopInterview = () => {
    try {
      // First check if we have a reference to the call
      if (vapiCallRef.current) {
        // Try the stop() method first (correct for v2.5.2)
        if (typeof vapiCallRef.current.stop === 'function') {
          vapiCallRef.current.stop();
        } 
        // Fall back to destroy() if stop doesn't exist
        else if (typeof vapiCallRef.current.destroy === 'function') {
          vapiCallRef.current.destroy();
        } 
        // Last resort - just log a warning
        else {
          console.warn('No stop or destroy method found on Vapi call reference');
        }
      }
      
      // Clear reference regardless
      vapiCallRef.current = null;
      setCallStatus("processing");
      toast.info("Ending call...");
    } catch (error) {
      console.error("Error stopping interview:", error);
      // Still clear reference and update UI even if there's an error
      vapiCallRef.current = null;
      setCallStatus("processing");
    }
  };
  
  // No longer needed - Vapi handles audio processing
  
  // No longer needed - Vapi handles TTS
  
  const endInterview = () => {
    try {
      // Stop the call if it's still active
      if (vapiCallRef.current) {
        // Try the stop() method first (correct for v2.5.2)
        if (typeof vapiCallRef.current.stop === 'function') {
          vapiCallRef.current.stop();
        } 
        // Fall back to destroy() if stop doesn't exist
        else if (typeof vapiCallRef.current.destroy === 'function') {
          vapiCallRef.current.destroy();
        } 
        // Last resort - just log a warning
        else {
          console.warn('No stop or destroy method found on Vapi call reference');
        }
        
        // Clear reference regardless
        vapiCallRef.current = null;
      }
    } catch (error) {
      console.error("Error ending interview:", error);
      // Still clear reference even if there's an error
      vapiCallRef.current = null;
    }
    
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
  const RegistrationContextPanel = ({ registrationForm, loading }: { registrationForm?: RegistrationForm; loading?: boolean }) => {
    if (loading) {
      return (
        <div className="bg-gray-100 border border-gray-200 rounded-lg p-4 mb-6 animate-pulse">
          <div className="h-4 bg-gray-300 rounded w-1/4 mb-3"></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="h-3 bg-gray-300 rounded"></div>
            <div className="h-3 bg-gray-300 rounded"></div>
          </div>
        </div>
      );
    }
    
    if (!registrationForm || Object.keys(registrationForm).length === 0) return null;
    
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
            <RegistrationContextPanel 
              registrationForm={registrationForm || candidate?.registration_form}
              loading={loadingContext}
            />
          </div>
          
          {/* Inconsistency Alert */}
          {detectedInconsistencies.length > 0 && (
            <InconsistencyAlert inconsistency={detectedInconsistencies[detectedInconsistencies.length - 1]} />
          )}

          {/* Vapi container - this is where the Vapi UI will be rendered */}
          <div ref={vapiContainerRef} className="mt-8 w-full h-32 bg-gray-50 rounded-lg"></div>
          
          {/* Call controls */}
          <div className="mt-8 flex flex-col items-center gap-4">
            {callStatus === "ready" && (
              <button
                onClick={startInterview}
                className="flex h-20 w-20 items-center justify-center rounded-full bg-green-500 text-white shadow-lg transition hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50"
                aria-label="Start interview"
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
            {callStatus === "live" && (
              <div className="flex flex-col items-center gap-3">
                <div className="flex items-center justify-center gap-3">
                  <div className="h-3 w-3 animate-pulse rounded-full bg-green-500"></div>
                  <span className="text-sm font-medium text-green-600">Live Call</span>
                </div>
                <button
                  onClick={stopInterview}
                  className="flex h-16 w-16 items-center justify-center rounded-full bg-red-500 text-white shadow-lg transition hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                  aria-label="End call"
                >
                  <svg
                    className="h-8 w-8"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11H7v-2h10v2z" />
                  </svg>
                </button>
              </div>
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
              {callStatus === "live" && "Live call in progress — Speak naturally"}
              {callStatus === "processing" && "Ending call..."}
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
