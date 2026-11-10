<div align="center">
  <img src="./author/logo.svg" width="320" alt="TikTok APIs logo">
  <p>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+"></a>
    <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-18%2B-339933" alt="Node.js 18+"></a>
  </p>

  # 🎵 TikTok APIs

  **Python implementation of TikTok Web data access, interactions, Creator publishing, and real-time messaging APIs.**
</div>

> For learning and technical research only. Use your own account and browser session, follow platform rules, and never submit Cookies, private keys, or network captures.

## 🌟 Features

| Area | Available entry points |
| --- | --- |
| Content and users | Video details, profiles and post lists, recommendations, search, following/followers, favorites, and notifications |
| Comments and interactions | Comment and reply retrieval, pagination, posting comments/replies, likes, favorites, and follows |
| Creator Studio | `creator_publish` for videos; `creator_publish_photos` for photo posts, private by default |
| Live | Feeds, room/user/gift lists, protobuf fetches, and WebSocket chat/like/gift events |
| Direct messages | HTTP conversation/message retrieval, text sending, and WebSocket text push events |
| TikTok Shop | Product details and review retrieval; no e-commerce write operations |

The project is layered into `api / builder / signing / utils`. Standard Web and Creator HTTP signatures are calculated in Python from the current request; live and direct-message WebSocket `frontierSign`, plus Shop BSID, use local Node.js runners shipped with the repository. Captured signatures are never used as runtime constants. Requests are rejected when required fields, signature sets, or lengths do not match. Cookies, storage, user-agent, header order, and bodies required by each page or endpoint must come from the **same real browser session**.

## 🚀 Quick start

Python 3.11+ is required. Live/direct-message WebSockets and local Shop BSID signing additionally require Node.js 18+. Install from the project root:

```bash
python -m pip install -r requirements.txt
```

This project is a library. The root `demo.py` provides a private publishing example and performs only local preflight checks by default. The only implemented authentication entry point is `TiktokAuth.from_cookie`; password, QR-code, and SMS login are placeholders that explicitly raise `NotImplementedError`.

```python
import os

from builder.auth import TiktokAuth
from api.tiktok_web import TiktokWebAPI

# Provide this through your own application process; do not hard-code or commit Cookies.
auth = TiktokAuth.from_cookie(
    os.environ["TIKTOK_COOKIE"],
    local_storage={"g_exp": "g_exp from the current browser"},
    session_storage={"msToken": "msToken from the current browser"},
    # Some signed endpoints also require the current page's device_id,
    # browser_metrics, and security-sdk storage. Missing values fail
    # explicitly; the client does not fabricate defaults.
)
api = TiktokWebAPI(auth)

# Video details come from hydration data on the standalone video page,
# not from a guessed JSON API.
detail = api.get_video_detail("https://www.tiktok.com/@some_user/video/1234567890")
print(detail)
```

Browser Cookies are often insufficient to reproduce signed requests. Also provide the same-session `device_id`, `local_storage`, `session_storage`, `document_cookie`, `browser_metrics`, and CSRF/ticket-guard material required for write operations. The API never pads, truncates, or reuses old signatures to satisfy browser lengths. Use the fields from your current browser request.

Common calls after login state and page evidence are ready:

```python
posts = api.get_user_posted("user secUid")
comments = api.get_all_comments("video ID")
replies = api.get_all_comment_replies(
    "video ID", "top-level comment ID",
    referer="current video page URL",
    root_referer="current tab root navigation URL",
)

# Private by default; requires the complete current Creator Studio browser state.
result = api.creator_publish("video.mp4", "video caption")
photos = api.creator_publish_photos(["1.jpg", "2.jpg"], "photo caption")
```

Use `iter_live_ws_events(live_id, room_id, ...)` for live events and `iter_im_ws_messages(...)` for direct messages. Both are iterators; callers manage stop events and reconnects. Direct-message push connections and protocol parsing work, but cross-account end-to-end validation is still pending test messages from another account.

## 🎬 Publishing demo

Save the **same** logged-in Chrome Creator Studio session profile as `.tiktok-runtime.json` in the project root; Git and Docker ignore it. This is a flat JSON object containing `cookie` (the complete request Cookie; `TIKTOK_COOKIE` can override it), `document_cookie`, `device_id`, `odin_id`, `user_agent`, complete `local_storage` / `session_storage` / `browser_metrics` objects, and the current security-sdk values `ticket_guard_private_key`, `ticket_guard_encrypt_ticket`, `ticket_guard_ts_sign`, `ticket_guard_public_key`, `ticket_guard_web_version`, `ticket_guard_version`, and `ticket_guard_iteration_version`. Preflight recalculates ticket-guard headers and never replays captured signatures. Do not commit this profile.

Run local file, login-state, and ticket-guard checks without sending network requests:

```bash
python demo.py video ./video.mp4 --text "My video"
```

After confirming the profile, add `--publish` explicitly to upload and publish. Visibility defaults to **private**:

```bash
python demo.py --publish video ./video.mp4 --text "My video"
python demo.py --publish photos ./1.jpg ./2.jpg --text "My photo post" --title "Title"
```

Use `--profile path` to select another local profile. Preflight only verifies the profile structure and local signing material; it does not verify server-side login. The API still checks all request fields and signature lengths during publishing. A mid-publish failure may have uploaded some media; the demo does not retry automatically.

## 🔌 n8n FastAPI Bridge

`bridge.py` exposes a small local HTTP service for n8n:

```powershell
python -m pip install -r requirements.txt
$env:TIKTOK_PROFILE = ".tiktok-runtime.json"
$env:BRIDGE_API_KEY = "replace-with-a-local-secret"
python bridge.py
```

Check readiness with `GET http://127.0.0.1:8000/health`. Send a text DM with
`POST /send-dm` and the `X-Bridge-Key` header when `BRIDGE_API_KEY` is set:

```json
{
  "conversation_id": "conversation-id-from-browser",
  "conversation_short_id": 123456,
  "text": "Message from n8n"
}
```

Incoming-message forwarding is disabled by default because it opens a
long-lived synchronous WebSocket iterator. Enable it explicitly with
`BRIDGE_LISTEN_INCOMING=1` and provide `N8N_WEBHOOK_URL`. The bridge never
extracts browser state and never logs Cookies, private keys, signed URLs, or
request bodies. Keep the service bound to localhost or protect it with a
firewall/reverse-proxy rule before exposing it to n8n.

## 📦 Runtime directories

```text
api/                         TikTok Web API, compatibility entry points, login placeholders
builder/                     Cookies, browser state, headers, queries, and signing dispatch
signing/                     Python signing, protobuf, and local WebMssdk runner
reverse/tiktok_shop_bsid/env/ Shop BSID local SDK runner and required bundle
static/                      Generated IM protobuf code used by message transport
utils/                       HTTP and compatibility utilities
demo.py                      Private video/photo publishing example (no request by default)
bridge.py                    FastAPI/n8n direct-message bridge
author/logo.svg              Project logo
```

`Dockerfile` includes the runtime directories above. Use `docker build -t tiktok-apis .` to validate the environment; the image only performs import checks by default and does not log in or call APIs.

## ⚠️ Scope and limitations

- Shop support is read-only; gift sending/charging, co-hosting, PK, live sharing, and e-commerce writes are out of scope.
- Direct messages currently support text only; images, audio, and other types are not supported.
- Login only creates sessions from an existing Cookie; expired Cookies or browser parameter changes require fresh evidence from the same session.
- Signature, header, and body alignment is based on captured page/endpoint evidence. Re-check real browser requests after TikTok changes; old samples are not a stable long-term protocol.

## 📈 Star history

<a href="https://cvcat.site/star-history/svg?repos=cv-cat/TiktokApis&type=Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cvcat.site/star-history/svg?repos=cv-cat/TiktokApis&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://cvcat.site/star-history/svg?repos=cv-cat/TiktokApis&type=Date" />
    <img alt="TikTok APIs Star History Chart" src="https://cvcat.site/star-history/svg?repos=cv-cat/TiktokApis&type=Date" />
  </picture>
</a>

## 🍔 Community

If you are interested in web scraping and AI agents, join the discussion groups.

PS: If a group is full or a QR code has expired, notify the author through an issue, WeChat, or QQ.

| group-1 | group-2 | group-3 | group-4 (2,000-member QQ group) |
|:--:|:--:|:--:|:--:|
| <img width="280" alt="group-1 QR code" src="https://cvcat.site/assets/group1.jpg" /> | <img width="280" alt="group-2 QR code" src="https://cvcat.site/assets/group2.jpg" /> | <img width="280" alt="group-3 QR code" src="https://cvcat.site/assets/group3.jpg" /> | <img width="280" alt="group-4 QQ QR code" src="https://cvcat.site/assets/group4.jpg" /> |

Please open an issue or PR for reproducible request differences. Remove all personal session information before submitting.
