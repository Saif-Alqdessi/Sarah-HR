import { createClient, SupabaseClient } from "@supabase/supabase-js";

/**
 * Singleton Supabase client to prevent "Multiple GoTrueClient instances" error
 */
let supabaseInstance: SupabaseClient | null = null;

/**
 * Creates a Supabase client strictly using environment variables.
 * Uses singleton pattern to prevent multiple client instances.
 * No fallbacks or hardcoded URLs - fixes ERR_NAME_NOT_RESOLVED for placeholder domains.
 * Restart dev server or rebuild after changing .env.local.
 */
export function createSupabaseClient(): SupabaseClient {
  // Return existing instance if already created
  if (supabaseInstance) {
    return supabaseInstance;
  }
  
  // Get environment variables
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

  // Create new instance and store it
  supabaseInstance = createClient(supabaseUrl, supabaseAnonKey);
  return supabaseInstance;
}
