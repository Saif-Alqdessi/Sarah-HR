"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Play, Pause, FileText, CheckCircle, XCircle, AlertTriangle, User, MessageCircle, BarChart3, Clock, DollarSign, Calendar } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function CandidateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const candidateId = params?.id as string;

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchCandidateDetail() {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
        const res = await fetch(`${apiUrl}/api/admin/candidates/${candidateId}`, {
          headers: {
            "X-Admin-Key": process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key",
          }
        });

        if (!res.ok) throw new Error("Failed to fetch candidate details");

        const json = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    }
    if (candidateId) {
      fetchCandidateDetail();
    }
  }, [candidateId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="mt-4 text-slate-500">Loading candidate profile...</p>
      </div>
    );
  }

  if (error || !data?.candidate) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <AlertTriangle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-xl font-bold text-slate-900">Error Loading Candidate</h2>
        <p className="text-slate-500 mt-2">{error || "Candidate not found"}</p>
        <button
          onClick={() => router.back()}
          className="mt-6 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md font-medium transition-colors"
        >
          Go Back
        </button>
      </div>
    );
  }

  const { candidate, interview, score } = data;
  const transcript = interview?.full_transcript || [];

  // Format chart data
  const categoryScores = score?.category_scores || {};
  const chartData = [
    { name: "Communication", score: categoryScores.communication?.score || 0 },
    { name: "Learning", score: categoryScores.learning?.score || 0 },
    { name: "Stability", score: categoryScores.stability?.score || 0 },
    { name: "Credibility", score: categoryScores.credibility?.score || 0 },
    { name: "Adaptability", score: categoryScores.adaptability?.score || 0 },
    { name: "Field Knowledge", score: categoryScores.field_knowledge?.score || 0 },
  ];

  const getRecommendationBadge = (recommendation: string | null | undefined) => {
    switch (recommendation) {
      case "strongly_recommend":
        return <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-green-500 text-white shadow-sm">مقبول بشدة (Strongly Recommend)</span>;
      case "recommend":
        return <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-green-400 text-white shadow-sm">مقبول (Recommend)</span>;
      case "neutral":
        return <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-yellow-400 text-slate-900 shadow-sm">محتمل (Neutral)</span>;
      case "not_recommend":
        return <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-red-400 text-white shadow-sm">غير مناسب (Not Recommend)</span>;
      case "reject":
        return <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-red-500 text-white shadow-sm">مرفوض (Reject)</span>;
      default:
        return <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-slate-200 text-slate-700 shadow-sm">غير مقيّم (Unscored)</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 rounded-full transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{candidate.full_name}</h1>
            <p className="text-sm text-slate-500 mt-0.5">{candidate.target_role} • {candidate.email || candidate.phone_number}</p>
          </div>
        </div>
        <div>
          {getRecommendationBadge(score?.hire_recommendation)}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Candidate Info & AI Score Overview */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Candidate Profile Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <User className="w-4 h-4 text-slate-400" />
              Candidate Profile
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between pb-3 border-b border-slate-100">
                <span className="text-sm text-slate-500">Experience</span>
                <span className="text-sm font-medium text-slate-900">{candidate.years_of_experience || 0} Years</span>
              </div>
              <div className="flex justify-between pb-3 border-b border-slate-100">
                <span className="text-sm text-slate-500">Target Role</span>
                <span className="text-sm font-medium text-slate-900">{candidate.target_role}</span>
              </div>
              <div className="flex justify-between pb-3 border-b border-slate-100">
                <span className="text-sm text-slate-500">Expected Salary</span>
                <span className="text-sm font-medium text-slate-900">{candidate.expected_salary ? `${candidate.expected_salary} JOD` : "N/A"}</span>
              </div>
              <div className="flex justify-between pb-3 border-b border-slate-100">
                <span className="text-sm text-slate-500">Can Start Immediately</span>
                <span className="text-sm font-medium text-slate-900">{candidate.can_start_immediately ? "Yes" : "No"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-500">Applied On</span>
                <span className="text-sm font-medium text-slate-900">{new Date(candidate.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          {/* AI Score Summary Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-slate-400" />
              AI Evaluation
            </h2>
            
            {score ? (
              <div className="space-y-6">
                <div className="flex items-center justify-center py-4">
                  <div className="relative flex items-center justify-center w-32 h-32 rounded-full border-8 border-slate-100">
                    <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                      <circle
                        className={`text-${score.final_score >= 80 ? 'green' : score.final_score >= 60 ? 'amber' : 'red'}-500 stroke-current`}
                        strokeWidth="8"
                        strokeDasharray={2 * Math.PI * 56}
                        strokeDashoffset={2 * Math.PI * 56 * (1 - score.final_score / 100)}
                        strokeLinecap="round"
                        fill="transparent"
                        r="56"
                        cx="64"
                        cy="64"
                      />
                    </svg>
                    <div className="flex flex-col items-center justify-center">
                      <span className="text-4xl font-bold tracking-tighter text-slate-900">{Math.round(score.final_score)}</span>
                      <span className="text-xs text-slate-500 uppercase font-semibold">Score</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 pt-4 border-t border-slate-100">
                  <div className="flex justify-between items-center pb-2">
                    <span className="text-sm font-medium text-slate-700">Competency Breakdown</span>
                  </div>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                        <XAxis type="number" domain={[0, 100]} hide />
                        <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                        <Tooltip 
                          cursor={{ fill: '#f1f5f9' }}
                          contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} 
                        />
                        <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                          {chartData.map((entry, index) => (
                            <cell key={`cell-${index}`} fill={entry.score >= 80 ? '#22c55e' : entry.score >= 60 ? '#f59e0b' : '#ef4444'} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {score.bottom_line_summary && (
                  <div className="p-4 bg-slate-50 rounded-lg text-sm text-slate-700 border border-slate-100">
                    <span className="font-semibold block mb-1">Bottom Line:</span>
                    {score.bottom_line_summary}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-20" />
                <p>No evaluation available yet.</p>
                {interview?.status === "completed" && (
                  <p className="text-xs mt-1 text-slate-400">Scoring might be in progress...</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Audio Player & Transcript */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Audio Player Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Play className="w-4 h-4 text-slate-400" />
              Interview Session Recording
            </h2>
            
            {interview?.audio_public_url ? (
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl">
                <audio 
                  controls 
                  className="w-full" 
                  src={interview.audio_public_url}
                >
                  Your browser does not support the audio element.
                </audio>
                <div className="flex justify-between items-center mt-3 text-xs text-slate-500 px-2">
                  <span>Recorded: {interview.completed_at ? new Date(interview.completed_at).toLocaleString() : "Unknown"}</span>
                  {interview.audio_duration_seconds && <span>Duration: {Math.floor(interview.audio_duration_seconds / 60)}:{(interview.audio_duration_seconds % 60).toString().padStart(2, '0')}</span>}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <Play className="w-10 h-10 text-slate-300 mb-2" />
                <p className="text-sm text-slate-500">No recording available for this interview.</p>
              </div>
            )}
          </div>

          {/* Transcript & Feedback */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <MessageCircle className="w-4 h-4 text-slate-400" />
                Interactive Transcript
              </h2>
              {interview && (
                <span className="text-xs font-medium px-2 py-1 rounded bg-slate-100 text-slate-600">
                  {interview.status}
                </span>
              )}
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/30">
              {transcript.length > 0 ? (
                transcript.map((turn: any, i: number) => {
                  const isSarah = turn.role === "assistant";
                  return (
                    <div key={i} className={`flex ${isSarah ? "justify-start" : "justify-end"} group`}>
                      <div className={`max-w-[80%] rounded-2xl px-5 py-3.5 shadow-sm ${
                        isSarah 
                          ? "bg-white border border-slate-200 text-slate-700 rounded-tl-none" 
                          : "bg-amber-500 text-white rounded-tr-none"
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-bold uppercase tracking-wider ${isSarah ? "text-slate-900" : "text-amber-100"}`}>
                            {isSarah ? "Sarah AI" : candidate.full_name.split(" ")[0]}
                          </span>
                        </div>
                        <p className="leading-relaxed text-sm whitespace-pre-wrap dir-rtl text-right" dir="auto">
                          {turn.content}
                        </p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <FileText className="w-12 h-12 mb-3 opacity-20" />
                  <p>Transcript is empty or not available.</p>
                </div>
              )}
            </div>
          </div>

          {/* Detailed Strengths & Weaknesses (if available) */}
          {score && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  Key Strengths
                </h3>
                <ul className="space-y-3">
                  {score.strengths?.length > 0 ? score.strengths.map((s: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-slate-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 flex-shrink-0"></span>
                      <span>{s}</span>
                    </li>
                  )) : <li className="text-sm text-slate-500">None identified</li>}
                </ul>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                  Areas for Improvement
                </h3>
                <ul className="space-y-3">
                  {score.weaknesses?.length > 0 ? score.weaknesses.map((w: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-slate-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 flex-shrink-0"></span>
                      <span>{w}</span>
                    </li>
                  )) : <li className="text-sm text-slate-500">None identified</li>}
                </ul>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
