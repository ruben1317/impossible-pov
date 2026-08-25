# IMPOSSIBLE POV Content Studio — V1.3 Economy Hybrid

A YouTube-only, semi-automatic AI video production studio designed to be operated from an iPhone after deployment.

## What V1.3 adds

- Mobile-first dashboard, review queue, creation flow, and settings.
- Fixed bottom navigation with large touch targets.
- PWA metadata/icons so the deployed studio can be added to the iPhone Home Screen.
- Runtime settings stored in the database instead of requiring YAML edits for everyday changes.
- Phone-editable budget caps, video defaults, provider routing, model IDs, voice ID, and YouTube privacy defaults.
- Provider health cards that report which live credentials are missing without exposing secret values.
- A `/setup` screen with a one-time GitHub → Railway → Vercel deployment checklist.
- YouTube only. Instagram is intentionally absent.
- Mock mode remains the default, so initial testing cannot consume video/voice credits or publish publicly.

## Architecture

- `frontend/` — Next.js mobile-first web app / PWA.
- `backend/` — FastAPI workflow API.
- `config/app.yaml` — safe baseline configuration committed to source control.
- Runtime UI overrides are stored in the SQL database and deep-merged over `config/app.yaml`.
- `.env` / hosting environment variables — secrets only.
- SQLite by default for development; use persistent storage or Postgres when deployed.

## Local run

Copy environment defaults:

```bash
cp .env.example .env
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Phone-first deployment

The intended production path is:

1. Put the repository in a **private GitHub repo**.
2. Deploy `backend/` to **Railway** with persistent database/media storage.
3. Deploy `frontend/` to **Vercel**.
4. Set `NEXT_PUBLIC_API_BASE_URL` on Vercel to the Railway backend URL.
5. Open the Vercel URL in Safari → Share → **Add to Home Screen**.
6. Use the in-app **Settings** page for normal changes.
7. Use Railway environment variables only for secrets such as API keys.

## Environment variables

See `.env.example`. Important values:

- `OPENAI_API_KEY`
- `RUNWAY_API_KEY`
- `ELEVENLABS_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `DATABASE_URL`
- `CORS_ORIGINS`
- Frontend: `NEXT_PUBLIC_API_BASE_URL`

Never commit real credentials.

## Recommended activation order

Keep all providers on `mock` first. Then enable one at a time from the phone Settings UI:

1. OpenAI — ideas, research, scripts, storyboard.
2. Runway — AI video scenes.
3. ElevenLabs — narration.
4. FFmpeg — final assembly.
5. YouTube — OAuth/upload, while default privacy remains **Private**.

## Semi-auto approval chain

`Idea → Research/Script → Storyboard → Video scenes → Voice → Render → Final → YouTube`

The goal is that expensive generation and publishing remain behind explicit user approvals.

## Important V1.3 limitation

Only the OpenAI text/research adapter is live in this version. Runway, ElevenLabs, FFmpeg, and YouTube remain provider placeholders until their adapters are wired. The mobile UI is ready for those connections, and the provider routing is configurable without changing workflow code.


## V1.3 Economy Hybrid
- Economy scene plan: scenes 1, 3, 5 use Runway Gen-4 Turbo motion; scenes 2, 4, 6 use Gen-4 Image Turbo stills.
- Hard scene-generation guardrail defaults to $1.25.
- Per-scene approve/regenerate controls prevent paying to regenerate the whole video.
- Runway live image + image-to-video adapter is wired to the API.
- Economy mode forces Gen-4 Turbo for motion even if an older runtime override still says Gen-4.5.
- Default target finished-video budget is $1.10.
