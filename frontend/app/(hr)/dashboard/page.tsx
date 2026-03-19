"use client";

import { useState, useEffect } from "react";
import { Users, FileText, CheckCircle, TrendingUp } from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
        const res = await fetch(`${apiUrl}/api/admin/dashboard/stats`, {
           headers: {
            "X-Admin-Key": process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key",
          }
        });
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch (err) {
        console.error("Failed to load stats", err);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  const statCards = [
    {
      name: "Total Candidates",
      value: stats?.total_candidates || 0,
      icon: Users,
      color: "text-blue-500",
      bg: "bg-blue-50",
    },
    {
      name: "Total Interviews",
      value: stats?.total_interviews || 0,
      icon: FileText,
      color: "text-amber-500",
      bg: "bg-amber-50",
    },
    {
      name: "Completed Interviews",
      value: stats?.completed_interviews || 0,
      icon: CheckCircle,
      color: "text-green-500",
      bg: "bg-green-50",
    },
    {
      name: "Average Score",
      value: stats ? `${stats.average_score}%` : "0%",
      icon: TrendingUp,
      color: "text-indigo-500",
      bg: "bg-indigo-50",
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard Overview</h1>
        <p className="text-sm text-slate-500 mt-1">Key metrics for Sarah AI interviews</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat) => (
          <div key={stat.name} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
            <div className={`p-4 rounded-lg ${stat.bg}`}>
              <stat.icon className={`w-6 h-6 ${stat.color}`} />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">{stat.name}</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {loading ? (
                  <div className="h-8 w-16 bg-slate-100 rounded animate-pulse" />
                ) : (
                  stat.value
                )}
              </h3>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
