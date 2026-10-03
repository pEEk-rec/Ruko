# Share-target spike (throwaway)

**Question this spike answers:** can a message in Telegram or WhatsApp be shared to Ruko on an
Android phone in one tap? Everything in Ruko assumes yes. This is not the frontend; it will be
deleted once the answer is known.

Files: `manifest.json` (declares a `share_target` with `title`, `text`, `url`), `sw.js` (an empty
service worker, required for installation), `index.html` (shows what was shared and can send it
to the backend), two plain placeholder icons.

## Test on a real Android phone (about 15 minutes)

You need: an Android phone with Chrome, Telegram and/or WhatsApp, and a way to serve these files
over **HTTPS** (Android only installs web apps from HTTPS origins).

1. Serve this folder locally:
   `cd spike/share_target` then `python -m http.server 8080`
2. Expose it over HTTPS with any tunnel you trust (for example `cloudflared tunnel --url
   http://localhost:8080`, or `ngrok http 8080`). Note the `https://...` URL.
3. (Optional, to try step 9) start the backend and expose it too:
   `RUKO_CORS_ALLOW_ORIGINS=https://<spike-tunnel-host> .venv/Scripts/python -m uvicorn
   ruko.main:app --port 8000`, then tunnel port 8000.
4. On the phone, open the spike's HTTPS URL in **Chrome**.
5. Chrome menu (three dots) -> **Add to Home screen** / **Install app**. Confirm.
6. Open Telegram (or WhatsApp), long-press a message -> **Share** / **Forward** -> look for
   **Ruko test** in the Android share sheet. (On some phones: Share -> More.)
7. Tap **Ruko test**. The page should open and show the message text.
8. Paste the backend tunnel URL into "Backend URL", tap **1. Check backend /health**.
9. Tap **2. Send to /v1/analyze** and look at the JSON response.

## Results checklist (fill in)

| Check | Telegram | WhatsApp |
|---|---|---|
| Phone model / Android version | | |
| "Ruko test" appears in the share sheet | yes / no | yes / no |
| Number of taps from message to Ruko | | |
| Full message text arrives (not truncated) | yes / no | yes / no |
| Links arrive (in `text` or `url`) | yes / no | yes / no |
| Hindi / Kannada text arrives intact | yes / no | yes / no |
| Forwarded images can be shared (expected: no, text only) | | |
| `/health` reachable from the phone | yes / no | |
| `/v1/analyze` returns a response | yes / no | |
| Notes | | |

## Known limits

- GET share targets carry text only; sharing images would need a POST share target with
  `multipart/form-data` (not in this spike).
- Some apps share only a link, or put the text in `title`; the page shows all three fields.
- The page stores only the backend URL you typed (in this phone's browser), nothing else.
