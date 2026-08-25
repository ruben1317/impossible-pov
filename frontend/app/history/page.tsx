"use client";
import {useEffect,useMemo,useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "@/lib/api";

type HistoryIdea={id:number;title:string;category:string;premise:string;viral_reason:string;estimated_cost:number;used:boolean;project_id?:number|null;created_at:string};

export default function HistoryPage(){
 const router=useRouter();
 const [ideas,setIdeas]=useState<HistoryIdea[]>([]),[loading,setLoading]=useState(true),[using,setUsing]=useState<number|null>(null),[error,setError]=useState("");
 useEffect(()=>{api<HistoryIdea[]>("/api/ideas/history").then(setIdeas).catch((e:any)=>setError(e.message)).finally(()=>setLoading(false))},[]);
 const grouped=useMemo(()=>ideas, [ideas]);
 async function useIdea(id:number){setUsing(id);setError("");try{const p=await api<any>(`/api/ideas/history/${id}/use`,{method:"POST"});router.push(`/videos/${p.id}`)}catch(e:any){setError(e.message)}finally{setUsing(null)}}
 return <>
  <section className="hero"><div className="badge">History</div><h1 className="mobileHeadline">Idea <em>History</em></h1><p>Every idea you have already been shown is saved here. Reopen one anytime instead of paying to generate the same idea again.</p></section>
  {error&&<div className="notice">{error}</div>}
  {loading?<div className="card"><p className="muted">Loading idea history…</p></div>:grouped.length===0?<div className="card"><p className="muted">No saved ideas yet. Generate a batch and they will appear here automatically.</p></div>:<div className="grid grid-2">{grouped.map(i=><div className="card" key={i.id}>
   <div className="row space"><span className="badge">{i.category}</span><span className={`badge ${i.used?"green":""}`}>{i.used?"used":"saved"}</span></div>
   <h3 style={{marginTop:14}}>{i.title}</h3><p>{i.premise}</p><p className="muted"><strong>Why it could work:</strong> {i.viral_reason||"Saved from a previous idea batch."}</p>
   <div className="muted" style={{fontSize:12,marginBottom:12}}>Shown {new Date(i.created_at).toLocaleString()}</div>
   <button className="btn primary tap" style={{width:"100%"}} disabled={using===i.id} onClick={()=>useIdea(i.id)}>{using===i.id?"Opening…":i.used?"Use Again":"Use This Idea"}</button>
  </div>)}</div>}
 </>
}
