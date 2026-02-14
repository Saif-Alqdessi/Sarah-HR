"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSupabaseClient } from "@/lib/supabase/client";
import { toast } from "sonner";

const TARGET_ROLES = [
  { value: "baker", label: "Baker" },
  { value: "cashier", label: "Cashier" },
  { value: "delivery_driver", label: "Driver" },
] as const;

const PHONE_REGEX = /^[\d\s\-+()]{10,20}$/;

export default function ApplyPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formData, setFormData] = useState({
    fullName: "",
    phoneNumber: "",
    email: "",
    targetRole: "",
  });

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.fullName.trim()) {
      newErrors.fullName = "Full name is required";
    }

    if (!formData.phoneNumber.trim()) {
      newErrors.phoneNumber = "Phone number is required";
    } else if (!PHONE_REGEX.test(formData.phoneNumber.replace(/\s/g, ""))) {
      newErrors.phoneNumber =
        "Please enter a valid phone number (10-20 digits)";
    }

    if (!formData.targetRole) {
      newErrors.targetRole = "Please select a target role";
    }

    if (
      formData.email &&
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)
    ) {
      newErrors.email = "Please enter a valid email address";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate() || isSubmitting) return;

    setIsSubmitting(true);
    setErrors({});

    try {
      const supabase = createSupabaseClient();

      const { data, error } = await supabase
        .from("candidates")
        .insert({
          full_name: formData.fullName.trim(),
          phone_number: formData.phoneNumber.trim().replace(/\s/g, ""),
          email: formData.email.trim() || null,
          target_role: formData.targetRole,
          application_source: "web_form",
        })
        .select("id")
        .single();

      if (error) {
        if (error.code === "23505") {
          toast.error("This phone number has already been used for an application.");
          setErrors({ phoneNumber: "Phone number already registered" });
          return;
        }
        throw error;
      }

      if (!data?.id) {
        throw new Error("No candidate ID returned");
      }

      toast.success("Application submitted successfully!");
      router.push(`/interview/${data.id}`);
    } catch (err) {
      console.error("Submit error:", err);
      toast.error(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-amber-50 to-white">
      <div className="mx-auto max-w-md px-6 py-12 sm:py-16">
        <div className="rounded-2xl bg-white p-6 shadow-lg ring-1 ring-amber-100 sm:p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-amber-900 sm:text-3xl">
              Join Our Team
            </h1>
            <p className="mt-2 text-amber-700/80">
              Golden Crust Bakery • Apply for a position
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Full Name */}
            <div>
              <label
                htmlFor="fullName"
                className="block text-sm font-medium text-amber-900"
              >
                Full Name <span className="text-amber-600">*</span>
              </label>
              <input
                id="fullName"
                type="text"
                value={formData.fullName}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, fullName: e.target.value }))
                }
                className="mt-1.5 block w-full rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3 text-amber-900 placeholder-amber-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 focus:outline-none sm:text-sm"
                placeholder="Ahmed Hassan"
                autoComplete="name"
                disabled={isSubmitting}
              />
              {errors.fullName && (
                <p className="mt-1.5 text-sm text-red-600">{errors.fullName}</p>
              )}
            </div>

            {/* Phone Number */}
            <div>
              <label
                htmlFor="phoneNumber"
                className="block text-sm font-medium text-amber-900"
              >
                Phone Number <span className="text-amber-600">*</span>
              </label>
              <input
                id="phoneNumber"
                type="tel"
                value={formData.phoneNumber}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, phoneNumber: e.target.value }))
                }
                className="mt-1.5 block w-full rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3 text-amber-900 placeholder-amber-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 focus:outline-none sm:text-sm"
                placeholder="+962 7X XXX XXXX"
                autoComplete="tel"
                disabled={isSubmitting}
              />
              {errors.phoneNumber && (
                <p className="mt-1.5 text-sm text-red-600">
                  {errors.phoneNumber}
                </p>
              )}
            </div>

            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-amber-900"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, email: e.target.value }))
                }
                className="mt-1.5 block w-full rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3 text-amber-900 placeholder-amber-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 focus:outline-none sm:text-sm"
                placeholder="ahmed@example.com"
                autoComplete="email"
                disabled={isSubmitting}
              />
              {errors.email && (
                <p className="mt-1.5 text-sm text-red-600">{errors.email}</p>
              )}
            </div>

            {/* Target Role */}
            <div>
              <label
                htmlFor="targetRole"
                className="block text-sm font-medium text-amber-900"
              >
                Target Role <span className="text-amber-600">*</span>
              </label>
              <select
                id="targetRole"
                value={formData.targetRole}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, targetRole: e.target.value }))
                }
                className="mt-1.5 block w-full rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3 text-amber-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 focus:outline-none sm:text-sm"
                disabled={isSubmitting}
              >
                <option value="">Select a role</option>
                {TARGET_ROLES.map((role) => (
                  <option key={role.value} value={role.value}>
                    {role.label}
                  </option>
                ))}
              </select>
              {errors.targetRole && (
                <p className="mt-1.5 text-sm text-red-600">
                  {errors.targetRole}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-lg bg-amber-600 px-4 py-3 font-semibold text-white shadow-md transition hover:bg-amber-700 focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? "Submitting..." : "Submit Application"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-amber-700/70">
          You will be redirected to a short voice interview after submitting.
        </p>
      </div>
    </main>
  );
}
