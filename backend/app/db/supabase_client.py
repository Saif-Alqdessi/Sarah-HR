"""Supabase client for backend database operations."""

from supabase import create_client, Client

from app.config import settings


def get_supabase_client() -> Client:
    """Get Supabase client. Prefers SUPABASE_SERVICE_ROLE_KEY (bypasses RLS) for backend ops."""
    if not settings.supabase_url:
        raise ValueError("SUPABASE_URL must be set in .env")
    key = settings.supabase_service_role_key or settings.supabase_key
    if not key:
        raise ValueError(
            "SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY must be set in .env. "
            "Use service_role key for backend to bypass Row Level Security."
        )
    return create_client(settings.supabase_url, key)
