"use client";

import { useState, useEffect, useCallback } from "react";
import {
  MessageSquare,
  Plus,
  Save,
  Trash2,
  Edit3,
  Check,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Loader2,
  Weight,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  Database,
  Sliders,
  Brain,
} from "lucide-react";

interface Question {
  question_id: string;
  category_id: number;
  category_name_ar: string;
  category_name_en: string;
  category_stage: string;
  question_text_ar: string;
  question_text_en?: string;
  weight: number;
  is_active: boolean;
  display_order: number;
}

interface Category {
  category_id: number;
  category_name_ar: string;
  category_name_en: string;
  questions: Question[];
}

interface RegistrationWeight {
  id: number;
  field_key: string;
  label_ar: string;
  label_en?: string;
  weight: number;
  role_target: string;
  description_ar?: string;
  display_order: number;
  is_active: boolean;
}

interface AiSetting {
  setting_key: string;
  setting_value: string;
  data_type: string;
  label_ar: string;
  label_en?: string;
  description?: string;
  min_value?: number;
  max_value?: number;
  display_order: number;
  is_editable: boolean;
}

type TabId = "questions" | "weights" | "ai";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("questions");
  
  // Questions tab state
  const [categories, setCategories] = useState<Category[]>([]);
  const [expandedCats, setExpandedCats] = useState<Set<number>>(new Set());
  const [editingQ, setEditingQ] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<Question>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newQ, setNewQ] = useState({
    question_text_ar: "",
    question_text_en: "",
    weight: 1.0,
    category_id: 1,
    category_name_ar: "",
    category_name_en: "",
    category_stage: "general",
  });

  // Registration Weights tab state
  const [regWeights, setRegWeights] = useState<RegistrationWeight[]>([]);
  const [roleFilter, setRoleFilter] = useState<string>("cashier");
  const [editingWeight, setEditingWeight] = useState<number | null>(null);
  const [weightEditValue, setWeightEditValue] = useState<number>(0);

  // AI Settings tab state
  const [aiSettings, setAiSettings] = useState<AiSetting[]>([]);
  const [editingSetting, setEditingSetting] = useState<string | null>(null);
  const [settingEditValue, setSettingEditValue] = useState<string>("");

  // Global state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const adminKey = process.env.NEXT_PUBLIC_ADMIN_API_KEY || "dev-admin-key";

  const headers = {
    "Content-Type": "application/json",
    "X-Admin-Key": adminKey,
  };

  // ── Fetch Questions ─────────────────────────

  const fetchQuestions = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiUrl}/api/admin/questions`, { headers });
      if (!res.ok) throw new Error("Failed to fetch questions");
      const json = await res.json();
      setCategories(json.categories || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, adminKey]);

  // ── Fetch Registration Weights ──────────────

  const fetchRegWeights = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiUrl}/api/admin/registration-weights?role_target=${roleFilter}`, { headers });
      if (!res.ok) throw new Error("Failed to fetch weights");
      const json = await res.json();
      setRegWeights(json.weights || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, adminKey, roleFilter]);

  // ── Fetch AI Settings ───────────────────────

  const fetchAiSettings = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiUrl}/api/admin/ai-settings`, { headers });
      if (!res.ok) throw new Error("Failed to fetch AI settings");
      const json = await res.json();
      setAiSettings(json.settings || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, adminKey]);

  // ── Initial Load ────────────────────────────

  useEffect(() => {
    if (activeTab === "questions") fetchQuestions();
    else if (activeTab === "weights") fetchRegWeights();
    else if (activeTab === "ai") fetchAiSettings();
  }, [activeTab, fetchQuestions, fetchRegWeights, fetchAiSettings]);

  // ── Toggle Category ────────────────────────

  const toggleCategory = (catId: number) => {
    setExpandedCats((prev) => {
      const next = new Set(prev);
      next.has(catId) ? next.delete(catId) : next.add(catId);
      return next;
    });
  };

  // ── Edit Question ──────────────────────────

  const startEdit = (q: Question) => {
    setEditingQ(q.question_id);
    setEditForm({
      question_text_ar: q.question_text_ar,
      question_text_en: q.question_text_en || "",
      weight: q.weight,
      is_active: q.is_active,
    });
  };

  const cancelEdit = () => {
    setEditingQ(null);
    setEditForm({});
  };

  const saveEdit = async (questionId: string) => {
    setSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/admin/questions/${questionId}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(editForm),
      });
      if (!res.ok) throw new Error("Failed to update");
      setEditingQ(null);
      setSaveMsg("تم الحفظ ✓");
      setTimeout(() => setSaveMsg(""), 2000);
      fetchQuestions();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  // ── Toggle Active ──────────────────────────

  const toggleActive = async (q: Question) => {
    try {
      await fetch(`${apiUrl}/api/admin/questions/${q.question_id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ is_active: !q.is_active }),
      });
      fetchQuestions();
    } catch (err) {
      console.error(err);
    }
  };

  // ── Delete Question ────────────────────────

  const deleteQuestion = async (questionId: string) => {
    if (!confirm("هل تريد حذف هذا السؤال؟ (سيتم تعطيله وليس حذفه نهائياً)")) return;
    try {
      await fetch(`${apiUrl}/api/admin/questions/${questionId}`, {
        method: "DELETE",
        headers,
      });
      fetchQuestions();
    } catch (err) {
      console.error(err);
    }
  };

  // ── Add Question ───────────────────────────

  const addQuestion = async () => {
    if (!newQ.question_text_ar.trim()) return;
    setSaving(true);
    try {
      // Find category info
      const cat = categories.find((c) => c.category_id === newQ.category_id);
      const body = {
        ...newQ,
        category_name_ar: cat?.category_name_ar || newQ.category_name_ar,
        category_name_en: cat?.category_name_en || newQ.category_name_en,
      };

      const res = await fetch(`${apiUrl}/api/admin/questions`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to add question");

      setNewQ({ question_text_ar: "", question_text_en: "", weight: 1.0, category_id: newQ.category_id, category_name_ar: "", category_name_en: "", category_stage: "general" });
      setShowAddForm(false);
      setSaveMsg("تمت إضافة السؤال ✓");
      setTimeout(() => setSaveMsg(""), 2000);
      fetchQuestions();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  // ── Update Registration Weight ─────────────

  const saveWeightEdit = async (weightId: number) => {
    setSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/admin/registration-weights/${weightId}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ weight: weightEditValue }),
      });
      if (!res.ok) throw new Error("Failed to update weight");
      setEditingWeight(null);
      setSaveMsg("تم الحفظ ✓");
      setTimeout(() => setSaveMsg(""), 2000);
      fetchRegWeights();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  // ── Update AI Setting ───────────────────────

  const saveSettingEdit = async (settingKey: string) => {
    setSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/admin/ai-settings/${settingKey}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ setting_value: settingEditValue }),
      });
      if (!res.ok) throw new Error("Failed to update setting");
      setEditingSetting(null);
      setSaveMsg("تم الحفظ ✓");
      setTimeout(() => setSaveMsg(""), 2000);
      fetchAiSettings();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  // ── Refresh MV ─────────────────────────────

  const refreshDashboard = async () => {
    setRefreshing(true);
    try {
      await fetch(`${apiUrl}/api/admin/dashboard/stats`, { headers });
      setSaveMsg("تم تحديث لوحة التحكم ✓");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  };

  // ── Render ─────────────────────────────────

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
        <p className="mt-4 text-slate-500">جاري تحميل الإعدادات...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <AlertTriangle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-xl font-bold text-slate-900">خطأ في تحميل الإعدادات</h2>
        <p className="text-slate-500 mt-2">{error}</p>
      </div>
    );
  }

  const totalActive = categories.reduce((sum, c) => sum + c.questions.filter((q) => q.is_active).length, 0);
  const totalAll = categories.reduce((sum, c) => sum + c.questions.length, 0);
  const weightsTotal = regWeights.reduce((sum, w) => sum + w.weight, 0);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">إعدادات النظام</h1>
          <p className="text-sm text-slate-500 mt-1">
            إدارة أسئلة المقابلة، أوزان التسجيل، وإعدادات الذكاء الاصطناعي
          </p>
        </div>
        <div className="flex items-center gap-3">
          {saveMsg && (
            <span className="text-sm font-medium text-green-600 animate-pulse">{saveMsg}</span>
          )}
          <button
            onClick={refreshDashboard}
            disabled={refreshing}
            className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
            تحديث
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab("questions")}
            className={`flex-1 px-6 py-4 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
              activeTab === "questions"
                ? "bg-amber-50 text-amber-700 border-b-2 border-amber-500"
                : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            أسئلة المقابلة
          </button>
          <button
            onClick={() => setActiveTab("weights")}
            className={`flex-1 px-6 py-4 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
              activeTab === "weights"
                ? "bg-amber-50 text-amber-700 border-b-2 border-amber-500"
                : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            <Weight className="w-4 h-4" />
            أوزان التسجيل
          </button>
          <button
            onClick={() => setActiveTab("ai")}
            className={`flex-1 px-6 py-4 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
              activeTab === "ai"
                ? "bg-amber-50 text-amber-700 border-b-2 border-amber-500"
                : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            <Brain className="w-4 h-4" />
            إعدادات الذكاء الاصطناعي
          </button>
        </div>

        <div className="p-6">
          {/* TAB 1: Questions */}
          {activeTab === "questions" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-600">
                  {totalActive} سؤال نشط من {totalAll}
                </p>
                <button
                  onClick={() => setShowAddForm(!showAddForm)}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  إضافة سؤال
                </button>
              </div>

      {/* Add Question Form */}
      {showAddForm && (
        <div className="bg-amber-50 rounded-xl border border-amber-200 p-6 space-y-4">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <Plus className="w-4 h-4 text-amber-600" />
            إضافة سؤال جديد
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">الفئة</label>
              <select
                value={newQ.category_id}
                onChange={(e) => setNewQ({ ...newQ, category_id: parseInt(e.target.value) })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              >
                {categories.map((c) => (
                  <option key={c.category_id} value={c.category_id}>
                    {c.category_name_ar} ({c.category_name_en})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">الوزن</label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                max="5"
                value={newQ.weight}
                onChange={(e) => setNewQ({ ...newQ, weight: parseFloat(e.target.value) })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">نص السؤال (عربي) *</label>
            <textarea
              value={newQ.question_text_ar}
              onChange={(e) => setNewQ({ ...newQ, question_text_ar: e.target.value })}
              placeholder="أدخل نص السؤال بالعربية..."
              rows={2}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              dir="rtl"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={() => setShowAddForm(false)} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
              إلغاء
            </button>
            <button
              onClick={addQuestion}
              disabled={saving || !newQ.question_text_ar.trim()}
              className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              إضافة
            </button>
          </div>
        </div>
      )}

      {/* Question Categories */}
      <div className="space-y-4">
        {categories.map((cat) => {
          const isExpanded = expandedCats.has(cat.category_id);
          const activeCount = cat.questions.filter((q) => q.is_active).length;

          return (
            <div key={cat.category_id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              {/* Category Header */}
              <button
                onClick={() => toggleCategory(cat.category_id)}
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  {isExpanded ? <ChevronDown className="w-5 h-5 text-slate-400" /> : <ChevronRight className="w-5 h-5 text-slate-400" />}
                  <div className="text-left">
                    <h3 className="font-semibold text-slate-900">{cat.category_name_ar}</h3>
                    <p className="text-xs text-slate-500">{cat.category_name_en} — {activeCount} سؤال نشط</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-xs font-semibold">
                    {cat.questions.length} أسئلة
                  </span>
                </div>
              </button>

              {/* Questions List */}
              {isExpanded && (
                <div className="border-t border-slate-100 divide-y divide-slate-50">
                  {cat.questions.map((q) => (
                    <div
                      key={q.question_id}
                      className={`px-6 py-4 flex items-start gap-4 transition-colors ${
                        !q.is_active ? "opacity-50 bg-slate-50" : "hover:bg-slate-50/50"
                      }`}
                    >
                      {/* Toggle Active */}
                      <button onClick={() => toggleActive(q)} className="mt-0.5 flex-shrink-0">
                        {q.is_active ? (
                          <ToggleRight className="w-6 h-6 text-green-500" />
                        ) : (
                          <ToggleLeft className="w-6 h-6 text-slate-300" />
                        )}
                      </button>

                      {/* Question Content */}
                      <div className="flex-1 min-w-0">
                        {editingQ === q.question_id ? (
                          /* Edit Mode */
                          <div className="space-y-3">
                            <textarea
                              value={editForm.question_text_ar || ""}
                              onChange={(e) => setEditForm({ ...editForm, question_text_ar: e.target.value })}
                              rows={2}
                              className="w-full border border-amber-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/30"
                              dir="rtl"
                            />
                            <div className="flex items-center gap-3">
                              <label className="text-xs text-slate-500">الوزن:</label>
                              <input
                                type="number"
                                step="0.5"
                                min="0.5"
                                max="5"
                                value={editForm.weight || 1}
                                onChange={(e) => setEditForm({ ...editForm, weight: parseFloat(e.target.value) })}
                                className="w-20 border border-slate-200 rounded-md px-2 py-1 text-sm"
                              />
                              <button
                                onClick={() => saveEdit(q.question_id)}
                                disabled={saving}
                                className="px-3 py-1 bg-green-500 text-white text-xs font-medium rounded-md hover:bg-green-600"
                              >
                                {saving ? "..." : "حفظ"}
                              </button>
                              <button onClick={cancelEdit} className="px-3 py-1 text-slate-500 text-xs hover:bg-slate-100 rounded-md">
                                إلغاء
                              </button>
                            </div>
                          </div>
                        ) : (
                          /* View Mode */
                          <div>
                            <p className="text-sm text-slate-900 leading-relaxed" dir="rtl">{q.question_text_ar}</p>
                            <div className="flex items-center gap-3 mt-1.5">
                              <span className="text-xs text-slate-400">{q.question_id}</span>
                              <span className="text-xs text-slate-400">•</span>
                              <span className="text-xs font-medium text-amber-600">الوزن: {q.weight}</span>
                              {!q.is_active && (
                                <span className="text-xs text-red-500 font-medium">معطّل</span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Action Buttons */}
                      {editingQ !== q.question_id && (
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button
                            onClick={() => startEdit(q)}
                            className="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-md transition-colors"
                            title="تعديل"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteQuestion(q.question_id)}
                            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                            title="حذف"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
            </div>
          )}

          {/* TAB 2: Registration Weights */}
          {activeTab === "weights" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-600">
                  إجمالي الأوزان: {(weightsTotal * 100).toFixed(0)}%
                  {Math.abs(weightsTotal - 1.0) > 0.01 && (
                    <span className="text-amber-600 mr-2">⚠ يجب أن يساوي 100%</span>
                  )}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setRoleFilter("cashier")}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      roleFilter === "cashier"
                        ? "bg-amber-500 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    كاشير
                  </button>
                  <button
                    onClick={() => setRoleFilter("supervisor")}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      roleFilter === "supervisor"
                        ? "bg-amber-500 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    مشرف
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                {regWeights.map((w) => (
                  <div
                    key={w.id}
                    className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200 hover:border-amber-300 transition-colors"
                  >
                    <div className="flex-1">
                      <h4 className="font-semibold text-slate-900">{w.label_ar}</h4>
                      {w.description_ar && (
                        <p className="text-xs text-slate-500 mt-0.5">{w.description_ar}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {editingWeight === w.id ? (
                        <>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={weightEditValue}
                            onChange={(e) => setWeightEditValue(parseFloat(e.target.value))}
                            className="w-20 border border-amber-300 rounded-md px-2 py-1 text-sm text-center"
                          />
                          <button
                            onClick={() => saveWeightEdit(w.id)}
                            disabled={saving}
                            className="px-3 py-1 bg-green-500 text-white text-xs font-medium rounded-md hover:bg-green-600"
                          >
                            {saving ? "..." : "حفظ"}
                          </button>
                          <button
                            onClick={() => setEditingWeight(null)}
                            className="px-3 py-1 text-slate-500 text-xs hover:bg-slate-100 rounded-md"
                          >
                            إلغاء
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="text-2xl font-bold text-amber-600">
                            {(w.weight * 100).toFixed(0)}%
                          </span>
                          <button
                            onClick={() => {
                              setEditingWeight(w.id);
                              setWeightEditValue(w.weight);
                            }}
                            className="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-md transition-colors"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: AI Settings */}
          {activeTab === "ai" && (
            <div className="space-y-6">
              <p className="text-sm text-slate-600">
                إعدادات الذكاء الاصطناعي لتقييم المقابلات
              </p>

              <div className="space-y-3">
                {aiSettings.map((s) => (
                  <div
                    key={s.setting_key}
                    className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200 hover:border-amber-300 transition-colors"
                  >
                    <div className="flex-1">
                      <h4 className="font-semibold text-slate-900">{s.label_ar}</h4>
                      {s.description && (
                        <p className="text-xs text-slate-500 mt-0.5">{s.description}</p>
                      )}
                      {s.min_value !== null && s.max_value !== null && (
                        <p className="text-xs text-slate-400 mt-1">
                          النطاق: {s.min_value} - {s.max_value}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {editingSetting === s.setting_key ? (
                        <>
                          <input
                            type={s.data_type === "number" ? "number" : "text"}
                            step={s.data_type === "number" ? "0.01" : undefined}
                            min={s.min_value ?? undefined}
                            max={s.max_value ?? undefined}
                            value={settingEditValue}
                            onChange={(e) => setSettingEditValue(e.target.value)}
                            className="w-24 border border-amber-300 rounded-md px-2 py-1 text-sm text-center"
                          />
                          <button
                            onClick={() => saveSettingEdit(s.setting_key)}
                            disabled={saving}
                            className="px-3 py-1 bg-green-500 text-white text-xs font-medium rounded-md hover:bg-green-600"
                          >
                            {saving ? "..." : "حفظ"}
                          </button>
                          <button
                            onClick={() => setEditingSetting(null)}
                            className="px-3 py-1 text-slate-500 text-xs hover:bg-slate-100 rounded-md"
                          >
                            إلغاء
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="text-lg font-bold text-amber-600">
                            {s.data_type === "number" && s.setting_key.startsWith("weight_")
                              ? `${(parseFloat(s.setting_value) * 100).toFixed(0)}%`
                              : s.setting_value}
                          </span>
                          <button
                            onClick={() => {
                              setEditingSetting(s.setting_key);
                              setSettingEditValue(s.setting_value);
                            }}
                            className="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-md transition-colors"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
