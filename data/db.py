import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        _client = create_client(url, key)
    return _client


# ── Watchlist ──────────────────────────────────────────────────────────────

def wl_load(user_id: str = "default") -> list[str]:
    try:
        res = get_db().table("watchlist").select("stock_id").eq("user_id", user_id).execute()
        return [r["stock_id"] for r in res.data]
    except Exception:
        return []


def wl_add(stock_id: str, user_id: str = "default"):
    try:
        get_db().table("watchlist").upsert(
            {"user_id": user_id, "stock_id": stock_id},
            on_conflict="user_id,stock_id"
        ).execute()
    except Exception:
        pass


def wl_remove(stock_id: str, user_id: str = "default"):
    try:
        get_db().table("watchlist").delete().eq("user_id", user_id).eq("stock_id", stock_id).execute()
    except Exception:
        pass


# ── Holdings ───────────────────────────────────────────────────────────────

def holdings_load(user_id: str = "default") -> list[dict]:
    try:
        res = get_db().table("holdings").select("*").eq("user_id", user_id).order("created_at").execute()
        return res.data
    except Exception:
        return []


def holdings_add(user_id: str = "default", **kwargs) -> dict | None:
    try:
        res = get_db().table("holdings").insert({"user_id": user_id, **kwargs}).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def holdings_delete(holding_id: str):
    try:
        get_db().table("holdings").delete().eq("id", holding_id).execute()
    except Exception:
        pass
