# iPhone setup checklist

This repo is designed so the *ongoing* workflow happens in IMPOSSIBLE POV Studio from Safari/Home Screen. Deployment and secrets are one-time infrastructure tasks.

## A. GitHub from iPhone

1. Create a private repository named `impossible-pov`.
2. Upload the contents of this repository.
3. Confirm `.env` is not uploaded. Only `.env.example` should be in GitHub.

## B. Railway backend

1. Create a Railway project from the GitHub repository.
2. Railway will read the root `railway.json` and build `backend/Dockerfile`.
3. Add a persistent volume mounted at `/data`.
4. Add environment variables:
   - `DATABASE_URL=sqlite:////data/impossible_pov.db`
   - `CORS_ORIGINS=<your Vercel URL>` after Vercel is created.
   - Provider keys only when you are ready to activate each provider.
5. Generate a public Railway domain and test `<domain>/api/health`.

## C. Vercel frontend

1. Import the same GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Add `NEXT_PUBLIC_API_BASE_URL=<your Railway URL>`.
4. Deploy.
5. Return to Railway and set `CORS_ORIGINS` to the Vercel URL, then redeploy the backend.

## D. Put it on your iPhone

1. Open the Vercel URL in Safari.
2. Tap **Share** → **Add to Home Screen**.
3. Open **POV Studio** from the new icon.
4. Go to **Settings** and keep all providers in `Mock` until the flow is tested.

## E. Activate providers safely

Use this order: OpenAI → Runway → ElevenLabs → FFmpeg → YouTube. API keys go in Railway's environment-variable screen; normal options (provider choice, model IDs, budget, scenes, lengths, YouTube privacy) are controlled from the Studio Settings UI.

Keep YouTube visibility **Private** until the upload integration is proven end-to-end.
