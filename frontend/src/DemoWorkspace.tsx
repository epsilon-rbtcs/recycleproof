import {useCallback,useEffect,useMemo,useState} from 'react';
import {ArrowLeft,ArrowRight,Check,Download,FileText,LogOut,RefreshCw,RotateCcw,ShieldCheck,TriangleAlert} from 'lucide-react';
import {API,clearDemoToken,demoRequest,demoToken} from './api';

type Claim={id:number;scenario_key:string;reference:string;scenario_title:string;scenario_description:string;recycler:string;facility:string;material_category:string;claimed_quantity:number;units:string;processing_date:string|null;shipment_quantity:number|null;permit_expiry:string|null;status:string;priority_score:number};
type Document={id:number;document_type:string;filename:string;content_type:string;size_bytes:number;summary:string;extracted_text:string;extracted_fields:Record<string,any>};
type Finding={id:number;code:string;severity:string;title:string;description:string;values_compared:Record<string,any>;document_refs:number[];recommendation:string};
type Report={id:number;status:string;priority_score:number;priority:string;score_explanation:string;checks:any[];findings:Finding[];recommended_action:string;created_at:string};
type Detail=Claim&{documents:Document[];verification_runs:Report[];reviews:any[]};
type Props={onExit:()=>void;onRestart:()=>Promise<void>};
const scenarioLetter=(key:string)=>({consistent:'A',quantity_discrepancy:'B',duplicate_shipment:'C',expired_permit:'D',identity_chronology:'E'} as Record<string,string>)[key]||'•';
const nice=(s:string)=>s?.replace(/_/g,' ').toLowerCase().replace(/\b\w/g,m=>m.toUpperCase())||'Unknown';
const quantity=(value:number,unit:string)=>`${Number(value).toLocaleString(undefined,{maximumFractionDigits:2})} ${unit}`;

export default function DemoWorkspace({onExit,onRestart}:Props){
 const [claims,setClaims]=useState<Claim[]>([]);
 const [selectedId,setSelectedId]=useState<number|null>(null);
 const [detail,setDetail]=useState<Detail|null>(null);
 const [storage,setStorage]=useState<any>(null);
 const [secondsRemaining,setSecondsRemaining]=useState<number|null>(null);
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [expired,setExpired]=useState(false);
 const [reviewComment,setReviewComment]=useState('');
 const [restartBusy,setRestartBusy]=useState(false);

 const handleFailure=useCallback((err:any)=>{
   if(err?.status===401){clearDemoToken();setExpired(true);setDetail(null);setError('This demo session has expired or is no longer valid. Start a fresh synthetic-data session to continue.');}
   else setError(err?.message||'The demo service could not be reached. Please retry.');
 },[]);
 const loadWorkspace=useCallback(async()=>{
   setLoading(true);setError('');
   try{
     if(!demoToken())throw Object.assign(new Error('Demo session missing. Start a fresh demo session.'),{status:401});
     const [status,rows]=await Promise.all([demoRequest('/demo/status'),demoRequest('/demo/claims')]);
     setStorage(status.storage);setSecondsRemaining(status.seconds_remaining);setClaims(rows);
     const preferred=rows.find((c:Claim)=>c.scenario_key==='quantity_discrepancy')||rows[0];
     if(preferred){setSelectedId(preferred.id);setDetail(await demoRequest(`/demo/claims/${preferred.id}`));}
     else{setSelectedId(null);setDetail(null);}
     setExpired(false);
   }catch(err:any){handleFailure(err)}finally{setLoading(false)}
 },[handleFailure]);
 useEffect(()=>{void loadWorkspace()},[loadWorkspace]);
 useEffect(()=>{
   if(secondsRemaining===null||expired)return;
   const timer=window.setInterval(()=>setSecondsRemaining(value=>{
     const next=Math.max(0,(value||0)-1);
     if(next===0){clearDemoToken();setExpired(true);setDetail(null);setError('This demo session has expired. Start a fresh session to continue.');}
     return next;
   }),1000);
   return()=>window.clearInterval(timer);
 },[secondsRemaining!==null,expired]);

 const report=detail?.verification_runs?.[0]||null;
 const docNames=useMemo(()=>new Map((detail?.documents||[]).map(doc=>[doc.id,`${nice(doc.document_type)} · ${doc.filename}`])),[detail?.documents]);
 const selectClaim=async(claim:Claim)=>{
   setSelectedId(claim.id);setBusy(true);setError('');setNotice('');
   try{setDetail(await demoRequest(`/demo/claims/${claim.id}`));}
   catch(err:any){handleFailure(err)}finally{setBusy(false)}
 };
 const runVerification=async()=>{
   if(!selectedId)return;setBusy(true);setError('');setNotice('');
   try{
     await demoRequest(`/demo/claims/${selectedId}/analyze`,{method:'POST'});
     const [updated,rows]=await Promise.all([demoRequest(`/demo/claims/${selectedId}`),demoRequest('/demo/claims')]);
     setDetail(updated);setClaims(rows);setNotice('Verification completed by the backend rules engine. Findings are review signals, not proof of misconduct.');
   }catch(err:any){handleFailure(err)}finally{setBusy(false)}
 };
 const markForReview=async()=>{
   if(!selectedId)return;setBusy(true);setError('');setNotice('');
   try{
     await demoRequest(`/demo/claims/${selectedId}/review`,{method:'POST',body:JSON.stringify({decision:'mark_for_further_review',comments:reviewComment})});
     setDetail(await demoRequest(`/demo/claims/${selectedId}`));setReviewComment('');setNotice('Demo-only review decision recorded in this session.');
   }catch(err:any){handleFailure(err)}finally{setBusy(false)}
 };
 const resetDemo=async()=>{
   setBusy(true);setError('');setNotice('');
   try{
     await demoRequest('/demo/reset',{method:'POST'});
     setDetail(null);setSelectedId(null);setNotice('Synthetic cases restored. Verification runs and review decisions in this session were cleared.');
     await loadWorkspace();
   }catch(err:any){handleFailure(err)}finally{setBusy(false)}
 };
 const exitDemo=async()=>{
   try{if(demoToken())await demoRequest('/demo/session/revoke',{method:'POST'});}catch{}
   clearDemoToken();onExit();
 };
 const startFresh=async()=>{setRestartBusy(true);setError('');try{await onRestart()}catch(err:any){setError(err?.message||'Could not start a new demo session. Retry.')}finally{setRestartBusy(false)}};
 const downloadDocument=async(doc:Document)=>{
   setError('');
   try{
     const response=await fetch(`${API}/api/demo/claims/${selectedId}/documents/${doc.id}/download`,{headers:{Authorization:`Bearer ${demoToken()}`}});
     if(!response.ok){const data=await response.json().catch(()=>({}));const err=Object.assign(new Error(data.detail||`Download failed (${response.status})`),{status:response.status});throw err;}
     const blob=await response.blob();const href=URL.createObjectURL(blob);const link=document.createElement('a');link.href=href;link.download=doc.filename;link.click();window.setTimeout(()=>URL.revokeObjectURL(href),1000);
   }catch(err:any){handleFailure(err)}
 };
 const remainingLabel=secondsRemaining===null?'—':`${Math.floor(secondsRemaining/60)}:${String(secondsRemaining%60).padStart(2,'0')}`;

 if(loading)return <div className="demo-loading"><div className="demo-banner"><ShieldCheck size={18}/><b>DEMO MODE — SYNTHETIC DATA</b></div><div className="demo-loading-card"><span className="demo-spinner"/><h1>Opening the evidence sandbox…</h1><p>Checking your restricted demo session and loading fictional cases.</p></div></div>;
 if(expired)return <div className="demo-shell"><header className="demo-banner"><ShieldCheck size={18}/><b>DEMO MODE — SYNTHETIC DATA</b><button onClick={onExit}><ArrowLeft size={15}/> Public landing page</button></header><main className="demo-state-card"><span className="demo-state-icon warning"><TriangleAlert size={23}/></span><h1>Demo session ended</h1><p>{error||'This short-lived demo session is no longer available.'} Your real account session, if any, has not been changed.</p><div className="demo-state-actions"><button className="demo-btn primary" onClick={startFresh} disabled={restartBusy}>{restartBusy?'Starting…':'Start a fresh demo'} <ArrowRight size={16}/></button><button className="demo-btn secondary" onClick={onExit}>Return to landing page</button></div></main></div>;
 if(error&&!claims.length)return <div className="demo-shell"><header className="demo-banner"><ShieldCheck size={18}/><b>DEMO MODE — SYNTHETIC DATA</b><button onClick={onExit}><ArrowLeft size={15}/> Public landing page</button></header><main className="demo-state-card"><span className="demo-state-icon warning"><TriangleAlert size={23}/></span><h1>We couldn't open the sandbox</h1><p>{error}</p><div className="demo-state-actions"><button className="demo-btn primary" onClick={loadWorkspace}>Retry <RefreshCw size={15}/></button><button className="demo-btn secondary" onClick={startFresh} disabled={restartBusy}>{restartBusy?'Starting…':'Start a new demo'}</button><button className="demo-btn text" onClick={onExit}>Return to landing page</button></div></main></div>;

 return <div className="demo-shell">
   <header className="demo-banner"><div className="demo-banner-brand"><span className="demo-brand-mark"><ShieldCheck size={16}/></span><span>Recycle<span>Proof</span></span></div><div className="demo-mode-tag"><i/>DEMO MODE — SYNTHETIC DATA</div><div className="demo-banner-actions"><span className="demo-expiry"><span className="demo-live-dot"/>Session {remainingLabel}</span><button onClick={exitDemo}><LogOut size={15}/> Exit demo</button></div></header>
   <div className="demo-disclaimer"><ShieldCheck size={16}/><span>This is an interactive sandbox using fictional recycling records. Findings demonstrate evidence-checking functionality and do not represent real investigations.</span></div>
   <main className="demo-main">
     <div className="demo-heading-row"><div><div className="demo-eyebrow">RECYCLEPROOF / RESTRICTED SANDBOX</div><h1>Evidence review workspace</h1><p>Choose a fictional case, inspect its source records, then run the same deterministic checks used by the application.</p></div><div className={`demo-storage ${storage?.aws_connected?'connected':''}`} title={storage?.message||''}><span className="demo-storage-dot"/><span><b>{storage?.label||'Checking storage'}</b><small>{storage?.aws_connected?'Evidence served through the backend from the configured private bucket':'No AWS S3 connection claimed'}</small></span></div></div>
     {error&&<div className="demo-alert error" role="alert"><TriangleAlert size={16}/><span>{error}</span><button onClick={loadWorkspace}>Retry</button></div>}
     {notice&&<div className="demo-alert success" role="status"><Check size={16}/><span>{notice}</span><button onClick={()=>setNotice('')} aria-label="Dismiss">×</button></div>}
     <div className="demo-layout">
       <aside className="demo-scenario-panel"><div className="demo-list-heading"><div><span>SCENARIO REGISTER</span><b>Five synthetic claims</b></div><span className="demo-count">{claims.length.toString().padStart(2,'0')}</span></div>
         <div className="demo-scenario-list">{claims.map(claim=><button key={claim.id} className={`demo-scenario-card ${selectedId===claim.id?'active':''}`} onClick={()=>void selectClaim(claim)} disabled={busy&&selectedId===claim.id}>
           <span className="demo-case-letter">{scenarioLetter(claim.scenario_key)}</span><span className="demo-scenario-copy"><b>{claim.scenario_title}</b><small>{claim.reference} · {claim.material_category}</small><em>{quantity(claim.claimed_quantity,claim.units)} reported</em></span><span className={`demo-state-pill ${claim.status==='NEEDS_REVIEW'?'attention':claim.status==='NO_MAJOR_INCONSISTENCY_DETECTED'?'passed':''}`}>{claim.status==='NOT_VERIFIED'?'Ready':nice(claim.status)}</span>
         </button>)}</div>
         <div className="demo-sidebar-foot"><span>Fictional identifiers only</span><span>·</span><span>Session-isolated</span></div>
       </aside>
       <section className="demo-case-view">
         {!detail?<div className="demo-empty"><FileText size={24}/><h2>No scenario selected</h2><p>Choose one of the synthetic cases to inspect.</p></div>:<>
           <div className="demo-case-header"><div><div className="demo-eyebrow">{detail.reference} <span>·</span> CASE {scenarioLetter(detail.scenario_key)}</div><h2>{detail.scenario_title}</h2><p>{detail.scenario_description}</p></div><button className="demo-btn secondary reset-btn" onClick={resetDemo} disabled={busy}><RotateCcw size={15}/>{busy?'Working…':'Reset demo'}</button></div>
           <div className="demo-claim-facts"><div><small>CLAIMED</small><b>{quantity(detail.claimed_quantity,detail.units)}</b></div><div><small>LINKED SHIPMENT TOTAL</small><b>{detail.shipment_quantity===null?'Not provided':quantity(detail.shipment_quantity,detail.units)}</b></div><div><small>PROCESSING DATE</small><b>{detail.processing_date||'Not provided'}</b></div><div><small>PERMIT THROUGH</small><b>{detail.permit_expiry||'Not provided'}</b></div></div>
           <div className="demo-entity-line"><span><small>RECYCLER</small><b>{detail.recycler}</b></span><span><small>FACILITY</small><b>{detail.facility}</b></span><span><small>MATERIAL</small><b>{detail.material_category}</b></span></div>
           <section className="demo-section"><div className="demo-section-heading"><div><span>01 / SOURCE RECORDS</span><h3>Evidence documents <small>{detail.documents.length} linked</small></h3></div><p>Open the document card to inspect its synthetic contents. Downloads are authorized by this demo session.</p></div>
             <div className="demo-doc-grid">{detail.documents.map(doc=><article className="demo-document" key={doc.id}><div className="demo-document-top"><span className="demo-doc-icon"><FileText size={17}/></span><span className="demo-doc-kind">{nice(doc.document_type)}</span><button aria-label={`Download ${doc.filename}`} title="Download synthetic PDF" onClick={()=>void downloadDocument(doc)}><Download size={15}/></button></div><h4>{doc.filename}</h4><p>{doc.summary}</p><details><summary>Inspect source text and recorded fields</summary><pre>{doc.extracted_text}</pre><dl>{Object.entries(doc.extracted_fields||{}).map(([key,value])=><div key={key}><dt>{nice(key)}</dt><dd>{Array.isArray(value)?value.join(', '):String(value)}</dd></div>)}</dl></details></article>)}</div>
           </section>
           <section className="demo-section demo-run-section"><div className="demo-section-heading"><div><span>02 / BACKEND VERIFICATION</span><h3>Run the checks</h3></div><button className="demo-btn primary" onClick={runVerification} disabled={busy}>{busy?'Running…':'Run Verification'} <ArrowRight size={15}/></button></div><p className="demo-engine-note">The report below is returned by the server after evaluating this session's claim and evidence records. It is not a fixed front-end result.</p>
           </section>
           {report?<section className="demo-section demo-report"><div className="demo-report-head"><div><span>VERIFICATION REPORT · RUN {report.id}</span><h3>{nice(report.status)}</h3><p>{report.score_explanation}</p></div><span className={`demo-priority ${report.priority}`}>{report.priority_score}<small>/100 · {report.priority} priority</small></span></div>
             <div className="demo-check-list">{report.checks.map((check:any)=><div className="demo-check-row" key={check.code}><span className={`demo-check-mark ${String(check.outcome).toLowerCase()}`}>{check.outcome==='PASSED'?<Check size={14}/>:check.outcome==='FAILED'?<TriangleAlert size={14}/>:<span>i</span>}</span><div><b>{nice(check.code)}</b><p>{check.detail}</p></div><span className={`demo-check-state ${String(check.outcome).toLowerCase()}`}>{nice(check.outcome)}</span></div>)}</div>
             <div className="demo-findings-heading"><h4>Findings</h4><span>{report.findings.length} review signal{report.findings.length===1?'':'s'}</span></div>
             {report.findings.length===0?<div className="demo-no-finding"><Check size={16}/> No major inconsistency detected among the checks that could be performed.</div>:<div className="demo-finding-list">{report.findings.map(finding=><article className={`demo-finding ${finding.severity}`} key={finding.id||finding.code}><div className="demo-finding-top"><span className={`demo-severity ${finding.severity}`}>{finding.severity}</span><b>{finding.title}</b></div><p>{finding.description}</p><details><summary>Inspect comparison and supporting evidence</summary>{Object.keys(finding.values_compared||{}).length>0&&<pre>{JSON.stringify(finding.values_compared,null,2)}</pre>}<div className="demo-ref-list"><b>Supporting records</b>{finding.document_refs.length?finding.document_refs.map(id=><span key={id}><FileText size={13}/>{docNames.get(id)||`Synthetic evidence record ${id}`}</span>):<small>No document-level record was available; compare the claim field shown above with the source records.</small>}</div><p className="demo-next-step"><b>Recommended next action:</b> {finding.recommendation}</p></details></article>)}</div>}
             <div className="demo-recommendation"><ShieldCheck size={17}/><span><b>What to investigate next</b>{report.recommended_action}</span></div>
           </section>:<section className="demo-report-placeholder"><span className="demo-placeholder-icon"><RefreshCw size={17}/></span><span><b>No report for this case yet</b><small>Select “Run Verification” to execute the backend checks on these fictional inputs.</small></span></section>}
           <section className="demo-review-box"><div><span>03 / HUMAN REVIEW</span><h3>Record a demo-only decision</h3><p>This review is stored only under this demo session and disappears when you reset.</p></div><div className="demo-review-action"><textarea value={reviewComment} onChange={e=>setReviewComment(e.target.value)} maxLength={2000} placeholder="Optional note: what should a reviewer confirm?"/><button className="demo-btn secondary" onClick={markForReview} disabled={busy}><ShieldCheck size={15}/>{busy?'Saving…':'Mark for Further Review'}</button></div>{detail.reviews.length>0&&<div className="demo-review-history"><b>Session review history</b>{detail.reviews.map((review:any)=><div key={review.id}><span>{nice(review.decision)}</span><small>{review.comments||'No comment'} · {review.created_at.slice(0,16).replace('T',' ')}</small></div>)}</div>}</section>
         </>}
       </section>
     </div>
     <footer className="demo-footer"><span>Fictional data only · No production records · Human review remains essential.</span><button onClick={exitDemo}><LogOut size={14}/> Exit demo and return to public page</button></footer>
   </main>
 </div>;
}
