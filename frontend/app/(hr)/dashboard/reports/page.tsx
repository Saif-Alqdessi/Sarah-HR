"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
  AreaChart, Area,
  FunnelChart, Funnel, LabelList,
} from "recharts";
import { BarChart3, TrendingUp, Users, Target, Loader2 } from "lucide-react";

const COLORS = ["#f59e0b", "#3b82f6", "#22c55e", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

const SCORE_COLORS: Record<string, string> = {
  "0-20": "#ef4444",
  "21-40": "#f97316",
  "41-60": "#f59e0b",
  "61-80": "#22c55e",
  "81-100": "#059669",
};

const REVIEW_LABELS: Record<string, string> = {
  new: "جديد",
  viewed: "تمت المراجعة",
  strong_candidate: "مرشح قوي",
  weak_candidate: "مرشح ضعيف",
  shortlisted: "مرحلة متقدمة",
  hired: "تم التوظيف",
  rejected: "مرفوض",
};

export default function ReportsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const adminKey = process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key";

  useEffect(() => {
    async function fetchReports() {
      try {
        const res = await fetch(`${apiUrl}/api/admin/dashboard/reports`, {
          headers: { "X-Admin-Key": adminKey },
        });
        if (!res.ok) throw new Error("Failed to fetch reports");
        const json = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchReports();
  }, [apiUrl, adminKey]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
        <p className="mt-4 text-slate-500">جاري تحميل التقارير...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <BarChart3 className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-xl font-bold text-slate-900">خطأ في تحميل التقارير</h2>
        <p className="text-slate-500 mt-2">{error}</p>
      </div>
    );
  }

  const { score_distribution, role_breakdown, funnel, daily_trend, review_distribution } = data;

  // Enrich review distribution with Arabic labels
  const reviewData = (review_distribution || []).map((r: any) => ({
    ...r,
    label: REVIEW_LABELS[r.status] || r.status,
  }));

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">التقارير والتحليلات</h1>
        <p className="text-sm text-slate-500 mt-1">إحصائيات شاملة عن عمليات التوظيف</p>
      </div>

      {/* ═════ Top Row: Score Distribution + Role Breakdown ═════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Score Distribution */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-amber-500" />
            توزيع النتائج
          </h2>
          <p className="text-xs text-slate-500 mb-4">عدد المرشحين حسب فئة الدرجات</p>

          {score_distribution?.some((d: any) => d.count > 0) ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={score_distribution} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="range" tick={{ fontSize: 12, fill: "#64748b" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#64748b" }} />
                  <Tooltip
                    contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                    formatter={(value: number) => [value, "مرشحين"]}
                  />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {score_distribution.map((entry: any, i: number) => (
                      <Cell key={i} fill={SCORE_COLORS[entry.range] || COLORS[i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyChart message="لا توجد نتائج بعد" />
          )}
        </div>

        {/* Candidates by Role */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1 flex items-center gap-2">
            <Users className="w-4 h-4 text-blue-500" />
            المرشحون حسب الوظيفة
          </h2>
          <p className="text-xs text-slate-500 mb-4">توزيع التقديمات على المسميات الوظيفية</p>

          {role_breakdown?.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={role_breakdown}
                    dataKey="count"
                    nameKey="role"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    innerRadius={50}
                    paddingAngle={3}
                    label={({ role, count }: any) => `${role} (${count})`}
                    labelLine={{ strokeWidth: 1, stroke: "#94a3b8" }}
                  >
                    {role_breakdown.map((_: any, i: number) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => [value, "مرشح"]} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyChart message="لا توجد بيانات" />
          )}
        </div>
      </div>

      {/* ═════ Middle Row: Hiring Funnel + Review Status ═════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Hiring Funnel */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1 flex items-center gap-2">
            <Target className="w-4 h-4 text-green-500" />
            قمع التوظيف
          </h2>
          <p className="text-xs text-slate-500 mb-4">من التسجيل إلى التوظيف</p>

          {funnel?.length > 0 ? (
            <div className="space-y-4 pt-2">
              {funnel.map((stage: any, i: number) => {
                const maxCount = funnel[0]?.count || 1;
                const pct = maxCount > 0 ? Math.round((stage.count / maxCount) * 100) : 0;
                return (
                  <div key={i}>
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-sm font-medium text-slate-700">{stage.stage}</span>
                      <span className="text-sm font-bold text-slate-900">{stage.count}</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-8 overflow-hidden">
                      <div
                        className="h-full rounded-full flex items-center justify-end px-3 transition-all duration-700"
                        style={{
                          width: `${Math.max(pct, 8)}%`,
                          background: `linear-gradient(90deg, ${COLORS[i]}, ${COLORS[i]}dd)`,
                        }}
                      >
                        <span className="text-xs font-bold text-white drop-shadow-sm">{pct}%</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyChart message="لا توجد بيانات" />
          )}
        </div>

        {/* Review Status Distribution */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1 flex items-center gap-2">
            <Target className="w-4 h-4 text-indigo-500" />
            حالة المراجعة
          </h2>
          <p className="text-xs text-slate-500 mb-4">توزيع مراحل اتخاذ القرار</p>

          {reviewData?.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reviewData} layout="vertical" margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#64748b" }} />
                  <YAxis dataKey="label" type="category" width={100} tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0" }}
                    formatter={(value: number) => [value, "مقابلات"]}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                    {reviewData.map((_: any, i: number) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyChart message="لا توجد بيانات" />
          )}
        </div>
      </div>

      {/* ═════ Bottom Row: Daily Trend ═════ */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-500" />
          اتجاه التقديمات اليومي
        </h2>
        <p className="text-xs text-slate-500 mb-4">عدد التقديمات خلال آخر 30 يوم</p>

        {daily_trend?.length > 0 ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={daily_trend} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#64748b" }} />
                <Tooltip
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0" }}
                  formatter={(value: number) => [value, "تقديم"]}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fill="url(#colorCount)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChart message="لا توجد تقديمات في آخر 30 يوم" />
        )}
      </div>
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="h-64 flex flex-col items-center justify-center text-slate-400">
      <BarChart3 className="w-12 h-12 mb-3 opacity-20" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
