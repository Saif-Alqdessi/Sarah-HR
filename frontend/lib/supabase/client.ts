import { createClient, SupabaseClient } from "@supabase/supabase-js";

/**
 * Creates a Supabase client strictly using environment variables.
 * No fallbacks or hardcoded URLs - fixes ERR_NAME_NOT_RESOLVED for placeholder domains.
 * Restart dev server or rebuild after changing .env.local.
 */
export function createSupabaseClient(): SupabaseClient {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local"
    );
  }

  if (supabaseUrl.includes("your-project.supabase.co")) {
    throw new Error(
      "Invalid Supabase URL: Replace your-project.supabase.co with your actual Supabase project URL in .env.local"
    );
  }

  return createClient(supabaseUrl, supabaseAnonKey);
}
