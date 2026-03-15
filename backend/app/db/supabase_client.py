"""Supabase client for backend database operations."""

import httpx
from typing import Optional
from supabase import create_client, Client

from app.config import settings

# Extended timeout to handle slow/cold Supabase connections (WinError 10060 fix)
_TIMEOUT = httpx.Timeout(
    connect=20.0,   # Time to establish TCP connection
    read=30.0,      # Time to wait for response body
    write=20.0,     # Time to send request body
    pool=20.0,      # Time waiting for a connection from the pool
)

# Module-level singleton so we don't recreate on every call
_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get (or create) a Supabase client with extended timeouts.

    Prefers SUPABASE_SERVICE_ROLE_KEY (bypasses RLS) for backend ops.
    The client is cached as a module singleton for connection reuse.
    """
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

    # Create client first
    client = create_client(settings.supabase_url, key)

    # Patch the underlying httpx timeout on the PostgREST session.
    # supabase-py uses postgrest-py which has an internal _session (httpx.Client).
    # We override its timeout to avoid WinError 10060 on slow networks.
    try:
        # postgrest-py >= 0.10: client.postgrest.session is an httpx.Client
        if hasattr(client, "postgrest") and hasattr(client.postgrest, "session"):
            client.postgrest.session.timeout = _TIMEOUT
        # Some versions use _session
        elif hasattr(client, "postgrest") and hasattr(client.postgrest, "_session"):
            client.postgrest._session.timeout = _TIMEOUT
    except Exception:
        pass  # Non-fatal: worst case we just use the default timeout

    _client = client
    return _client
