"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Play,
  FileText,
  CheckCircle,
  XCircle,
  AlertTriangle,
  User,
  MessageCircle,
  BarChart3,
  Clock,
  DollarSign,
  Calendar,
  MapPin,
  Phone,
  Briefcase,
  GraduationCap,
  Heart,
  Shield,
  Star,
  Loader2,
  Save,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// ─── Review Status Config ──────────────────────────────────────────────────

const REVIEW_STATUSES = [
  { value: "new",              label: "جديد",           labelEn: "New",              color: "bg-slate-100 text-slate-700 border-slate-300",    dot: "bg-slate-400" },
  { value: "viewed",           label: "تمت المراجعة",   labelEn: "Viewed",           color: "bg-blue-50 text-blue-700 border-blue-200",        dot: "bg-blue-400" },
  { value: "strong_candidate", label: "مرشح قوي",       labelEn: "Strong",           color: "bg-green-50 text-green-700 border-green-200",     dot: "bg-green-500" },
  { value: "weak_candidate",   label: "مرشح ضعيف",      labelEn: "Weak",             color: "bg-orange-50 text-orange-700 border-orange-200",  dot: "bg-orange-400" },
  { value: "shortlisted",      label: "مرحلة متقدمة",   labelEn: "Shortlisted",      color: "bg-indigo-50 text-indigo-700 border-indigo-200",  dot: "bg-indigo-500" },
  { value: "hired",            label: "تم التوظيف ✓",   labelEn: "Hired",            color: "bg-emerald-500 text-white border-emerald-600",    dot: "bg-white" },
  { value: "rejected",         label: "مرفوض ✗",        labelEn: "Rejected",         color: "bg-red-500 text-white border-red-600",            dot: "bg-white" },
];

function getStatusConfig(value: string) {
  return REVIEW_STATUSES.find((s) => s.value === value) || REVIEW_STATUSES[0];
}

// ─── Score Badge ───────────────────────────────────────────────────────────

function getScoreColor(score: number) {
  if (score >= 80) return { ring: "text-green-500", bg: "bg-green-50", text: "text-green-700" };
  if (score >= 60) return { ring: "text-amber-500", bg: "bg-amber-50", text: "text-amber-700" };
  return { ring: "text-red-500", bg: "bg-red-50", text: "text-red-700" };
}

function getBarColor(score: number) {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}

// ─── Main Component ────────────────────────────────────────────────────────

export default function CandidateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const candidateId = params?.id as string;

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // HR Review state
  const [reviewStatus, setReviewStatus] = useState("new");
  const [hrNotes, setHrNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Audio signed URL
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioLoading, setAudioLoading] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const adminKey = process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key";

  // ─── Fetch Data ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (!candidateId) return;

    async function fetchDetail() {
      try {
        const res = await fetch(`${apiUrl}/api/admin/candidates/${candidateId}`, {
          headers: { "X-Admin-Key": adminKey },
        });
        if (!res.ok) throw new Error("Failed to fetch candidate");
        const json = await res.json();
        setData(json);

        // Seed review state from server
        if (json.interview?.review_status) {
          setReviewStatus(json.interview.review_status);
        }
        if (json.interview?.hr_notes) {
          setHrNotes(json.interview.hr_notes);
        }

        // Fetch signed audio URL if interview has audio
        if (json.interview?.audio_storage_path || json.interview?.audio_public_url) {
          setAudioLoading(true);
          fetch(`${apiUrl}/api/admin/candidates/${candidateId}/audio-url`, {
            headers: { "X-Admin-Key": adminKey },
          })
            .then((r) => r.json())
            .then((audioData) => {
              if (audioData?.signed_url) setAudioUrl(audioData.signed_url);
            })
            .catch(() => {
              // fallback to public URL
              if (json.interview?.audio_public_url) setAudioUrl(json.interview.audio_public_url);
            })
            .finally(() => setAudioLoading(false));
        }
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchDetail();
  }, [candidateId, apiUrl, adminKey]);

  // ─── Save Review ────────────────────────────────────────────────────────

  const saveReview = useCallback(
    async (newStatus?: string) => {
      const statusToSave = newStatus || reviewStatus;
      setSaving(true);
      setSaveSuccess(false);

      try {
        const res = await fetch(`${apiUrl}/api/admin/candidates/${candidateId}/review`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Key": adminKey,
          },
          body: JSON.stringify({
            review_status: statusToSave,
            hr_notes: hrNotes || null,
          }),
        });

        if (!res.ok) throw new Error("Failed to save review");

        if (newStatus) setReviewStatus(newStatus);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2000);
      } catch (err) {
        console.error("Save review failed:", err);
      } finally {
        setSaving(false);
      }
    },
    [apiUrl, adminKey, candidateId, reviewStatus, hrNotes]
  );

  // ─── Loading / Error States ──────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
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
        <button onClick={() => router.back()} className="mt-6 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md font-medium transition-colors">
          Go Back
        </button>
      </div>
    );
  }

  const { candidate, interview, score, scoring_job } = data;
  const transcript: any[] = interview?.full_transcript || [];
  const currentStatusConfig = getStatusConfig(reviewStatus);

  // Chart data
  const categoryScores = score?.category_scores || {};
  const chartData = [
    { name: "تواصل", nameEn: "Communication", score: categoryScores.communication?.score || 0 },
    { name: "تعلم", nameEn: "Learning", score: categoryScores.learning?.score || 0 },
    { name: "استقرار", nameEn: "Stability", score: categoryScores.stability?.score || 0 },
    { name: "مصداقية", nameEn: "Credibility", score: categoryScores.credibility?.score || 0 },
    { name: "مرونة", nameEn: "Adaptability", score: categoryScores.adaptability?.score || 0 },
    { name: "خبرة ميدانية", nameEn: "Field Knowledge", score: categoryScores.field_knowledge?.score || 0 },
  ];

  // ─── Registration Data Sections ──────────────────────────────────────────

  const personalInfo = [
    { icon: User, label: "الاسم الكامل", value: candidate.full_name },
    { icon: Phone, label: "رقم الهاتف", value: candidate.phone_number },
    { icon: Calendar, label: "تاريخ الميلاد", value: candidate.date_of_birth },
    { icon: User, label: "الجنس", value: candidate.gender },
    { icon: Shield, label: "الجنسية", value: candidate.nationality },
    { icon: Heart, label: "الحالة الاجتماعية", value: candidate.marital_status },
    { icon: MapPin, label: "مكان السكن", value: candidate.detailed_residence },
  ];

  const jobInfo = [
    { icon: Briefcase, label: "الوظيفة المطلوبة", value: candidate.target_role },
    { icon: Clock, label: "سنوات الخبرة", value: candidate.years_of_experience != null ? `${candidate.years_of_experience} سنة` : null },
    { icon: Briefcase, label: "خبرة ميدانية", value: candidate.has_field_experience },
    { icon: DollarSign, label: "الراتب المتوقع", value: candidate.expected_salary ? `${candidate.expected_salary} دينار` : null },
    { icon: Clock, label: "الوردية المفضلة", value: candidate.preferred_schedule },
    { icon: CheckCircle, label: "بدء فوري", value: candidate.can_start_immediately },
  ];

  const additionalInfo = [
    { icon: Calendar, label: "الفئة العمرية", value: candidate.age_range },
    { icon: GraduationCap, label: "المسار الدراسي", value: candidate.academic_status },
    { icon: GraduationCap, label: "المؤهل الأكاديمي", value: candidate.academic_qualification },
    { icon: MapPin, label: "قرب السكن من الفرع", value: candidate.proximity_to_branch },
    { icon: User, label: "أقارب بالشركة", value: candidate.has_relatives_at_company },
    { icon: User, label: "عمل سابق بقبلان", value: candidate.previously_at_qabalan },
    { icon: Shield, label: "ضمان اجتماعي", value: candidate.social_security_issues },
  ];

  const commitments = [
    { icon: Star, label: "الصلاة", value: candidate.prayer_regularity },
    { icon: AlertTriangle, label: "التدخين", value: candidate.is_smoker },
    { icon: User, label: "مانع حلاقة/مظهر", value: candidate.grooming_objection },
  ];

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      {/* ═════ HEADER ═════ */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={() => router.back()} className="p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 rounded-full transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{candidate.full_name}</h1>
            <p className="text-sm text-slate-500 mt-0.5">{candidate.target_role} • {candidate.phone_number}</p>
          </div>
        </div>

        {/* Score Pill */}
        {score?.final_score != null && (
          <div className={`flex items-center gap-3 px-4 py-2 rounded-xl border ${getScoreColor(score.final_score).bg} border-slate-200 shadow-sm`}>
            <span className={`text-3xl font-bold tracking-tighter ${getScoreColor(score.final_score).text}`}>
              {Math.round(score.final_score)}%
            </span>
            <span className="text-xs text-slate-500 leading-tight">AI<br/>Score</span>
          </div>
        )}
      </div>

      {/* ═════ HR DECISION BAR ═════ */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-4">
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className={`w-3 h-3 rounded-full ${currentStatusConfig.dot}`} />
            <span className="text-sm font-semibold text-slate-700">قرار التوظيف:</span>
          </div>

          {/* Status Buttons */}
          <div className="flex flex-wrap gap-2 flex-1">
            {REVIEW_STATUSES.map((s) => (
              <button
                key={s.value}
                onClick={() => {
                  setReviewStatus(s.value);
                  saveReview(s.value);
                }}
                disabled={saving}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  reviewStatus === s.value
                    ? `${s.color} ring-2 ring-offset-1 ring-amber-500/50 scale-105`
                    : "bg-white border-slate-200 text-slate-500 hover:border-slate-400 hover:text-slate-700"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Save indicator */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {saving && <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />}
            {saveSuccess && (
              <span className="text-xs font-medium text-green-600 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> تم الحفظ
              </span>
            )}
          </div>
        </div>

        {/* HR Notes */}
        <div className="mt-4 flex gap-3">
          <textarea
            value={hrNotes}
            onChange={(e) => setHrNotes(e.target.value)}
            placeholder="ملاحظات الموارد البشرية (اختياري)..."
            rows={2}
            className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 resize-none"
            dir="rtl"
          />
          <button
            onClick={() => saveReview()}
            disabled={saving}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 self-end disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            حفظ
          </button>
        </div>
      </div>

      {/* ═════ MAIN GRID ═════ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ─── LEFT COLUMN ─── */}
        <div className="lg:col-span-1 space-y-6">

          {/* AI Score Circle */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-slate-400" />
              تقييم سارة الذكي
            </h2>

            {score ? (
              <div className="space-y-6">
                {/* Score Ring */}
                <div className="flex items-center justify-center py-4">
                  <div className="relative flex items-center justify-center w-32 h-32 rounded-full border-8 border-slate-100">
                    <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                      <circle
                        className={`${getScoreColor(score.final_score).ring} stroke-current`}
                        strokeWidth="8"
                        strokeDasharray={2 * Math.PI * 56}
                        strokeDashoffset={2 * Math.PI * 56 * (1 - score.final_score / 100)}
                        strokeLinecap="round"
                        fill="transparent"
                        r="56" cx="64" cy="64"
                      />
                    </svg>
                    <div className="flex flex-col items-center">
                      <span className="text-4xl font-bold tracking-tighter text-slate-900">{Math.round(score.final_score)}</span>
                      <span className="text-xs text-slate-500 uppercase font-semibold">نقطة</span>
                    </div>
                  </div>
                </div>

                {/* Category Breakdown */}
                <div className="h-52">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 5 }}>
                      <XAxis type="number" domain={[0, 100]} hide />
                      <YAxis dataKey="name" type="category" width={90} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                      <Tooltip
                        cursor={{ fill: '#f1f5f9' }}
                        contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        formatter={(value: number) => [`${value}%`, "النتيجة"]}
                      />
                      <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry, i) => (
                          <Cell key={i} fill={getBarColor(entry.score)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Bottom Line */}
                {score.bottom_line_summary && (
                  <div className="p-4 bg-slate-50 rounded-lg text-sm text-slate-700 border border-slate-100" dir="rtl">
                    <span className="font-semibold block mb-1">الخلاصة:</span>
                    {score.bottom_line_summary}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-20" />
                <p>لم يتم التقييم بعد</p>
                {scoring_job?.status === "pending" && (
                  <p className="text-xs mt-1 text-amber-500 animate-pulse">جاري التقييم...</p>
                )}
              </div>
            )}
          </div>

          {/* Registration Data: Personal */}
          <InfoSection title="البيانات الشخصية" icon={User} items={personalInfo} />
          <InfoSection title="البيانات الوظيفية" icon={Briefcase} items={jobInfo} />
          <InfoSection title="معلومات إضافية" icon={GraduationCap} items={additionalInfo} />
          <InfoSection title="الالتزامات" icon={Heart} items={commitments} />
        </div>

        {/* ─── RIGHT COLUMN ─── */}
        <div className="lg:col-span-2 space-y-6">

          {/* Audio Player */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Play className="w-4 h-4 text-slate-400" />
              تسجيل المقابلة
            </h2>
            {audioLoading ? (
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl animate-pulse">
                <div className="h-10 bg-slate-200 rounded-lg w-full" />
                <div className="flex justify-between mt-3 px-2">
                  <div className="h-3 bg-slate-200 rounded w-32" />
                  <div className="h-3 bg-slate-200 rounded w-20" />
                </div>
              </div>
            ) : audioUrl ? (
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl">
                <audio controls className="w-full" src={audioUrl}>
                  Your browser does not support audio.
                </audio>
                <div className="flex justify-between items-center mt-3 text-xs text-slate-500 px-2">
                  <span>تاريخ: {interview.completed_at ? new Date(interview.completed_at).toLocaleString("ar-JO") : "—"}</span>
                  {interview.duration_seconds && (
                    <span>المدة: {Math.floor(interview.duration_seconds / 60)}:{String(interview.duration_seconds % 60).padStart(2, "0")}</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <Play className="w-10 h-10 text-slate-300 mb-2" />
                <p className="text-sm text-slate-500">لا يوجد تسجيل متاح لهذه المقابلة</p>
              </div>
            )}
          </div>

          {/* Transcript */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col" style={{ height: "600px" }}>
            <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <MessageCircle className="w-4 h-4 text-slate-400" />
                سجل المحادثة
              </h2>
              {transcript.length > 0 && (
                <span className="text-xs font-medium px-2 py-1 rounded bg-slate-100 text-slate-600">
                  {transcript.length} رسالة
                </span>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50/30">
              {transcript.length > 0 ? (
                transcript.map((turn: any, i: number) => {
                  const isSarah = turn.role === "assistant" || turn.role === "Sarah";
                  return (
                    <div key={i} className={`flex ${isSarah ? "justify-start" : "justify-end"}`}>
                      <div className={`max-w-[80%] rounded-2xl px-5 py-3.5 shadow-sm ${
                        isSarah
                          ? "bg-white border border-slate-200 text-slate-700 rounded-tl-none"
                          : "bg-amber-500 text-white rounded-tr-none"
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-bold uppercase tracking-wider ${isSarah ? "text-slate-900" : "text-amber-100"}`}>
                            {isSarah ? "سارة AI" : candidate.full_name?.split(" ")[0]}
                          </span>
                        </div>
                        <p className="leading-relaxed text-sm whitespace-pre-wrap" dir="auto">
                          {turn.content || turn.text}
                        </p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <FileText className="w-12 h-12 mb-3 opacity-20" />
                  <p>لا يوجد سجل محادثة</p>
                </div>
              )}
            </div>
          </div>

          {/* Strengths & Weaknesses */}
          {score && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  نقاط القوة
                </h3>
                <ul className="space-y-3">
                  {score.strengths?.length > 0 ? score.strengths.map((s: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-slate-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 flex-shrink-0" />
                      <span dir="auto">{s}</span>
                    </li>
                  )) : <li className="text-sm text-slate-500">لم يتم تحديد نقاط قوة</li>}
                </ul>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
                  <XCircle className="w-4 h-4 text-red-500" />
                  نقاط تحتاج تحسين
                </h3>
                <ul className="space-y-3">
                  {score.weaknesses?.length > 0 ? score.weaknesses.map((w: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-slate-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5 flex-shrink-0" />
                      <span dir="auto">{w}</span>
                    </li>
                  )) : <li className="text-sm text-slate-500">لم يتم تحديد نقاط ضعف</li>}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Reusable Info Section Component ─────────────────────────────────────────

function InfoSection({ title, icon: Icon, items }: {
  title: string;
  icon: any;
  items: { icon: any; label: string; value: any }[];
}) {
  // Filter to only items with values
  const populated = items.filter((item) => item.value != null && item.value !== "");

  if (populated.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
        <Icon className="w-4 h-4 text-slate-400" />
        {title}
      </h2>
      <div className="space-y-3">
        {populated.map((item, i) => (
          <div key={i} className="flex justify-between items-center pb-3 border-b border-slate-100 last:border-0 last:pb-0">
            <span className="text-sm text-slate-500 flex items-center gap-2">
              <item.icon className="w-3.5 h-3.5 text-slate-400" />
              {item.label}
            </span>
            <span className="text-sm font-medium text-slate-900 text-right max-w-[55%]" dir="auto">
              {String(item.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
