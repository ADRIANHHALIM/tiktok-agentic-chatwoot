"""FastAPI bridge for integrating the TikTok client with n8n.

The bridge never extracts browser state.  Provide a locally-created runtime
profile through TIKTOK_PROFILE, defaulting to .tiktok-runtime.json.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from threading import Event
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from api.tiktok_web import TiktokWebAPI
from builder.auth import BrowserEvidenceError, TiktokAuth


LOGGER = logging.getLogger("tiktok-bridge")
PROFILE_PATH = Path(os.getenv("TIKTOK_PROFILE", ".tiktok-runtime.json"))
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
BRIDGE_API_KEY = os.getenv("BRIDGE_API_KEY", "").strip()
LISTEN_INCOMING = os.getenv("BRIDGE_LISTEN_INCOMING", "").lower() in {
    "1", "true", "yes", "on",
}


class SendMessageRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    conversation_short_id: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=4000)


def _load_api() -> TiktokWebAPI:
    if not PROFILE_PATH.is_file():
        raise RuntimeError(
            f"Runtime profile tidak ditemukan: {PROFILE_PATH}. "
            "Buat file lokal dari profil browser Anda sendiri."
        )
    try:
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Runtime profile tidak dapat dibaca sebagai JSON") from exc
    if not isinstance(profile, dict):
        raise RuntimeError("Runtime profile harus berupa objek JSON")
    cookie = os.getenv("TIKTOK_COOKIE") or profile.pop("cookie", "")
    if not isinstance(cookie, str) or not cookie.strip():
        raise RuntimeError("Runtime profile tidak memiliki Cookie")
    try:
        auth = TiktokAuth.from_cookie(cookie, **profile)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Runtime profile memiliki format yang tidak valid") from exc
    return TiktokWebAPI(auth)


async def _require_api_key(
    x_bridge_key: str | None = Header(default=None),
) -> None:
    if BRIDGE_API_KEY and x_bridge_key != BRIDGE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bridge API key tidak valid",
        )


def _send_message(api: TiktokWebAPI, payload: SendMessageRequest) -> dict[str, Any]:
    result = api.send_im_message(
        conversation_id=payload.conversation_id,
        conversation_short_id=payload.conversation_short_id,
        text=payload.text,
    )
    return result if isinstance(result, dict) else {"result": result}


def _listener_worker(api: TiktokWebAPI, stop_event: Event) -> None:
    if not N8N_WEBHOOK_URL:
        LOGGER.error("BRIDGE_LISTEN_INCOMING aktif tetapi N8N_WEBHOOK_URL kosong")
        return
    while not stop_event.is_set():
        try:
            with httpx.Client(timeout=20) as client:
                for message in api.iter_im_ws_messages(stop_event=stop_event):
                    if stop_event.is_set():
                        break
                    client.post(N8N_WEBHOOK_URL, json=message).raise_for_status()
        except Exception:
            if not stop_event.is_set():
                LOGGER.exception("Listener IM terputus; mencoba ulang setelah 5 detik")
                stop_event.wait(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.api = _load_api()
    except RuntimeError as exc:
        app.state.api = None
        app.state.startup_error = str(exc)
        LOGGER.warning("TikTok API belum siap: %s", exc)
    app.state.stop_event = Event()
    app.state.listener_task = None
    if LISTEN_INCOMING and app.state.api is not None:
        app.state.listener_task = asyncio.create_task(
            asyncio.to_thread(_listener_worker, app.state.api, app.state.stop_event)
        )
    yield
    app.state.stop_event.set()
    task = app.state.listener_task
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="TikTok n8n Bridge", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    api = getattr(app.state, "api", None)
    return {
        "status": "ok" if api is not None else "not_ready",
        "profile": str(PROFILE_PATH),
        "listener_enabled": LISTEN_INCOMING,
    }


@app.post("/send-dm", dependencies=[Depends(_require_api_key)])
async def send_dm(payload: SendMessageRequest) -> dict[str, Any]:
    api = getattr(app.state, "api", None)
    if api is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TikTok runtime profile belum siap",
        )
    try:
        result = await run_in_threadpool(_send_message, api, payload)
    except (BrowserEvidenceError, ValueError) as exc:
        LOGGER.warning("DM ditolak karena browser evidence tidak lengkap: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Browser evidence tidak lengkap atau tidak valid",
        ) from exc
    except Exception:
        LOGGER.exception("Pengiriman DM gagal")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Pengiriman pesan TikTok gagal",
        ) from None
    return {"status": "success", "data": result}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bridge:app",
        host=os.getenv("BRIDGE_HOST", "127.0.0.1"),
        port=int(os.getenv("BRIDGE_PORT", "8000")),
        reload=False,
    )
