"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createSupabaseClient } from "@/lib/supabase/client";
import { toast } from "sonner";
import { useVoiceInterview } from "@/hooks/useVoiceInterview";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Phone, PhoneOff, Loader2, Sparkles, CheckCircle2 } from "lucide-react";

interface Candidate {
  id: string;
  full_name: string;
  phone_number: string;
  email?: string;
  target_role: string;
}

export default function InterviewPage() {
  const params = useParams();
  const router = useRouter();
  const candidateId = params?.candidateId as string;
  const interviewIdRef = useRef<string | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [interviewId, setInterviewId] = useState<string | null>(null);

  // Audio visualizer
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Voice interview hook
  const voice = useVoiceInterview();
  const recorder = useAudioRecorder();
  const transcript = voice.transcript;

  // Derive UI state from voice hook
  const uiState = voice.isCompleted
    ? "completed"
    : voice.isSpeaking
    ? "processing"
    : voice.isConnected
    ? "live"
    : voice.isConnecting
    ? "connecting"
    : "ready";

  // Fetch candidate
  useEffect(() => {
    async function fetchCandidate() {
      if (!candidateId) {
        setError("Missing candidate ID");
        setIsLoading(false);
        return;
      }

      try {
        const supabase = createSupabaseClient();
        const { data, error: fetchError } = await supabase
          .from("candidates")
          .select("*")
          .eq("id", candidateId)
          .single();

        if (fetchError) throw fetchError;
        setCandidate(data);
      } catch (err) {
        console.error("Error fetching candidate:", err);
        setError(err instanceof Error ? err.message : "Failed to load candidate");
      } finally {
        setIsLoading(false);
      }
    }

    fetchCandidate();
  }, [candidateId]);

  // Setup Web Audio visualizer
  useEffect(() => {
    if (uiState !== "live") return;

    const setupVisualizer = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        analyserRef.current = analyser;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const draw = () => {
          animationFrameRef.current = requestAnimationFrame(draw);
          analyser.getByteFrequencyData(dataArray);

          ctx.clearRect(0, 0, canvas.width, canvas.height);

          const barWidth = canvas.width / bufferLength;
          let x = 0;

          for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255) * canvas.height * 0.8;
            const hue = 45 + (dataArray[i] / 255) * 15;
            ctx.fillStyle = `hsl(${hue}, 85%, 55%)`;
            ctx.fillRect(x, canvas.height - barHeight, barWidth - 2, barHeight);
            x += barWidth;
          }
        };

        draw();
      } catch (err) {
        console.error("Visualizer setup failed:", err);
      }
    };

    setupVisualizer();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [uiState]);

  // Handle completion
  useEffect(() => {
    if (voice.isCompleted && interviewIdRef.current) {
      toast.success("تم الانتهاء من المقابلة!");
      
      const blob = recorder.getBlob();
      if (blob) {
        recorder.uploadToSupabase(interviewIdRef.current).catch((err) => {
          console.error("Audio upload failed:", err);
        });
      }

      setTimeout(() => {
        router.push(`/interview/complete?candidate_id=${candidateId}`);
      }, 3000);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voice.isCompleted]);

  const startInterview = async () => {
    if (!candidate) return;
    setError(null);

    try {
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

      await voice.start(candidate.id);
      const stream = voice.getStream();
      if (stream) {
        recorder.startFullSession(stream);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start interview";
      setError(msg);
      toast.error(msg);
    }
  };

  const stopInterview = () => {
    voice.stop();
    recorder.stopFullSession();
    toast.info("إنهاء المقابلة...");
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-amber-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 text-amber-400 animate-spin" />
          <p className="text-amber-300 text-lg">جاري التحميل...</p>
        </div>
      </main>
    );
  }

  if (error && !candidate) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-amber-900 flex items-center justify-center p-8">
        <div className="text-center">
          <p className="text-red-400 mb-4 text-lg">{error}</p>
          <button
            onClick={() => router.push("/apply")}
            className="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors"
          >
            العودة للتسجيل
          </button>
        </div>
      </main>
    );
  }

  return (
    <main dir="rtl" className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-amber-900 relative overflow-hidden">
      {/* Radial Glow Effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-amber-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-orange-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
      </div>

      <div className="relative mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-2xl shadow-amber-500/30 mb-6">
            <Sparkles className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white sm:text-5xl mb-3">
            مقابلة مع سارة AI
          </h1>
          <p className="text-amber-300/90 text-xl font-medium">
            {candidate?.full_name}
          </p>
          <p className="text-slate-400 text-sm mt-2">
            الوظيفة: {candidate?.target_role}
          </p>
        </motion.div>

        {/* Main Interview Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 shadow-2xl border border-slate-700/50 mb-6"
        >
          {/* State-Based UI */}
          <AnimatePresence mode="wait">
            {/* READY STATE */}
            {uiState === "ready" && (
              <motion.div
                key="ready"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-12"
              >
                <div className="w-32 h-32 mx-auto mb-6 rounded-full bg-gradient-to-br from-green-400 to-emerald-500 flex items-center justify-center shadow-2xl shadow-green-500/30">
                  <Phone className="w-16 h-16 text-white" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-3">
                  جاهز للبدء؟
                </h2>
                <p className="text-slate-300 mb-8 max-w-md mx-auto">
                  اضغط على الزر أدناه لبدء المقابلة الصوتية مع سارة. تأكد من وجودك في مكان هادئ.
                </p>
                <button
                  onClick={startInterview}
                  className="px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white rounded-xl transition-all shadow-lg shadow-green-500/30 flex items-center gap-3 mx-auto text-lg font-bold"
                >
                  <Mic className="w-6 h-6" />
                  بدء المقابلة
                </button>
              </motion.div>
            )}

            {/* CONNECTING STATE */}
            {uiState === "connecting" && (
              <motion.div
                key="connecting"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-12"
              >
                <div className="w-32 h-32 mx-auto mb-6 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-2xl shadow-amber-500/30">
                  <Loader2 className="w-16 h-16 text-white animate-spin" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-3">
                  جاري الاتصال...
                </h2>
                <p className="text-slate-300">
                  يرجى الانتظار بينما نقوم بتوصيلك مع سارة
                </p>
              </motion.div>
            )}

            {/* LIVE STATE */}
            {uiState === "live" && (
              <motion.div
                key="live"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-6"
              >
                {/* Audio Visualizer */}
                <div className="relative">
                  <canvas
                    ref={canvasRef}
                    width={800}
                    height={200}
                    className="w-full h-48 rounded-xl bg-slate-900/50 border border-slate-700"
                  />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <motion.div
                      animate={{
                        scale: [1, 1.2, 1],
                        opacity: [0.5, 0.8, 0.5],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                      className="w-24 h-24 rounded-full bg-amber-500/20 border-2 border-amber-500/50"
                    />
                    <motion.div
                      animate={{
                        scale: [1, 1.4, 1],
                        opacity: [0.3, 0.6, 0.3],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                        delay: 0.5,
                      }}
                      className="absolute w-32 h-32 rounded-full bg-amber-500/10 border border-amber-500/30"
                    />
                  </div>
                </div>

                {/* Status */}
                <div className="flex items-center justify-center gap-3 py-4">
                  <div className="w-3 h-3 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-green-300 font-semibold">المقابلة جارية</span>
                </div>

                {/* End Call Button */}
                <div className="text-center">
                  <button
                    onClick={stopInterview}
                    className="px-8 py-4 bg-gradient-to-r from-red-500 to-rose-500 hover:from-red-600 hover:to-rose-600 text-white rounded-xl transition-all shadow-lg shadow-red-500/30 flex items-center gap-3 mx-auto text-lg font-bold"
                  >
                    <PhoneOff className="w-6 h-6" />
                    إنهاء المقابلة
                  </button>
                </div>
              </motion.div>
            )}

            {/* PROCESSING STATE */}
            {uiState === "processing" && (
              <motion.div
                key="processing"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-12"
              >
                <div className="w-32 h-32 mx-auto mb-6 rounded-full bg-gradient-to-br from-purple-400 to-violet-500 flex items-center justify-center shadow-2xl shadow-purple-500/30">
                  <Loader2 className="w-16 h-16 text-white animate-spin" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-3">
                  جاري المعالجة...
                </h2>
                <p className="text-slate-300">
                  سارة تقوم بتحليل إجاباتك الآن
                </p>
              </motion.div>
            )}

            {/* COMPLETED STATE */}
            {uiState === "completed" && (
              <motion.div
                key="completed"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-12"
              >
                <div className="w-32 h-32 mx-auto mb-6 rounded-full bg-gradient-to-br from-green-400 to-emerald-500 flex items-center justify-center shadow-2xl shadow-green-500/30">
                  <CheckCircle2 className="w-16 h-16 text-white" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-3">
                  تم الانتهاء!
                </h2>
                <p className="text-slate-300">
                  شكراً لك! سيتم تحويلك إلى صفحة النتائج...
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Transcript Panel */}
        {transcript.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 shadow-2xl border border-slate-700/50"
          >
            <h3 className="text-xl font-bold text-amber-400 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              سجل المحادثة
            </h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {transcript.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: msg.role === "Sarah" ? -20 : 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className={`flex ${msg.role === "Sarah" ? "justify-start" : "justify-end"}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                      msg.role === "Sarah"
                        ? "bg-amber-500/20 border border-amber-500/30 text-amber-100"
                        : "bg-slate-700/50 border border-slate-600 text-slate-200"
                    }`}
                  >
                    <p className="text-sm leading-relaxed">{msg.text}</p>
                    {msg.timestamp && (
                      <span className="text-xs opacity-60 mt-1 block">
                        {new Date(msg.timestamp).toLocaleTimeString("ar-JO", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Error Display */}
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-300 text-center"
          >
            {error}
          </motion.div>
        )}
      </div>
    </main>
  );
}
