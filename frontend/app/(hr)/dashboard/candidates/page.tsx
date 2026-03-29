"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Search, ChevronUp, ChevronDown, Filter, Users, Upload, X, FileSpreadsheet, CheckCircle, AlertCircle } from "lucide-react";

export default function CandidatesListPage() {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("candidate_created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [filterStatus, setFilterStatus] = useState("all");

  // Import drawer state
  const [showImportDrawer, setShowImportDrawer] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

  useEffect(() => {
    fetchCandidates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortBy, sortOrder, filterStatus]); // Refresh when sort/filter changes

  const fetchCandidates = async () => {
    try {
      setLoading(true);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

      // We pass query params matching backend: /api/admin/candidates
      const params = new URLSearchParams();
      if (filterStatus !== "all") params.append("status", filterStatus);
      params.append("sort_by", sortBy);
      params.append("sort_order", sortOrder);

      const res = await fetch(`${apiUrl}/api/admin/candidates?${params.toString()}`, {
        headers: {
          // Dev API key or auth token. We'll use the API key if defined, or assume auth is handled 
          // Assuming proxy or a dev key for admin
          "X-Admin-Key": process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key",
        }
      });

      if (!res.ok) throw new Error("Failed to fetch candidates");

      const data = await res.json();
      setCandidates(data.candidates || []);
    } catch (error) {
      console.error("Error fetching candidates:", error);
    } finally {
      setLoading(false);
    }
  };

  const filteredCandidates = candidates.filter((c) =>
    c.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.target_role?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getScoreBadgeColor = (score: number | null | undefined) => {
    if (score == null) return "bg-slate-100 text-slate-800 border-slate-200";
    if (score >= 80) return "bg-green-50 text-green-700 border-green-200";
    if (score >= 60) return "bg-amber-50 text-amber-700 border-amber-200";
    return "bg-red-50 text-red-700 border-red-200";
  };

  const getRecommendationBadge = (recommendation: string | null | undefined) => {
    switch (recommendation) {
      case "strongly_recommend":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-500 text-white shadow-sm">مقبول بشدة</span>;
      case "recommend":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-400 text-white shadow-sm">مقبول</span>;
      case "neutral":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-400 text-slate-900 shadow-sm">محتمل</span>;
      case "not_recommend":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-400 text-white shadow-sm">غير مناسب</span>;
      case "reject":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500 text-white shadow-sm">مرفوض</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700 shadow-sm">غير مقيّم</span>;
    }
  };

  const getStatusBadge = (status: string | null | undefined) => {
    if (!status) return <span className="text-slate-500 text-xs">New</span>;
    switch (status.toLowerCase()) {
      case "completed":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">Completed</span>;
      case "in_progress":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">In Progress</span>;
      case "pending":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-300">Pending</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 capitalize">{status.replace('_', ' ')}</span>;
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setImportResult(null);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) return;
    setImporting(true);
    setImportResult(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const adminKey = process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key";

      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch(`${apiUrl}/api/admin/import/candidates`, {
        method: "POST",
        headers: {
          "X-Admin-Key": adminKey,
        },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Import failed");
      }

      const result = await res.json();
      setImportResult(result);
      setSelectedFile(null);
      
      // Refresh candidates list
      if (result.imported > 0) {
        fetchCandidates();
      }
    } catch (err: any) {
      setImportResult({ status: "error", message: err.message });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Candidates</h1>
          <p className="text-sm text-slate-500 mt-1">Manage and review applicant interviews</p>
        </div>
        <button
          onClick={() => setShowImportDrawer(true)}
          className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
        >
          <Upload className="w-4 h-4" />
          استيراد من Excel
        </button>
      </div>

      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search by name or role..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 transition-all"
          />
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-500" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 shadow-sm"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="in_progress">In Progress</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
              <tr>
                <th
                  className="px-6 py-3 font-medium cursor-pointer hover:bg-slate-100 transition-colors"
                  onClick={() => toggleSort("full_name")}
                >
                  <div className="flex items-center gap-2">
                    Candidate
                    {sortBy === "full_name" && (sortOrder === "asc" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />)}
                  </div>
                </th>
                <th className="px-6 py-3 font-medium">Role applied</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th
                  className="px-6 py-3 font-medium cursor-pointer hover:bg-slate-100 transition-colors"
                  onClick={() => toggleSort("final_score")}
                >
                  <div className="flex items-center gap-2">
                    Score
                    {sortBy === "final_score" && (sortOrder === "asc" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />)}
                  </div>
                </th>
                <th className="px-6 py-3 font-medium">Decision</th>
                <th
                  className="px-6 py-3 font-medium cursor-pointer hover:bg-slate-100 transition-colors"
                  onClick={() => toggleSort("candidate_created_at")}
                >
                  <div className="flex items-center gap-2">
                    Date
                    {sortBy === "candidate_created_at" && (sortOrder === "asc" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />)}
                  </div>
                </th>
                <th className="px-6 py-3 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                      Loading candidates...
                    </div>
                  </td>
                </tr>
              ) : filteredCandidates.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center text-slate-400">
                      <Users className="w-12 h-12 mb-2 opacity-20" />
                      No candidates found.
                    </div>
                  </td>
                </tr>
              ) : (
                filteredCandidates.map((candidate) => {
                  /* 
                    Because the API query might be from `candidates` table (fallback) or `mv_admin_dashboard` (materialized view), 
                    the fields can be flat (c.final_score) or nested (c.score?.final_score).
                  */
                  const cId = candidate.candidate_id || candidate.id;
                  const scoreObj = candidate.score || candidate; // fallback to self if materialized
                  const intObj = candidate.interview || candidate; // fallback to self if materialized

                  return (
                    <tr key={cId} className="hover:bg-slate-50/50 transition-colors group">
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-900">{candidate.full_name}</div>
                        <div className="text-xs text-slate-500">{candidate.phone_number || candidate.email}</div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-slate-700">{candidate.target_role}</span>
                        {candidate.years_of_experience > 0 && (
                          <div className="text-xs text-slate-500">{candidate.years_of_experience} yrs exp</div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {getStatusBadge(intObj?.interview_status || intObj?.status)}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-sm font-semibold border ${getScoreBadgeColor(scoreObj?.final_score)}`}>
                          {scoreObj?.final_score ? `${Math.round(scoreObj.final_score)}%` : "--"}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {getRecommendationBadge(scoreObj?.hire_recommendation)}
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-sm">
                        {new Date(candidate.candidate_created_at || candidate.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/dashboard/candidates/${cId}`}
                          className="inline-flex items-center px-3 py-1.5 bg-white border border-slate-200 rounded-md text-sm font-medium text-slate-700 hover:border-amber-500 hover:text-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all opacity-0 group-hover:opacity-100"
                        >
                          View Details
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Import Drawer */}
      {showImportDrawer && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-200">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="w-6 h-6 text-amber-600" />
                <h2 className="text-xl font-bold text-slate-900">استيراد المرشحين</h2>
              </div>
              <button
                onClick={() => {
                  setShowImportDrawer(false);
                  setSelectedFile(null);
                  setImportResult(null);
                }}
                className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {!importResult ? (
                <>
                  {/* File Upload */}
                  <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-amber-400 transition-colors">
                    <input
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      onChange={handleFileSelect}
                      className="hidden"
                      id="file-upload"
                    />
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                      <p className="text-sm font-medium text-slate-700 mb-1">
                        اسحب الملف هنا أو انقر للاختيار
                      </p>
                      <p className="text-xs text-slate-500">
                        Excel (.xlsx, .xls) أو CSV (.csv)
                      </p>
                    </label>
                  </div>

                  {selectedFile && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <FileSpreadsheet className="w-8 h-8 text-amber-600" />
                          <div>
                            <p className="font-medium text-slate-900">{selectedFile.name}</p>
                            <p className="text-xs text-slate-500">
                              {(selectedFile.size / 1024).toFixed(1)} KB
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => setSelectedFile(null)}
                          className="p-1 hover:bg-amber-100 rounded transition-colors"
                        >
                          <X className="w-4 h-4 text-slate-500" />
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Column Mapping Info */}
                  <div className="bg-slate-50 rounded-lg p-4">
                    <h3 className="font-semibold text-slate-900 mb-3">الأعمدة المطلوبة:</h3>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-slate-700">الاسم الكامل *</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-slate-700">رقم الهاتف *</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <div className="w-4 h-4" />
                        <span>الوظيفة المطلوبة</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <div className="w-4 h-4" />
                        <span>سنوات الخبرة</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <div className="w-4 h-4" />
                        <span>الراتب المتوقع</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <div className="w-4 h-4" />
                        <span>المنطقة السكنية</span>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mt-3">* حقول إلزامية</p>
                  </div>
                </>
              ) : (
                /* Import Result */
                <div className="space-y-4">
                  {importResult.status === "error" ? (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                      <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
                      <h3 className="font-semibold text-red-900 mb-2">فشل الاستيراد</h3>
                      <p className="text-sm text-red-700">{importResult.message}</p>
                    </div>
                  ) : (
                    <>
                      <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
                        <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                        <h3 className="font-semibold text-green-900 mb-2">تم الاستيراد بنجاح!</h3>
                        <div className="grid grid-cols-3 gap-4 mt-4">
                          <div>
                            <p className="text-2xl font-bold text-green-600">{importResult.imported}</p>
                            <p className="text-xs text-slate-600">تم الاستيراد</p>
                          </div>
                          <div>
                            <p className="text-2xl font-bold text-amber-600">{importResult.skipped}</p>
                            <p className="text-xs text-slate-600">تم التخطي</p>
                          </div>
                          <div>
                            <p className="text-2xl font-bold text-red-600">{importResult.error_count}</p>
                            <p className="text-xs text-slate-600">أخطاء</p>
                          </div>
                        </div>
                      </div>

                      {importResult.errors && importResult.errors.length > 0 && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                          <h4 className="font-semibold text-red-900 mb-2 text-sm">الأخطاء:</h4>
                          <div className="space-y-2 max-h-40 overflow-y-auto">
                            {importResult.errors.slice(0, 5).map((err: any, i: number) => (
                              <div key={i} className="text-xs text-red-700">
                                <span className="font-medium">صف {err.row}:</span> {err.reason}
                              </div>
                            ))}
                            {importResult.errors.length > 5 && (
                              <p className="text-xs text-red-600">... و {importResult.errors.length - 5} أخطاء أخرى</p>
                            )}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-slate-200 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowImportDrawer(false);
                  setSelectedFile(null);
                  setImportResult(null);
                }}
                className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                {importResult ? "إغلاق" : "إلغاء"}
              </button>
              {!importResult && (
                <button
                  onClick={handleImport}
                  disabled={!selectedFile || importing}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {importing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      جاري الاستيراد...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      استيراد الآن
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
