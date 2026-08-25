import Link from "next/link";
export default function Setup(){return <>
<section className="hero"><div className="badge">One-time setup</div><h1 className="mobileHeadline">Get the studio <em>online</em></h1><p>You can operate the finished studio entirely from your phone. These are the one-time cloud setup steps.</p></section>
<div className="stack">
 <section className="card actionCard"><span className="badge">1</span><h2>GitHub</h2><p>Upload this repo to a private GitHub repository named <strong>impossible-pov</strong>. Never commit your real <code>.env</code> file.</p></section>
 <section className="card actionCard"><span className="badge">2</span><h2>Backend on Railway</h2><p>Deploy the <code>backend</code> service. Add a persistent volume and set <code>DATABASE_URL</code>, <code>CORS_ORIGINS</code>, and provider API keys as Railway environment variables.</p><p className="muted">Start with all providers in Mock mode. You can switch providers from the Studio Settings screen later.</p></section>
 <section className="card actionCard"><span className="badge">3</span><h2>Frontend on Vercel</h2><p>Deploy the <code>frontend</code> directory and set <code>NEXT_PUBLIC_API_BASE_URL</code> to the public Railway backend URL.</p></section>
 <section className="card actionCard"><span className="badge">4</span><h2>Add to iPhone Home Screen</h2><p>Open the deployed Vercel URL in Safari, tap Share, then <strong>Add to Home Screen</strong>. The app includes a mobile manifest and IMPOSSIBLE POV icon.</p></section>
 <section className="card actionCard"><span className="badge">5</span><h2>Connect providers one by one</h2><p>Open <strong>Settings</strong>. Turn on OpenAI first, test ideas/scripts, then Runway, ElevenLabs, FFmpeg, and YouTube. Keep YouTube visibility Private until the complete pipeline passes.</p></section>
</div><div className="savebar"><Link className="btn primary tap" style={{display:"grid",placeItems:"center"}} href="/settings">Open Studio Settings</Link></div>
</>}
