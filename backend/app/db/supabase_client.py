"""Supabase client — singleton with 60s timeout."""

import httpx
from typing import Optional
from supabase import create_client, Client

from app.config import settings

_TIMEOUT = httpx.Timeout(
    connect=60.0,
    read=60.0,
    write=60.0,
    pool=60.0,
)

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get singleton Supabase client with 60s timeout."""
    global _client
    if _client is not None:
        return _client

    if not settings.supabase_url:
        raise ValueError("SUPABASE_URL must be set in .env")
    key = settings.supabase_service_role_key or settings.supabase_key
    if not key:
        raise ValueError(
            "SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY must be set in .env. "
            "Use service_role key for backend to bypass Row Level Security."
        )

    client = create_client(settings.supabase_url, key)

    # Patch timeout on the internal postgrest session
    try:
        if hasattr(client, "postgrest") and hasattr(client.postgrest, "session"):
            client.postgrest.session.timeout = _TIMEOUT
        elif hasattr(client, "postgrest") and hasattr(client.postgrest, "_session"):
            client.postgrest._session.timeout = _TIMEOUT
    except Exception:
        pass

    _client = client
    return _client
