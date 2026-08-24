import Link from "next/link";
import {api} from "@/lib/api";
async function safeProjects(){try{return await api<any[]>("/api/projects")}catch{return []}}
async function safeConfig(){try{return await api<any>("/api/config/public")}catch{return null}}
async function safeBudget(){try{return await api<any>("/api/budget/status")}catch{return null}}
export default async function Page(){
 const [projects,cfg,budgetInfo]=await Promise.all([safeProjects(),safeConfig(),safeBudget()]);
 const needs=projects.filter(p=>p.status.includes("review")||p.status.includes("ready"));
 const budget=Number(budgetInfo?.cap ?? cfg?.budgets?.monthly_cap ?? 100),spent=Number(budgetInfo?.spent??0);
 return <>
  <section className="hero"><div className="badge">YouTube Only · Semi Auto</div><h1 className="mobileHeadline">IMPOSSIBLE <em>POV</em><br/>STUDIO</h1><p>Open this from your phone, review what AI prepared, approve the next step, and let the server do the production work.</p><div className="quickActions"><Link className="btn primary tap" href="/videos/new">＋ Create</Link><Link className="btn tap" href="/settings">⚙ Settings</Link></div></section>
  <section className="grid grid-3"><div className="card actionCard"><div className="muted">Needs your approval</div><div className="metric">{needs.length}</div></div><div className="card"><div className="muted">Videos in studio</div><div className="metric">{projects.length}</div></div><div className="card"><div className="muted">Monthly AI budget</div><div className="metric cost">${spent.toFixed(2)} <span className="muted" style={{fontSize:15}}>/ ${budget.toFixed(0)}</span></div><div className="progress"><span style={{width:`${Math.min(100,budget?spent/budget*100:0)}%`}}/></div></div></section>
  <section className="card" style={{marginTop:14}}><div className="row space"><h2 className="sectionTitle">Your review queue</h2><span className="badge">{needs.length} waiting</span></div>{projects.length===0?<><p className="muted">Your studio is empty. Start in demo mode so you can test every approval screen without spending money.</p><Link href="/videos/new" className="btn primary tap" style={{display:"grid",placeItems:"center"}}>Create First POV</Link></>:projects.map(p=><div className="project" key={p.id}><div style={{minWidth:0}}><div className="row"><strong>{p.title}</strong><span className={`badge ${p.status==="published"?"green":p.status.includes("ready")?"amber":""}`}>{p.status.replaceAll("_"," ")}</span></div><div className="muted">{p.category} · {p.stage.replaceAll("_"," ")} · ${Number(p.actual_cost||0).toFixed(2)}</div></div><Link className="btn primary tap" href={`/videos/${p.id}`}>{p.status==="published"?"View":"Review"}</Link></div>)}</section>
 </>}
