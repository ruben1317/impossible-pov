"use client";
import {useEffect,useState} from "react";
import {useParams} from "next/navigation";
import {api} from "@/lib/api";

const steps=["idea","research","script","storyboard","video_scenes","voice","render","final","publish","published"];
function fmtSeconds(value:number){const n=Math.max(0,Number(value)||0);const m=Math.floor(n/60);const sec=Math.floor(n%60);return `${m}:${String(sec).padStart(2,"0")}`;}
export default function ProjectPage(){const params=useParams<{id:string}>();const id=params.id;const [p,setP]=useState<any>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 async function refresh(){setP(await api(`/api/projects/${id}`))} useEffect(()=>{refresh().catch(e=>setError(String(e)))},[id]);
 async function act(path:string,body?:any){setBusy(true);setError("");try{setP(await api(`/api/projects/${id}/${path}`,{method:"POST",body:body?JSON.stringify(body):undefined}))}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 if(!p)return <p>{error||"Loading…"}</p>;
 const current=steps.indexOf(p.stage); const board=p.storyboard||[];
 return <><section className="hero"><div className="row"><span className="badge">{p.category}</span><span className="badge amber">{p.status.replaceAll("_"," ")}</span></div><h1 style={{fontSize:"clamp(30px,4vw,48px)"}}>{p.title}</h1><p>{p.premise}</p></section>
 <div className="stepbar">{steps.map((s,i)=><div key={s} className={`step ${i<current?"done":i===current?"active":""}`}>{i<current?"✓ ":""}{s.replaceAll("_"," ")}</div>)}</div>
 {error&&<p className="notice">{error}</p>}
 <div className="grid grid-2" style={{marginTop:16}}><div className="card"><h2>Current approval</h2><Workflow p={p} busy={busy} act={act}/></div><div className="card"><h2>Project controls</h2><p className="muted">Every expensive step stays behind an explicit approval. Provider behavior, cost targets, scene count, prompts and publishing defaults live in config—not this UI.</p><div className="row"><span className="badge green">YouTube + TikTok</span><span className="badge">No auto publish</span></div></div></div>
 {p.script?.segments?.length>0&&<div className="card" style={{marginTop:16}}><h2>Script</h2>{p.script.segments.map((s:any,i:number)=><div className="project" key={i}><div><strong>{fmtSeconds(s.start)}–{fmtSeconds(s.end)} · {s.narration}</strong><div className="muted">{s.visual}</div></div></div>)}</div>}
 {board.length>0&&<div className="card" style={{marginTop:16}}><div className="row space"><h2>Storyboard</h2><span className="muted">{board.filter((x:any)=>x.approved).length}/{board.length} approved</span></div>{board.map((s:any)=><div className="scene" key={s.index}><div className="preview">Scene {s.index+1}</div><div><strong>{s.narration}</strong><p className="muted">{s.prompt}</p><div className="row"><button className="btn primary" disabled={busy||s.approved} onClick={()=>act("scene-decision",{scene_index:s.index,approved:true,notes:""})}>{s.approved?"✓ Approved":"Approve"}</button><button className="btn" disabled={busy} onClick={()=>act("scene-decision",{scene_index:s.index,approved:false,notes:"Needs regeneration"})}>Reject</button></div></div></div>)}</div>}
 {p.scenes?.length>0&&<div className="card" style={{marginTop:16}}><div className="row space"><h2>Generated Scenes</h2><span className="badge green">Economy hybrid</span></div>{p.scenes.map((s:any)=><div className="project" key={s.index}><div><strong>Scene {s.index+1} · {s.production_type==="video"?"AI motion":"animated still"}</strong><div className="muted">{s.video?.provider} · {s.video?.status} · ${Number(s.video?.cost||0).toFixed(2)}{s.video_regenerations?` · ${s.video_regenerations} regen`:""}</div><div className="row" style={{marginTop:8}}><button className="btn primary" disabled={busy||s.video_approved} onClick={()=>act("approve-video-scene",{scene_index:s.index})}>{s.video_approved?"✓ Approved":"Approve"}</button><button className="btn" disabled={busy} onClick={()=>act("regenerate-video-scene",{scene_index:s.index})}>↻ Regenerate</button></div></div><span className={`badge ${s.video_approved?"green":"amber"}`}>{s.video_approved?"approved":"needs review"}</span></div>)}</div>}
 </>}

function Workflow({p,busy,act}:{p:any,busy:boolean,act:(path:string,body?:any)=>void}){
 if(p.stage==="idea")return <div className="stack"><p>Approve this concept before research or writing begins.</p><button className="btn primary" disabled={busy} onClick={()=>act("approve-idea")}>Approve Idea</button></div>;
 if(p.stage==="research"&&p.status==="ready_to_generate")return <button className="btn primary" disabled={busy} onClick={()=>act("generate-script")}>Research + Generate Script</button>;
 if(p.stage==="script")return <ScriptReview p={p} busy={busy} act={act}/>;
 if(p.stage==="storyboard"&&p.status==="ready_to_generate")return <button className="btn primary" disabled={busy} onClick={()=>act("generate-storyboard")}>Generate Storyboard</button>;
 if(p.stage==="storyboard")return <p>Approve each storyboard scene below. All scenes must be approved before video generation.</p>;
 if(p.stage==="video_scenes"&&p.status==="ready_to_generate")return <div className="stack"><div className="notice">Economy mode: 3 Runway motion clips + 3 animated stills. Target scene-generation cost is about $0.87 before narration.</div><button className="btn primary" disabled={busy} onClick={()=>act("generate-video-scenes")}>Generate Video Scenes</button></div>;
 if(p.stage==="video_scenes")return <button className="btn primary" onClick={()=>act("approve-video-scenes")} disabled={busy||!(p.scenes||[]).every((s:any)=>s.video_approved)}>Continue After Scene Approvals</button>;
 if(p.stage==="voice"&&p.status==="ready_to_generate")return <button className="btn primary" disabled={busy} onClick={()=>act("generate-voice")}>Generate Narration</button>;
 if(p.stage==="voice")return <button className="btn primary" disabled={busy} onClick={()=>act("approve-voice")}>Approve Narration</button>;
 if(p.stage==="render"&&p.status==="ready_to_generate")return <button className="btn primary" disabled={busy} onClick={()=>act("render")}>Render Final Short</button>;
 if(p.stage==="final")return <button className="btn primary" disabled={busy} onClick={()=>act("approve-final")}>Approve Final Video</button>;
 if(p.stage==="publish")return (
  <div className="stack">
    <p>
      Choose where to publish the approved final video.
      The same vertical master is used for both platforms.
    </p>

    <div className="row">
      <span className={`badge ${p.publish?.platforms?.youtube ? "green" : ""}`}>
        YouTube {p.publish?.platforms?.youtube ? "✓" : ""}
      </span>

      <span className={`badge ${p.publish?.platforms?.tiktok ? "green" : ""}`}>
        TikTok {p.publish?.platforms?.tiktok ? "✓" : ""}
      </span>
    </div>

    {!p.publish?.platforms?.youtube && (
      <button
        className="btn"
        disabled={busy}
        onClick={() =>
          act("publish", {
            platforms: ["youtube"],
          })
        }
      >
        Publish to YouTube
      </button>
    )}

    {!p.publish?.platforms?.tiktok && (
      <button
        className="btn"
        disabled={busy}
        onClick={() =>
          act("publish", {
            platforms: ["tiktok"],
          })
        }
      >
        Publish to TikTok
      </button>
    )}

    {!p.publish?.platforms?.youtube &&
      !p.publish?.platforms?.tiktok && (
        <button
          className="btn primary"
          disabled={busy}
          onClick={() =>
            act("publish", {
              platforms: ["youtube", "tiktok"],
            })
          }
        >
          Publish to Both
        </button>
      )}

    <p className="muted">
      Publishing remains manual. Nothing is posted until you choose a platform above.
    </p>
  </div>
);
 if(p.stage==="published")return (
  <div className="stack">
    <span className="badge green">Published to both platforms</span>

    <div className="row">
      <span className="badge green">YouTube ✓</span>
      <span className="badge green">TikTok ✓</span>
    </div>
  </div>
);
 return <p className="muted">Waiting for the next action.</p>
}

function ScriptReview({
  p,
  busy,
  act,
}: {
  p: any;
  busy: boolean;
  act: (path: string, body?: any) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [instructions, setInstructions] = useState("");

  function applyChanges() {
    const text = instructions.trim();
    if (!text) return;

    act("revise-script", {
      instructions: text,
    });

    setEditing(false);
    setInstructions("");
  }

  return (
    <div className="stack">
      <p>
        Review the full script below. No video generation has happened yet.
      </p>

      {!editing && (
        <>
          <button
            className="btn primary"
            disabled={busy}
            onClick={() => act("approve-script")}
          >
            Approve Script
          </button>

          <button
            className="btn"
            disabled={busy}
            onClick={() => setEditing(true)}
          >
            Edit Script
          </button>

          <button
            className="btn"
            disabled={busy}
            onClick={() => act("regenerate-script")}
          >
            ↻ Regenerate Script
          </button>
        </>
      )}

      {editing && (
        <div className="stack">
          <label>
            <strong>What would you like changed?</strong>
          </label>

          <p className="muted">
            Paste revision instructions here. AI will rewrite the script using
            your requested changes before you approve it.
          </p>

          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="Example: Change Scene 3 so there is no readable text on the time machine. Replace IMPACT DETECTED with flashing red warning lights, while keeping the rest of the script the same."
            rows={9}
            style={{
              width: "100%",
              resize: "vertical",
              padding: 12,
              borderRadius: 10,
              font: "inherit",
            }}
          />

          <button
            className="btn primary"
            disabled={busy || !instructions.trim()}
            onClick={applyChanges}
          >
            {busy ? "Applying Changes..." : "Apply Changes"}
          </button>

          <button
            className="btn"
            disabled={busy}
            onClick={() => {
              setEditing(false);
              setInstructions("");
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}