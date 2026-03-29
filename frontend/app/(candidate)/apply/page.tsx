"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { createSupabaseClient } from "@/lib/supabase/client";
import { toast } from "sonner";

// ─────────────────────────────────────────────
// Zod Schema — all validation with Arabic messages
// ─────────────────────────────────────────────

const registerSchema = z.object({
  // Section 1: Personal
  full_name: z.string().min(3, "الاسم يجب أن يكون 3 أحرف على الأقل"),
  phone_number: z
    .string()
    .regex(/^07[0-9]{8}$/, "رقم الهاتف يجب أن يبدأ بـ 07 ويتكون من 10 أرقام"),
  date_of_birth: z.string().min(1, "يرجى إدخال تاريخ الميلاد"),
  gender: z.enum(["ذكر", "انثى"], { message: "يرجى اختيار الجنس" }),
  nationality: z.enum(["أردني", "جنسية أخرى"], { message: "يرجى اختيار الجنسية" }),
  marital_status: z.enum(["اعزب", "متزوج", "مطلق", "ارمل"], { message: "يرجى اختيار الحالة الاجتماعية" }),
  detailed_residence: z.string().min(3, "يرجى إدخال العنوان"),

  // Section 2: Job
  target_role: z.enum(
    ["خباز", "كاشير", "سائق توصيل", "عامل نظافة", "تعبئة وتغليف", "موظف مبيعات في المعرض", "مدير فرع", "مساعد خباز", "عامل مستودعات"],
    { message: "يرجى اختيار الوظيفة" }
  ),
  years_of_experience: z.coerce.number().min(0, "الحد الأدنى 0").max(50, "الحد الأقصى 50"),
  has_field_experience: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),
  expected_salary: z.coerce.number().min(200, "الحد الأدنى 200 دينار").max(2000, "الحد الأقصى 2000 دينار"),
  preferred_schedule: z.enum(["صباحي", "مسائي", "أي وردية"], { message: "يرجى اختيار الوردية" }),
  can_start_immediately: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),

  // Section 3: Additional
  age_range: z.enum(["18-21", "22-25", "26 فأكثر"], { message: "يرجى اختيار الفئة العمرية" }),
  academic_status: z.enum(
    ["لا يوجد نية لاستكمال الدراسة", "أكمل مسيرتي الدراسية", "انتهيت من المسيرة الدراسية (متخرج)"],
    { message: "يرجى اختيار المسار الدراسي" }
  ),
  academic_qualification: z.enum(
    ["مؤهل للجامعة (توجيهي ناجح)", "توجيهي راسب", "جامعي", "متخرج"],
    { message: "يرجى اختيار المؤهل الأكاديمي" }
  ),
  proximity_to_branch: z.enum(
    ["قريب وأحضر مشياً على الاقدام", "قريب بنفس المنطقة واحضر مواصلات", "خارج المنطقة وأحضر مواصلات أو تكسي", "خارج المحافظة"],
    { message: "يرجى اختيار قرب السكن" }
  ),
  has_relatives_at_company: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),
  previously_at_qabalan: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),
  social_security_issues: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),

  // Section 4: Commitments
  prayer_regularity: z.enum(["نعم الحمد لله", "ليس بشكل منتظم"], { message: "يرجى الاختيار" }),
  is_smoker: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),
  grooming_objection: z.enum(["نعم", "لا"], { message: "يرجى الاختيار" }),
});

type RegisterForm = z.infer<typeof registerSchema>;

// ─────────────────────────────────────────────
// Shared UI Helpers
// ─────────────────────────────────────────────

const inputClass =
  "mt-1.5 block w-full rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3 text-amber-900 placeholder-amber-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 focus:outline-none text-sm";

const selectClass =
  "mt-1.5 block w-full rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3 text-amber-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 focus:outline-none text-sm appearance-none";

const labelClass = "block text-sm font-semibold text-amber-900";

const errorClass = "mt-1 text-xs text-red-600";

const requiredStar = <span className="text-red-500 mr-1">*</span>;

// ─────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────

export default function ApplyPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      years_of_experience: 0,
      expected_salary: 300,
      nationality: "أردني",
      has_field_experience: "لا",
      previously_at_qabalan: "لا",
      social_security_issues: "لا",
      is_smoker: "لا",
    },
  });

  const onSubmit = async (data: RegisterForm) => {
    if (isSubmitting) return;
    setIsSubmitting(true);

    try {
      const supabase = createSupabaseClient();

      const { data: result, error } = await supabase
        .from("candidates")
        .insert({
          full_name: data.full_name.trim(),
          phone_number: data.phone_number.trim(),
          date_of_birth: data.date_of_birth,
          gender: data.gender,
          nationality: data.nationality,
          marital_status: data.marital_status,
          detailed_residence: data.detailed_residence.trim(),
          target_role: data.target_role,
          years_of_experience: data.years_of_experience,
          has_field_experience: data.has_field_experience,
          expected_salary: data.expected_salary,
          preferred_schedule: data.preferred_schedule,
          can_start_immediately: data.can_start_immediately,
          age_range: data.age_range,
          academic_status: data.academic_status,
          academic_qualification: data.academic_qualification,
          proximity_to_branch: data.proximity_to_branch,
          has_relatives_at_company: data.has_relatives_at_company,
          previously_at_qabalan: data.previously_at_qabalan,
          social_security_issues: data.social_security_issues,
          prayer_regularity: data.prayer_regularity,
          is_smoker: data.is_smoker,
          grooming_objection: data.grooming_objection,
          company_name: "Qabalan",
          application_source: "web_form",
          registration_form_data: data, // full JSON backup
        })
        .select("id")
        .single();

      if (error) {
        if (error.code === "23505") {
          toast.error("رقم الهاتف مسجل مسبقاً");
          return;
        }
        throw error;
      }

      if (!result?.id) throw new Error("لم يتم إرجاع معرف المتقدم");

      toast.success("تم تقديم الطلب بنجاح! سيتم تحويلك للمقابلة الصوتية...");
      router.push(`/interview/${result.id}`);
    } catch (err) {
      console.error("Submit error:", err);
      toast.error(
        err instanceof Error ? err.message : "حدث خطأ. يرجى المحاولة مرة أخرى."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main
      dir="rtl"
      className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50/30 to-yellow-50"
    >
      {/* Background Pattern */}
      <div className="fixed inset-0 opacity-[0.02] pointer-events-none">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, #92400e 1px, transparent 0)`,
            backgroundSize: "32px 32px",
          }}
        />
      </div>

      <div className="relative mx-auto max-w-2xl px-4 py-8 sm:px-6 sm:py-12">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-amber-500/25 mb-4">
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-amber-900 sm:text-4xl">
            نموذج طلب التوظيف
          </h1>
          <p className="mt-2 text-amber-700/80 text-lg">
            شركة قبلان للصناعات الغذائية
          </p>
          <div className="mt-3 inline-flex items-center gap-2 bg-amber-100/60 text-amber-800 text-sm px-4 py-1.5 rounded-full">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            مقابلة صوتية مع سارة بعد التسجيل
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* ═══════════════════════════════════════════ */}
          {/* Section 1: Personal Info */}
          {/* ═══════════════════════════════════════════ */}
          <fieldset className="rounded-2xl bg-white/80 backdrop-blur-sm p-5 sm:p-7 shadow-lg ring-1 ring-amber-100/80">
            <legend className="flex items-center gap-2 text-lg font-bold text-amber-800 px-2">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-amber-100 text-amber-700 text-sm font-bold">
                ١
              </span>
              المعلومات الشخصية
            </legend>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Full Name */}
              <div className="sm:col-span-2">
                <label htmlFor="full_name" className={labelClass}>
                  {requiredStar} الاسم الكامل
                </label>
                <input
                  id="full_name"
                  type="text"
                  {...register("full_name")}
                  className={inputClass}
                  placeholder="مثال: أحمد محمد القبلاني"
                  disabled={isSubmitting}
                />
                {errors.full_name && (
                  <p className={errorClass}>{errors.full_name.message}</p>
                )}
              </div>

              {/* Phone */}
              <div>
                <label htmlFor="phone_number" className={labelClass}>
                  {requiredStar} رقم الهاتف
                </label>
                <input
                  id="phone_number"
                  type="tel"
                  dir="ltr"
                  {...register("phone_number")}
                  className={`${inputClass} text-left`}
                  placeholder="07XXXXXXXX"
                  disabled={isSubmitting}
                />
                {errors.phone_number && (
                  <p className={errorClass}>{errors.phone_number.message}</p>
                )}
              </div>

              {/* DOB */}
              <div>
                <label htmlFor="date_of_birth" className={labelClass}>
                  {requiredStar} تاريخ الميلاد
                </label>
                <input
                  id="date_of_birth"
                  type="date"
                  {...register("date_of_birth")}
                  className={inputClass}
                  disabled={isSubmitting}
                />
                {errors.date_of_birth && (
                  <p className={errorClass}>{errors.date_of_birth.message}</p>
                )}
              </div>

              {/* Gender */}
              <div>
                <label htmlFor="gender" className={labelClass}>
                  {requiredStar} الجنس
                </label>
                <select
                  id="gender"
                  {...register("gender")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="ذكر">ذكر</option>
                  <option value="انثى">انثى</option>
                </select>
                {errors.gender && (
                  <p className={errorClass}>{errors.gender.message}</p>
                )}
              </div>

              {/* Nationality */}
              <div>
                <label htmlFor="nationality" className={labelClass}>
                  {requiredStar} الجنسية
                </label>
                <select
                  id="nationality"
                  {...register("nationality")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="أردني">أردني</option>
                  <option value="جنسية أخرى">جنسية أخرى</option>
                </select>
                {errors.nationality && (
                  <p className={errorClass}>{errors.nationality.message}</p>
                )}
              </div>

              {/* Marital Status */}
              <div>
                <label htmlFor="marital_status" className={labelClass}>
                  {requiredStar} الحالة الاجتماعية
                </label>
                <select
                  id="marital_status"
                  {...register("marital_status")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="اعزب">أعزب</option>
                  <option value="متزوج">متزوج</option>
                  <option value="مطلق">مطلق</option>
                  <option value="ارمل">أرمل</option>
                </select>
                {errors.marital_status && (
                  <p className={errorClass}>{errors.marital_status.message}</p>
                )}
              </div>

              {/* Address */}
              <div className="sm:col-span-2">
                <label htmlFor="detailed_residence" className={labelClass}>
                  {requiredStar} العنوان التفصيلي
                </label>
                <input
                  id="detailed_residence"
                  type="text"
                  {...register("detailed_residence")}
                  className={inputClass}
                  placeholder="مثال: عمّان - ماركا الشمالية - شارع الحرية"
                  disabled={isSubmitting}
                />
                {errors.detailed_residence && (
                  <p className={errorClass}>
                    {errors.detailed_residence.message}
                  </p>
                )}
              </div>
            </div>
          </fieldset>

          {/* ═══════════════════════════════════════════ */}
          {/* Section 2: Job Info */}
          {/* ═══════════════════════════════════════════ */}
          <fieldset className="rounded-2xl bg-white/80 backdrop-blur-sm p-5 sm:p-7 shadow-lg ring-1 ring-amber-100/80">
            <legend className="flex items-center gap-2 text-lg font-bold text-amber-800 px-2">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-amber-100 text-amber-700 text-sm font-bold">
                ٢
              </span>
              معلومات التوظيف
            </legend>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Target Role */}
              <div className="sm:col-span-2">
                <label htmlFor="target_role" className={labelClass}>
                  {requiredStar} الوظيفة المطلوبة
                </label>
                <select
                  id="target_role"
                  {...register("target_role")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر الوظيفة —</option>
                  <option value="خباز">خباز</option>
                  <option value="مساعد خباز">مساعد خباز</option>
                  <option value="كاشير">كاشير</option>
                  <option value="سائق توصيل">سائق توصيل</option>
                  <option value="موظف مبيعات في المعرض">
                    موظف مبيعات في المعرض
                  </option>
                  <option value="عامل نظافة">عامل نظافة</option>
                  <option value="تعبئة وتغليف">تعبئة وتغليف</option>
                  <option value="عامل مستودعات">عامل مستودعات</option>
                  <option value="مدير فرع">مدير فرع</option>
                </select>
                {errors.target_role && (
                  <p className={errorClass}>{errors.target_role.message}</p>
                )}
              </div>

              {/* Years of Experience */}
              <div>
                <label htmlFor="years_of_experience" className={labelClass}>
                  {requiredStar} سنوات الخبرة
                </label>
                <input
                  id="years_of_experience"
                  type="number"
                  min={0}
                  max={50}
                  {...register("years_of_experience")}
                  className={inputClass}
                  disabled={isSubmitting}
                />
                {errors.years_of_experience && (
                  <p className={errorClass}>
                    {errors.years_of_experience.message}
                  </p>
                )}
              </div>

              {/* Has Field Experience */}
              <div>
                <label htmlFor="has_field_experience" className={labelClass}>
                  {requiredStar} هل لديك خبرة في المجال؟
                </label>
                <select
                  id="has_field_experience"
                  {...register("has_field_experience")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="لا">لا</option>
                  <option value="نعم">نعم</option>
                </select>
                {errors.has_field_experience && (
                  <p className={errorClass}>
                    {errors.has_field_experience.message}
                  </p>
                )}
              </div>

              {/* Expected Salary */}
              <div>
                <label htmlFor="expected_salary" className={labelClass}>
                  {requiredStar} الراتب المتوقع (دينار)
                </label>
                <input
                  id="expected_salary"
                  type="number"
                  min={200}
                  max={2000}
                  step={10}
                  {...register("expected_salary")}
                  className={inputClass}
                  placeholder="مثال: 350"
                  disabled={isSubmitting}
                />
                {errors.expected_salary && (
                  <p className={errorClass}>{errors.expected_salary.message}</p>
                )}
              </div>

              {/* Preferred Shift */}
              <div>
                <label htmlFor="preferred_schedule" className={labelClass}>
                  {requiredStar} الوردية المفضلة
                </label>
                <select
                  id="preferred_schedule"
                  {...register("preferred_schedule")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="صباحي">صباحي</option>
                  <option value="مسائي">مسائي</option>
                  <option value="أي وردية">أي وردية</option>
                </select>
                {errors.preferred_schedule && (
                  <p className={errorClass}>
                    {errors.preferred_schedule.message}
                  </p>
                )}
              </div>

              {/* Can Start Immediately */}
              <div>
                <label htmlFor="can_start_immediately" className={labelClass}>
                  {requiredStar} هل تستطيع البدء فوراً؟
                </label>
                <select
                  id="can_start_immediately"
                  {...register("can_start_immediately")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="نعم">نعم</option>
                  <option value="لا">لا</option>
                </select>
                {errors.can_start_immediately && (
                  <p className={errorClass}>
                    {errors.can_start_immediately.message}
                  </p>
                )}
              </div>
            </div>
          </fieldset>

          {/* ═══════════════════════════════════════════ */}
          {/* Section 3: Additional Info */}
          {/* ═══════════════════════════════════════════ */}
          <fieldset className="rounded-2xl bg-white/80 backdrop-blur-sm p-5 sm:p-7 shadow-lg ring-1 ring-amber-100/80">
            <legend className="flex items-center gap-2 text-lg font-bold text-amber-800 px-2">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-amber-100 text-amber-700 text-sm font-bold">
                ٣
              </span>
              معلومات إضافية
            </legend>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Age Group */}
              <div>
                <label htmlFor="age_range" className={labelClass}>
                  {requiredStar} الفئة العمرية
                </label>
                <select
                  id="age_range"
                  {...register("age_range")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="18-21">18 - 21</option>
                  <option value="22-25">22 - 25</option>
                  <option value="26 فأكثر">26 فأكثر</option>
                </select>
                {errors.age_range && (
                  <p className={errorClass}>{errors.age_range.message}</p>
                )}
              </div>

              {/* Academic Path */}
              <div>
                <label htmlFor="academic_status" className={labelClass}>
                  {requiredStar} المسار الأكاديمي
                </label>
                <select
                  id="academic_status"
                  {...register("academic_status")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="لا يوجد نية لاستكمال الدراسة">لا يوجد نية لاستكمال الدراسة</option>
                  <option value="أكمل مسيرتي الدراسية">أكمل مسيرتي الدراسية</option>
                  <option value="انتهيت من المسيرة الدراسية (متخرج)">انتهيت من المسيرة الدراسية (متخرج)</option>
                </select>
                {errors.academic_status && (
                  <p className={errorClass}>{errors.academic_status.message}</p>
                )}
              </div>

              {/* Academic Qualification */}
              <div>
                <label htmlFor="academic_qualification" className={labelClass}>
                  {requiredStar} المؤهل الأكاديمي
                </label>
                <select
                  id="academic_qualification"
                  {...register("academic_qualification")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="مؤهل للجامعة (توجيهي ناجح)">مؤهل للجامعة (توجيهي ناجح)</option>
                  <option value="توجيهي راسب">توجيهي راسب</option>
                  <option value="جامعي">جامعي</option>
                  <option value="متخرج">متخرج</option>
                </select>
                {errors.academic_qualification && (
                  <p className={errorClass}>{errors.academic_qualification.message}</p>
                )}
              </div>

              {/* Proximity to Branch */}
              <div>
                <label htmlFor="proximity_to_branch" className={labelClass}>
                  {requiredStar} قرب السكن من الفرع
                </label>
                <select
                  id="proximity_to_branch"
                  {...register("proximity_to_branch")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="قريب وأحضر مشياً على الاقدام">قريب وأحضر مشياً على الأقدام</option>
                  <option value="قريب بنفس المنطقة واحضر مواصلات">قريب بنفس المنطقة وأحضر مواصلات</option>
                  <option value="خارج المنطقة وأحضر مواصلات أو تكسي">خارج المنطقة وأحضر مواصلات أو تكسي</option>
                  <option value="خارج المحافظة">خارج المحافظة</option>
                </select>
                {errors.proximity_to_branch && (
                  <p className={errorClass}>
                    {errors.proximity_to_branch.message}
                  </p>
                )}
              </div>

              {/* Relatives at Company */}
              <div>
                <label
                  htmlFor="has_relatives_at_company"
                  className={labelClass}
                >
                  {requiredStar} هل لديك أقارب في الشركة؟
                </label>
                <select
                  id="has_relatives_at_company"
                  {...register("has_relatives_at_company")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="نعم">نعم</option>
                  <option value="لا">لا</option>
                </select>
                {errors.has_relatives_at_company && (
                  <p className={errorClass}>
                    {errors.has_relatives_at_company.message}
                  </p>
                )}
              </div>

              {/* Previously at Qabalan */}
              <div>
                <label htmlFor="previously_at_qabalan" className={labelClass}>
                  {requiredStar} هل عملت سابقاً في قبلان؟
                </label>
                <select
                  id="previously_at_qabalan"
                  {...register("previously_at_qabalan")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="لا">لا</option>
                  <option value="نعم">نعم</option>
                </select>
                {errors.previously_at_qabalan && (
                  <p className={errorClass}>
                    {errors.previously_at_qabalan.message}
                  </p>
                )}
              </div>

              {/* Social Security Issues */}
              <div>
                <label htmlFor="social_security_issues" className={labelClass}>
                  {requiredStar} هل عليك مشاكل ضمان اجتماعي؟
                </label>
                <select
                  id="social_security_issues"
                  {...register("social_security_issues")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="لا">لا</option>
                  <option value="نعم">نعم</option>
                </select>
                {errors.social_security_issues && (
                  <p className={errorClass}>
                    {errors.social_security_issues.message}
                  </p>
                )}
              </div>
            </div>
          </fieldset>

          {/* ═══════════════════════════════════════════ */}
          {/* Section 4: Personal Commitments */}
          {/* ═══════════════════════════════════════════ */}
          <fieldset className="rounded-2xl bg-white/80 backdrop-blur-sm p-5 sm:p-7 shadow-lg ring-1 ring-amber-100/80">
            <legend className="flex items-center gap-2 text-lg font-bold text-amber-800 px-2">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-amber-100 text-amber-700 text-sm font-bold">
                ٤
              </span>
              الالتزام الشخصي
            </legend>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              {/* Prayer */}
              <div>
                <label htmlFor="prayer_regularity" className={labelClass}>
                  {requiredStar} الالتزام بالصلاة
                </label>
                <select
                  id="prayer_regularity"
                  {...register("prayer_regularity")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="نعم الحمد لله">نعم الحمد لله</option>
                  <option value="ليس بشكل منتظم">ليس بشكل منتظم</option>
                </select>
                {errors.prayer_regularity && (
                  <p className={errorClass}>
                    {errors.prayer_regularity.message}
                  </p>
                )}
              </div>

              {/* Smoking */}
              <div>
                <label htmlFor="is_smoker" className={labelClass}>
                  {requiredStar} هل أنت مدخن؟
                </label>
                <select
                  id="is_smoker"
                  {...register("is_smoker")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="لا">لا</option>
                  <option value="نعم">نعم</option>
                </select>
                {errors.is_smoker && (
                  <p className={errorClass}>{errors.is_smoker.message}</p>
                )}
              </div>

              {/* Grooming */}
              <div>
                <label htmlFor="grooming_objection" className={labelClass}>
                  {requiredStar} مانع من حلق اللحية/تقصير الشعر؟
                </label>
                <select
                  id="grooming_objection"
                  {...register("grooming_objection")}
                  className={selectClass}
                  disabled={isSubmitting}
                >
                  <option value="">— اختر —</option>
                  <option value="لا">لا</option>
                  <option value="نعم">نعم</option>
                </select>
                {errors.grooming_objection && (
                  <p className={errorClass}>
                    {errors.grooming_objection.message}
                  </p>
                )}
              </div>
            </div>
          </fieldset>

          {/* ═══════════════════════════════════════════ */}
          {/* Submit */}
          {/* ═══════════════════════════════════════════ */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-xl bg-gradient-to-l from-amber-600 to-orange-600 px-6 py-4 text-lg font-bold text-white shadow-lg shadow-amber-600/25 transition-all hover:shadow-xl hover:shadow-amber-600/30 hover:-translate-y-0.5 focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
          >
            {isSubmitting ? (
              <span className="inline-flex items-center gap-2">
                <svg
                  className="w-5 h-5 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                جارٍ التسجيل...
              </span>
            ) : (
              "تقديم الطلب والبدء بالمقابلة"
            )}
          </button>
        </form>

        {/* Footer Note */}
        <p className="mt-6 text-center text-sm text-amber-700/60">
          بعد التسجيل سيتم تحويلك مباشرة لمقابلة صوتية قصيرة مع سارة
        </p>
      </div>
    </main>
  );
}
