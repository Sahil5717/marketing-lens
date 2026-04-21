import { useState, useEffect, useMemo } from "react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ComposedChart, Area, Legend, ReferenceLine, Cell, PieChart, Pie } from "recharts";
import { Home, BarChart3, Search, Lightbulb, Target, FileText, AlertTriangle, TrendingUp, DollarSign, Users, Activity, Zap, ArrowRight, Filter, Play, Download, Lock, Unlock, Shield, Eye, RefreshCw, Award, AlertCircle, ChevronRight, ChevronDown, Layers, Globe, Monitor, Radio, Mail, Megaphone, Tv, MapPin, Phone, FileSpreadsheet, ArrowUpRight, ArrowDownRight, Minus, ExternalLink, Info, CheckCircle, XCircle } from "lucide-react";

// Mock data constants, synthetic data generators, and formatters live in
// ./mockData.js -- extracted for readability. Imported here as named exports.
import {
  CH, CAMPS, MO, SEA, REG, PROD,
  sr, gen, runAttr, fitC, optim, diag, pil,
  F, FP, FX, FN,
} from "./mockData";

/*
  ┌──────────────────────────────────────────────────────────────┐
  │ FILE MAP                                                      │
  │                                                              │
  │   Lines ~24-32  : API_BASE + apiCall (fetch wrapper)          │
  │   Lines ~36-141 : export default function App — main component│
  │                   (state, useEffects, event handlers)         │
  │   Lines ~143-158: V (design tokens) + TABS (navigation)       │
  │   Lines ~160-205: UI primitives (Card, KPI, Badge, Btn,       │
  │                   SectionLabel, InsightStrip, SmartRecCard)   │
  │   Lines ~207+   : Main render return — sidebar + 7 screens    │
  │                   (Exec Summary, Performance, Deep Dive,      │
  │                    Value Leakage, Actions, Optimizer,         │
  │                    Business Case), all inline in one big JSX  │
  │                   block.                                      │
  │                                                              │
  │ TODO next-session: extract each screen into its own file      │
  │ under frontend/screens/. Requires running `npm run dev` after │
  │ each extraction to verify nothing broke.                      │
  └──────────────────────────────────────────────────────────────┘
*/

/* ═══ API LAYER ═══ */
const API_BASE = "/api";
async function apiCall(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { headers: { "Content-Type": "application/json" }, ...options });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch (e) { console.warn(`API unavailable (${endpoint}): ${e.message}`); return null; }
}

/* ═══════════════════════════════════════════════════════════════
   APP
   ═══════════════════════════════════════════════════════════════ */
export default function App(){
const[tab,setTab]=useState("home");const[D,setD]=useState(null);const[loading,setL]=useState(true);
const[atM,setAtM]=useState("markov");const[selCh,setSelCh]=useState(null);
const[bM,setBM]=useState(1);const[obj,setObj]=useState("balanced");
const[objWeights,setObjWeights]=useState({revenue:40,roi:30,leakage:15,cost:15});
const[hillMode,setHillMode]=useState("auto");
const[fl,setFl]=useState({reg:"All",prod:"All",ct:"All",q:"All"});
const[recs,setRecs]=useState([]);const[cons,setCons]=useState({});
const[recFilter,setRecFilter]=useState("ALL");
const[apiMode,setApiMode]=useState(false);
const[smartRecs,setSmartRecs]=useState([]);
const[insights,setInsights]=useState({});
const[modelSel,setModelSel]=useState({attribution:"markov",response_curves:"auto",mmm:"auto",forecasting:"prophet",optimizer:"slsqp"});
const[modelDiag,setModelDiag]=useState({});
const[channelTrends,setChannelTrends]=useState({});
const[extData,setExtData]=useState({});
const[modelPanelOpen,setModelPanelOpen]=useState(true);
const[modelRunning,setModelRunning]=useState(false);
const[scenarios,setScenarios]=useState([]);
const[showScenarios,setShowScenarios]=useState(false);

useEffect(()=>{(async()=>{
  // Try backend API — single endpoint returns all data shaped for frontend
  const loadRes = await apiCall("/load-mock-data", { method: "POST" });
  if (loadRes && !loadRes.error) {
    const state = await apiCall("/full-state");
    if (state && state.rows && state.rows.length > 0) {
      setApiMode(true);
      setD({ rows: state.rows, opt: state.opt, pl: state.pl, attr: state.attr || {},
             curves: state.curves || {}, tS: state.tS, js: [] });
      setRecs(state.recs || []);
      setSmartRecs(state.smartRecs || []);
      setInsights(state.insights || {});
      setModelSel(state.modelSelections || {attribution:"markov",response_curves:"auto",mmm:"auto",forecasting:"prophet",optimizer:"slsqp"});
      setModelDiag(state.modelDiagnostics || {});
      setChannelTrends(state.channelTrends || {});
      setExtData(state.externalData || {});
      setL(false); return;
    }
  }
  // Fallback: demo mode with JS engines
  setTimeout(()=>{const{rows,js}=gen();const curves=fitC(rows);const attr=runAttr(js);const tS=rows.reduce((a,r)=>a+r.spend,0);const o=optim(curves,tS);const rc=diag(rows,curves,attr);const pl2=pil(rows,o);setRecs(rc);setD({rows,js,curves,attr,opt:o,pl:pl2,tS});setL(false)},400);
})()},[]);

const reOpt=async()=>{if(!D)return;
  if(apiMode){
    const mt=hillMode===true?"hill":hillMode==="auto"?"auto":"power_law";
    const res=await apiCall(`/optimize?total_budget=${D.tS*bM}&objective=${obj}&model_type=${mt}&weight_revenue=${objWeights.revenue/100}&weight_roi=${objWeights.roi/100}&weight_leakage=${objWeights.leakage/100}&weight_cost=${objWeights.cost/100}`,{method:"POST"});
    if(res){const st=await apiCall("/full-state");if(st){setD(d=>({...d,opt:st.opt,pl:st.pl,curves:st.curves||d.curves}));setSmartRecs(st.smartRecs||[]);setInsights(st.insights||{});setModelDiag(st.modelDiagnostics||{})}}
  } else {
    const o=optim(D.curves,D.tS*bM,obj,cons);const p=pil(D.rows,o);setD(d=>({...d,opt:o,pl:p}));
  }};
const changeModel=async(category,value)=>{if(!apiMode)return;
  setModelRunning(true);
  const newSel={...modelSel,[category]:value};setModelSel(newSel);
  const qs=Object.entries(newSel).map(([k,v])=>`${k}=${v}`).join("&");
  const res=await apiCall(`/model-selections?${qs}`,{method:"POST"});
  if(res){const st=await apiCall("/full-state");if(st){
    setD(d=>({...d,opt:st.opt,pl:st.pl,curves:st.curves||d.curves,attr:st.attr||d.attr}));
    setRecs(st.recs||[]);setSmartRecs(st.smartRecs||[]);setInsights(st.insights||{});
    setModelDiag(st.modelDiagnostics||{});setChannelTrends(st.channelTrends||{});
    setExtData(st.externalData||{});
  }}
  setModelRunning(false);
};
const fd=useMemo(()=>D?D.rows.filter(r=>{if(fl.reg!=="All"&&r.reg!==fl.reg&&r.region!==fl.reg)return false;if(fl.prod!=="All"&&r.prod!==fl.prod&&r.product!==fl.prod)return false;if(fl.ct!=="All"&&r.ct!==fl.ct)return false;if(fl.q!=="All"){const mo=String(r.month||"").split("-")[1];if(mo){const q=Math.ceil(parseInt(mo)/3);if(`Q${q}`!==fl.q)return false}}return true}):[],[D,fl,apiMode]);
const kp=useMemo(()=>{if(!fd.length)return{};const s=fd.reduce((a,x)=>a+x.spend,0),rv=fd.reduce((a,x)=>a+x.rev,0),cv=fd.reduce((a,x)=>a+x.conv,0),cl=fd.reduce((a,x)=>a+x.clicks,0);return{s,rv,roi:(rv-s)/s,roas:rv/s,cv,cac:s/cv,cl}},[fd]);
const chD=useMemo(()=>{if(!fd.length)return[];const c={};fd.forEach(r=>{if(!c[r.ch])c[r.ch]={ch:r.ch,ct:r.ct,s:0,rv:0,im:0,cl:0,cv:0,col:CH[r.ch]?.color};const m=c[r.ch];m.s+=r.spend;m.rv+=r.rev;m.im+=r.imps;m.cl+=r.clicks;m.cv+=r.conv});return Object.values(c).map(m=>({...m,roi:(m.rv-m.s)/m.s,roas:m.rv/m.s,cac:m.s/Math.max(m.cv,1)})).sort((a,b)=>b.roi-a.roi)},[fd]);
const cpD=useMemo(()=>{if(!fd.length)return[];const c={};fd.forEach(r=>{const k=`${r.ch}|||${r.camp}`;if(!c[k])c[k]={ch:r.ch,camp:r.camp,ct:r.ct,s:0,rv:0,cl:0,cv:0,col:CH[r.ch]?.color};const m=c[k];m.s+=r.spend;m.rv+=r.rev;m.cl+=r.clicks;m.cv+=r.conv});return Object.values(c).map(m=>({...m,roi:(m.rv-m.s)/m.s,roas:m.rv/m.s,cvr:m.cv/Math.max(m.cl,1),cac:m.s/Math.max(m.cv,1)})).sort((a,b)=>b.rv-a.rv)},[fd]);
const mT=useMemo(()=>{if(!fd.length)return[];const m={};fd.forEach(r=>{if(!m[r.month])m[r.month]={month:r.ml,s:0,rv:0};m[r.month].s+=r.spend;m[r.month].rv+=r.rev});return Object.values(m)},[fd]);
const oVo=useMemo(()=>{if(!fd.length)return{};const d={online:{s:0,rv:0,cv:0},offline:{s:0,rv:0,cv:0}};fd.forEach(r=>{d[r.ct].s+=r.spend;d[r.ct].rv+=r.rev;d[r.ct].cv+=r.conv});return Object.fromEntries(Object.entries(d).map(([k,v])=>[k,{...v,roi:(v.rv-v.s)/v.s,roas:v.rv/v.s,cac:v.s/Math.max(v.cv,1)}]))},[fd]);
const exportExecSummary=async()=>{if(apiMode){window.open(`${API_BASE}/executive-summary`,"_blank")}else{alert("Connect to backend API for executive summary export")}};
const uploadCSV=async(type)=>{if(!apiMode){alert("Connect to backend API for data uploads");return;}
  const input=document.createElement("input");input.type="file";input.accept=".csv,.xlsx";
  input.onchange=async(e)=>{const file=e.target.files[0];if(!file)return;
    const form=new FormData();form.append("file",file);
    try{const r=await fetch(`${API_BASE}/upload-${type}`,{method:"POST",body:form});
      const d=await r.json();if(r.ok){alert(`${type} data loaded: ${d.status||"Success"}. ${d.recommendations||0} new recommendations generated.`);
        const st=await apiCall("/full-state");if(st){setSmartRecs(st.smartRecs||[]);setExtData(st.externalData||{})}}
      else{alert(`Error: ${d.detail||"Upload failed"}`)}
    }catch(err){alert(`Upload failed: ${err.message}`)}};
  input.click();
};
const saveScenario=async()=>{if(!apiMode)return;
  const name=prompt("Name this scenario:");if(!name)return;
  const desc=prompt("Description (optional):") || "";
  const r=await apiCall(`/scenarios/save?name=${encodeURIComponent(name)}&description=${encodeURIComponent(desc)}`,{method:"POST"});
  if(r){alert(`Scenario "${name}" saved (ID: ${r.id})`);loadScenarios()}
};
const loadScenarios=async()=>{if(!apiMode)return;
  const r=await apiCall("/scenarios");
  if(r)setScenarios(r.scenarios||[]);
};
const deleteScenario=async(id)=>{if(!confirm("Delete this scenario?"))return;
  await apiCall(`/scenarios/${id}`,{method:"DELETE"});loadScenarios()};
const exportCSV=()=>{if(!D)return;const h="Channel,Current,Optimized,Change%,ProjRev,ROI\n";const b=D.opt.channels.map(c=>`${FN(c.channel)},${c.cS},${c.oS},${c.chg.toFixed(1)}%,${c.oR},${c.oROI.toFixed(2)}`).join("\n");const bl=new Blob([h+b],{type:"text/csv"});const u=URL.createObjectURL(bl);const a=document.createElement("a");a.href=u;a.download="yield_plan.csv";a.click()};

/* ═══ LOADING ═══ */
if(loading)return(<div style={{height:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#FAFAF7",fontFamily:"'DM Sans',sans-serif"}}>
<style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Outfit:wght@300;400;500;600;700&display=swap');@keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}`}</style>
<div style={{textAlign:"center"}}>
<div style={{width:64,height:64,borderRadius:16,background:V.gradient||"linear-gradient(135deg,#0D9488,#3B82F6)",display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto 24px",boxShadow:"0 8px 32px rgba(27,107,95,.2)",animation:"breathe 2s ease infinite"}}><Target size={30} color="#fff" strokeWidth={2}/></div>
<div style={{fontSize:26,fontWeight:700,color:"#1A1A2E",letterSpacing:-.5}}>Yield Intelligence</div>
<div style={{fontSize:13,color:"#9CA3AF",marginTop:6,letterSpacing:1,fontFamily:"'Outfit',sans-serif"}}>Loading marketing engines...</div>
</div></div>);

/* ═══ DESIGN TOKENS ═══ */
const V = {
  bg:"#F8FAFC", card:"#FFFFFF", cardBorder:"#E2E8F0", text:"#0F172A", textMuted:"#64748B", textLight:"#94A3B8",
  teal:"#0D9488", tealLight:"#F0FDFA", tealDark:"#115E59",
  green:"#059669", greenLight:"#ECFDF5", greenDark:"#065F46",
  red:"#DC2626", redLight:"#FEF2F2", amber:"#D97706", amberLight:"#FFFBEB",
  blue:"#3B82F6", blueLight:"#EFF6FF", violet:"#7C3AED", violetLight:"#F5F3FF",
  navy:"#0F172A", navyLight:"#1E293B",
  shadow:"0 1px 3px rgba(15,23,42,.08),0 1px 2px rgba(15,23,42,.04)",
  shadowMd:"0 4px 12px rgba(15,23,42,.07),0 2px 4px rgba(15,23,42,.04)",
  shadowLg:"0 10px 40px rgba(15,23,42,.12),0 4px 12px rgba(15,23,42,.06)",
  gradient:"linear-gradient(135deg,#0D9488 0%,#3B82F6 100%)",
};
const tt={background:"#fff",border:"1px solid #E8E6E1",borderRadius:8,fontSize:12,color:"#1A1A2E",boxShadow:V.shadowLg};

const TABS=[{id:"home",icon:Home,label:"Executive Summary",sec:"overview"},{id:"performance",icon:BarChart3,label:"Performance",sec:"analysis"},{id:"deepdive",icon:Search,label:"Deep Dive",sec:"analysis"},{id:"pillars",icon:AlertTriangle,label:"Value Leakage",sec:"analysis"},{id:"recommendations",icon:Lightbulb,label:"Actions",sec:"decision"},{id:"optimizer",icon:Target,label:"Optimizer",sec:"decision"},{id:"business",icon:FileText,label:"Business Case",sec:"action"}];

/* ═══ COMPONENTS ═══ */
const Card=({children,style:s,...p})=><div style={{background:V.card,borderRadius:16,padding:22,border:`1px solid ${V.cardBorder}`,boxShadow:V.shadow,transition:"all .2s cubic-bezier(.16,1,.3,1)",...s}} onMouseEnter={e=>{if(s?.cursor==="pointer"){e.currentTarget.style.boxShadow=V.shadowMd;e.currentTarget.style.transform="translateY(-1px)"}}} onMouseLeave={e=>{e.currentTarget.style.boxShadow=V.shadow;e.currentTarget.style.transform="none"}} {...p}>{children}</div>;
const KPI=({label,value,sub,color=V.teal,icon:Ic,big,onClick})=><Card onClick={onClick} style={{cursor:onClick?"pointer":"default",position:"relative",overflow:"hidden",borderTop:`3px solid ${color}20`}}>
{Ic&&<div style={{position:"absolute",top:-8,right:-8,opacity:.05}}><Ic size={big?90:60} color={color}/></div>}
<div style={{fontSize:10,color:V.textLight,textTransform:"uppercase",letterSpacing:1.5,fontWeight:700,fontFamily:"'Outfit',sans-serif",marginBottom:big?12:6}}>{label}</div>
<div style={{fontSize:big?36:24,fontWeight:800,color:V.text,letterSpacing:-.8,lineHeight:1,fontFamily:"'DM Sans',sans-serif"}}>{value}</div>
{sub&&<div style={{fontSize:12,color:sub.c||V.textMuted,marginTop:8,fontWeight:500,fontFamily:"'Outfit',sans-serif",display:"flex",alignItems:"center",gap:4}}>{sub.c===V.green||sub.c===V.teal?<ArrowUpRight size={14}/>:sub.c===V.red?<ArrowDownRight size={14}/>:null}{sub.t}</div>}
</Card>};
const Badge=({children,color=V.teal,filled})=><span style={{display:"inline-flex",alignItems:"center",padding:"3px 10px",borderRadius:20,background:filled?color:`${color}10`,color:filled?"#fff":color,fontSize:10,fontWeight:700,letterSpacing:.4,fontFamily:"'Outfit',sans-serif",border:filled?"none":`1px solid ${color}25`}}>{children}</span>;
const Btn=({children,primary,onClick,style:s})=><button onClick={onClick} style={{padding:"9px 18px",background:primary?V.gradient:"#fff",color:primary?"#fff":V.text,border:primary?"none":`1px solid ${V.cardBorder}`,borderRadius:10,cursor:"pointer",fontSize:12,fontWeight:600,fontFamily:"'Outfit',sans-serif",display:"inline-flex",alignItems:"center",gap:6,boxShadow:primary?"0 4px 14px rgba(13,148,136,.3)":V.shadow,transition:"all .2s cubic-bezier(.16,1,.3,1)",...s}} onMouseEnter={e=>{e.currentTarget.style.transform="translateY(-1px)";e.currentTarget.style.boxShadow=primary?"0 6px 20px rgba(13,148,136,.4)":V.shadowMd}} onMouseLeave={e=>{e.currentTarget.style.transform="none";e.currentTarget.style.boxShadow=primary?"0 4px 14px rgba(13,148,136,.3)":V.shadow}}>{children}</button>;
const SectionLabel=({children})=><div style={{fontSize:10,fontWeight:700,color:V.textMuted,textTransform:"uppercase",letterSpacing:1.2,marginBottom:12,fontFamily:"'Outfit',sans-serif"}}>{children}</div>;
const InsightStrip=({items,title})=>items&&items.length>0?<div style={{marginBottom:24,borderRadius:14,overflow:"hidden",border:`1px solid ${V.cardBorder}`,boxShadow:V.shadow}}>
<div style={{padding:"12px 20px",background:V.navy,display:"flex",alignItems:"center",gap:8}}>
<div style={{width:24,height:24,borderRadius:8,background:"rgba(255,255,255,.15)",display:"flex",alignItems:"center",justifyContent:"center"}}><Zap size={13} color="#fff"/></div>
<span style={{fontSize:12,fontWeight:700,color:"#fff",letterSpacing:.5}}>{title||"Key Insights"}</span>
</div>
<div style={{padding:"14px 20px",background:V.card}}>
{items.slice(0,3).map((it,i)=><div key={i} style={{display:"flex",gap:12,padding:"10px 0",borderBottom:i<Math.min(items.length,3)-1?`1px solid ${V.cardBorder}`:"none"}}>
<div style={{width:4,borderRadius:2,flexShrink:0,background:it.type==="negative"||it.type==="warning"?V.red:it.type==="positive"?V.green:V.blue}}/>
<div style={{flex:1}}><div style={{fontSize:13,fontWeight:600,color:V.text,marginBottom:2}}>{it.headline||it.text}</div>
{it.detail&&<div style={{fontSize:12,color:V.textMuted,lineHeight:1.6}}>{it.detail}</div>}
</div>
</div>)}
</div>
</div>:null;
const recColor=t=>({REALLOCATE:V.teal,DECLINING:V.red,FIX_CX:V.amber,HIDDEN_VALUE:V.violet,DEFEND:V.red,OPPORTUNITY:V.green,PREPARE:V.amber,MITIGATE:V.red,CAPITALIZE:V.green,BENCHMARK:V.blue,COST_ALERT:V.red,DIFFERENTIATE:V.violet,SCALE:V.green,REDUCE:V.red,FIX:V.amber,RETARGET:V.blue,MAINTAIN:V.teal}[t]||V.blue);
const SmartRecCard=({r,i})=>{const rc=recColor(r.type);return<Card key={i} style={{borderLeft:`4px solid ${rc}`,animation:`fadeIn .4s cubic-bezier(.16,1,.3,1) ${i*.06}s both`,position:"relative",overflow:"hidden"}}>
<div style={{position:"absolute",top:0,right:0,width:120,height:120,background:`radial-gradient(circle at top right,${rc}06,transparent 70%)`}}/>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:8}}>
<div style={{display:"flex",gap:8,alignItems:"center"}}><Badge color={rc} filled>{r.type.replace(/_/g," ")}</Badge><span style={{fontSize:13,fontWeight:600,color:CH[r.channel]?.color||V.text}}>{FN(r.channel)}</span></div>
<div style={{display:"flex",gap:6}}><Badge color={r.confidence==="High"?V.green:V.amber}>{r.confidence}</Badge>{r.impact>0&&<Badge color={V.green}>+{F(r.impact)}</Badge>}{r.impact<0&&<Badge color={V.red}>{F(r.impact)}</Badge>}</div>
</div>
<div style={{fontSize:13,color:V.textMuted,lineHeight:1.7,marginBottom:12}}>{r.narrative}</div>
{r.phased_plan&&r.phased_plan.length>0&&<div style={{background:V.bg,borderRadius:8,padding:12,marginBottom:10,border:`1px solid ${V.cardBorder}`}}>
<div style={{fontSize:10,fontWeight:700,color:V.textMuted,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>Phased Plan</div>
{r.phased_plan.map((p,j)=><div key={j} style={{display:"flex",justifyContent:"space-between",fontSize:11,padding:"4px 0",borderBottom:j<r.phased_plan.length-1?`1px solid #F3F4F6`:"none",color:V.textMuted}}>
<span><span style={{fontWeight:600,color:V.text}}>{p.month}</span> — {p.action}</span>
<span style={{color:V.teal,fontWeight:600}}>{F(p.amount)}/mo</span>
</div>)}
</div>}
{r.sources&&r.sources.length>0&&<div style={{display:"flex",gap:4,flexWrap:"wrap"}}><span style={{fontSize:10,color:V.textLight}}>Source:</span>{r.sources.map((s,j)=><span key={j} style={{fontSize:10,padding:"2px 8px",background:`${V.teal}10`,color:V.teal,borderRadius:4,fontWeight:500}}>{s}</span>)}</div>}
{r.trends&&(r.trends.qoq_roi_change||r.trends.qoq_revenue)&&<div style={{display:"flex",gap:12,marginTop:8,fontSize:10,color:V.textLight}}>
{r.trends.qoq_roi_change&&<span>QoQ ROI: <span style={{color:r.trends.qoq_roi_change>0?V.green:V.red,fontWeight:600}}>{r.trends.qoq_roi_change>0?"+":""}{r.trends.qoq_roi_change.toFixed(1)}%</span></span>}
{r.trends.yoy_roi_change&&<span>YoY ROI: <span style={{color:r.trends.yoy_roi_change>0?V.green:V.red,fontWeight:600}}>{r.trends.yoy_roi_change>0?"+":""}{r.trends.yoy_roi_change.toFixed(1)}%</span></span>}
{r.trends.qoq_revenue&&<span>QoQ Rev: <span style={{color:r.trends.qoq_revenue>0?V.green:V.red,fontWeight:600}}>{r.trends.qoq_revenue>0?"+":""}{r.trends.qoq_revenue.toFixed(1)}%</span></span>}
</div>}
</Card>;

return(<div style={{minHeight:"100vh",background:V.bg,color:V.text,fontFamily:"'Outfit','Bricolage Grotesque',sans-serif",display:"flex"}}>
<style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Outfit:wght@300;400;500;600;700&display=swap');*{box-sizing:border-box;margin:0;padding:0}::-webkit-scrollbar{width:6px}::-webkit-scrollbar-thumb{background:#D1D5DB;border-radius:3px}table{width:100%;border-collapse:collapse;font-size:12px;font-family:'Outfit',sans-serif}th{text-align:left;padding:10px 12px;color:${V.textMuted};font-weight:600;border-bottom:2px solid ${V.cardBorder};font-size:11px;text-transform:uppercase;letter-spacing:.6px}td{padding:10px 12px;border-bottom:1px solid #F3F4F6}tr:hover td{background:#FAFAF7}select{background:#fff;color:${V.text};border:1px solid ${V.cardBorder};padding:6px 10px;border-radius:8px;font-size:12px;font-family:inherit;outline:none}input[type=range]{accent-color:${V.teal};width:100%}h1,h2,h3{font-family:'DM Sans',sans-serif}@keyframes fadeIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}.fade-in{animation:fadeIn .5s cubic-bezier(.16,1,.3,1) both}`}</style>

{/* ═══ SIDEBAR ═══ */}
<nav style={{width:240,minHeight:"100vh",background:V.navy,borderRight:"none",display:"flex",flexDirection:"column",flexShrink:0,position:"sticky",top:0,zIndex:10}}>
<div style={{padding:"22px 20px",borderBottom:"1px solid rgba(255,255,255,.08)",display:"flex",alignItems:"center",gap:12}}>
<div style={{width:40,height:40,borderRadius:12,background:V.gradient,display:"flex",alignItems:"center",justifyContent:"center",boxShadow:"0 4px 16px rgba(13,148,136,.3)"}}><Target size={20} color="#fff" strokeWidth={2.5}/></div>
<div><div style={{fontSize:15,fontWeight:800,color:"#fff",fontFamily:"'DM Sans',sans-serif",letterSpacing:-.3}}>Yield Intelligence</div><div style={{fontSize:9,color:"rgba(255,255,255,.45)",letterSpacing:2,textTransform:"uppercase",marginTop:2}}>Marketing ROI Engine</div></div>
</div>
<div style={{flex:1,padding:"16px 10px"}}>
{["overview","analysis","decision","action"].map(sec=><div key={sec} style={{marginBottom:20}}>
<div style={{fontSize:9,fontWeight:700,color:"rgba(255,255,255,.3)",textTransform:"uppercase",letterSpacing:2.5,padding:"0 12px",marginBottom:8}}>{{overview:"Overview",analysis:"Analysis",decision:"Decisioning",action:"Action"}[sec]}</div>
{TABS.filter(t=>t.sec===sec).map(t=>{const active=tab===t.id;return<button key={t.id} onClick={()=>setTab(t.id)} style={{display:"flex",alignItems:"center",gap:10,width:"100%",padding:"10px 14px",border:"none",background:active?"rgba(13,148,136,.12)":"transparent",color:active?"#5EEAD4":"rgba(255,255,255,.5)",cursor:"pointer",borderRadius:10,fontSize:13,fontWeight:active?600:400,fontFamily:"'Outfit',sans-serif",transition:"all .15s",position:"relative"}}>
{active&&<div style={{position:"absolute",left:0,top:"50%",transform:"translateY(-50%)",width:3,height:20,borderRadius:2,background:V.gradient}}/>}
<t.icon size={17} strokeWidth={active?2.2:1.7}/>{t.label}
</button>})}
</div>)}
</div>
<div style={{padding:"14px 20px",borderTop:"1px solid rgba(255,255,255,.06)",display:"flex",alignItems:"center",gap:8,fontSize:11,color:"rgba(255,255,255,.35)"}}>
<Shield size={14}/><span>FY 2025</span>
{apiMode&&<Badge color={V.green} filled>API</Badge>}
{!apiMode&&<Badge color={V.amber} filled>Demo</Badge>}
</div>
</nav>

{/* ═══ MAIN ═══ */}
<main style={{flex:1,minWidth:0,overflow:"auto"}}>
{/* Filter bar */}
<div style={{position:"sticky",top:0,zIndex:5,background:"rgba(250,250,247,.92)",backdropFilter:"blur(8px)",borderBottom:`1px solid ${V.cardBorder}`,padding:"10px 32px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
<div style={{display:"flex",alignItems:"center",gap:14,fontSize:12}}>
<Filter size={14} color={V.textLight}/>
{[{k:"q",o:["All","Q1","Q2","Q3","Q4"],l:"Quarter"},{k:"reg",o:["All",...REG],l:"Region"},{k:"prod",o:["All",...PROD],l:"Product"},{k:"ct",o:["All","online","offline"],l:"Type"}].map(f=><div key={f.k} style={{display:"flex",alignItems:"center",gap:5}}><span style={{color:V.textLight,fontSize:11}}>{f.l}</span><select value={fl[f.k]} onChange={e=>setFl(p=>({...p,[f.k]:e.target.value}))}>{f.o.map(o=><option key={o} value={o}>{o}</option>)}</select></div>)}
{Object.values(fl).some(v=>v!=="All")&&<button onClick={()=>setFl({reg:"All",prod:"All",ct:"All",q:"All"})} style={{background:"none",border:"none",color:V.teal,cursor:"pointer",fontSize:11,fontWeight:600,fontFamily:"inherit"}}>Clear filters</button>}
</div>
<Btn onClick={exportCSV}><Download size={13}/>Export</Btn>
</div>

<div style={{padding:"28px 32px",maxWidth:1480,margin:"0 auto"}}>

{/* ═══ EXECUTIVE SUMMARY ═══ */}
{tab==="home"&&D&&<div className="fade-in">
{/* Hero */}
<div style={{background:`linear-gradient(135deg,${V.tealLight} 0%,#fff 40%,${V.blueLight} 100%)`,borderRadius:20,padding:"36px 40px",marginBottom:28,border:`1px solid ${V.cardBorder}`,position:"relative",overflow:"hidden"}}>
<div style={{position:"absolute",top:-40,right:60,width:180,height:180,borderRadius:"50%",background:`radial-gradient(circle,${V.teal}08,transparent 70%)`}}/>
<div style={{position:"absolute",bottom:-30,right:200,width:120,height:120,borderRadius:"50%",background:`radial-gradient(circle,${V.blue}06,transparent 70%)`}}/>
<div style={{position:"relative"}}>
<div style={{display:"inline-flex",alignItems:"center",gap:6,background:V.navy,color:"#fff",padding:"4px 12px",borderRadius:20,fontSize:10,fontWeight:700,letterSpacing:1,textTransform:"uppercase",marginBottom:14}}><Zap size={11}/>Marketing Value Summary</div>
<h1 style={{fontSize:32,fontWeight:800,color:V.text,letterSpacing:-.8,lineHeight:1.2,marginBottom:14,fontFamily:"'DM Sans',sans-serif"}}>Marketing Performance<br/>& Budget Intelligence</h1>
<p style={{fontSize:15,color:V.textMuted,lineHeight:1.6,maxWidth:620,fontFamily:"'Outfit',sans-serif"}}>{Object.keys(CH).length} channels · {cpD.length} campaigns · {fd.length.toLocaleString()} data points across online and offline</p>
</div></div>

<InsightStrip items={[...(insights.executive_headlines||[]),...(insights.risk_narratives||[]),...(insights.opportunity_narratives||[])].slice(0,3)}/>
{/* KPI Strip */}
<div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:12,marginBottom:28}}>
<KPI label="Total Spend" value={F(kp.s)} color={V.blue} icon={DollarSign} onClick={()=>setTab("performance")}/>
<KPI label="Revenue" value={F(kp.rv)} color={V.green} icon={TrendingUp} sub={{t:`${FX(kp.roas)} ROAS`,c:V.green}} onClick={()=>setTab("performance")}/>
<KPI label="Portfolio ROI" value={FX(kp.roi)} color={V.teal} icon={Award}/>
<KPI label="Conversions" value={kp.cv?.toLocaleString()} color={V.blue} icon={Users}/>
<KPI label="Avg. CAC" value={F(kp.cac)} color={V.amber} icon={Activity}/>
<KPI label="Value at Risk" value={F(D.pl.totalRisk)} color={V.red} icon={AlertTriangle} sub={{t:"Leakage + CX + Cost",c:V.red}} onClick={()=>setTab("pillars")}/>
</div>

{/* Aha Moments */}
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:16,marginBottom:28}}>
{[{color:V.red,icon:AlertCircle,title:"Value at Risk",metric:F(D.pl.leak.total),body:"Revenue leaking from saturated and underfunded channels",link:"pillars",cta:"View drivers"},
{color:V.teal,icon:TrendingUp,title:"Optimization Uplift",metric:FP(D.opt.summary.uplift),body:"Achievable without increasing total spend — just reallocation",link:"optimizer",cta:"See plan"},
{color:V.amber,icon:Activity,title:"CX Friction Loss",metric:F(D.pl.exp.total),body:"Conversion suppression from journey friction, not media",link:"recommendations",cta:"Review fixes"}].map(a=>
<Card key={a.title} style={{background:V.card,cursor:"pointer",position:"relative",overflow:"hidden"}} onClick={()=>setTab(a.link)}>
<div style={{position:"absolute",top:0,left:0,right:0,height:3,background:a.color}}/>
<div style={{display:"flex",alignItems:"center",gap:8,marginBottom:14,marginTop:4}}>
<div style={{width:36,height:36,borderRadius:10,background:`${a.color}12`,display:"flex",alignItems:"center",justifyContent:"center"}}><a.icon size={18} color={a.color}/></div>
<span style={{fontSize:11,fontWeight:700,color:V.textLight,textTransform:"uppercase",letterSpacing:1.2}}>{a.title}</span>
</div>
<div style={{fontSize:32,fontWeight:800,color:a.color,letterSpacing:-1,lineHeight:1,marginBottom:10,fontFamily:"'DM Sans',sans-serif"}}>{a.metric}</div>
<div style={{fontSize:13,color:V.textMuted,lineHeight:1.6,marginBottom:14}}>{a.body}</div>
<div style={{display:"flex",alignItems:"center",gap:4,fontSize:12,fontWeight:600,color:a.color}}>{a.cta} <ArrowRight size={14}/></div>
</Card>)}
</div>

{/* Market Context (from external data) */}
{(extData.competitive||extData.events||extData.trends||extData.categoryGrowth)&&<Card style={{marginBottom:20,borderLeft:`4px solid ${V.blue}`,background:`linear-gradient(135deg,${V.blueLight},#fff)`}}>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
<SectionLabel>Market Intelligence</SectionLabel>
<div style={{display:"flex",gap:6}}>
{extData.competitive&&<Badge color={V.blue} filled>Competitive</Badge>}
{extData.events&&<Badge color={V.amber} filled>Events</Badge>}
{extData.trends&&<Badge color={V.green} filled>Trends</Badge>}
</div>
</div>
<div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12}}>
{extData.competitive&&<div style={{textAlign:"center",padding:10,background:V.bg,borderRadius:8}}>
<div style={{fontSize:20,fontWeight:800,color:V.blue}}>{extData.competitive.n_competitors||0}</div>
<div style={{fontSize:10,color:V.textMuted}}>Competitors Tracked</div>
</div>}
{extData.competitive&&<div style={{textAlign:"center",padding:10,background:V.bg,borderRadius:8}}>
<div style={{fontSize:20,fontWeight:800,color:extData.competitive.at_risk_channels>0?V.red:V.green}}>{extData.competitive.at_risk_channels||0}</div>
<div style={{fontSize:10,color:V.textMuted}}>Channels at Risk</div>
</div>}
{extData.categoryGrowth&&<div style={{textAlign:"center",padding:10,background:V.bg,borderRadius:8}}>
<div style={{fontSize:20,fontWeight:800,color:extData.categoryGrowth.trend==="up"?V.green:V.red}}>{extData.categoryGrowth.latest_value}%</div>
<div style={{fontSize:10,color:V.textMuted}}>Category Growth</div>
</div>}
{extData.events&&<div style={{textAlign:"center",padding:10,background:V.bg,borderRadius:8}}>
<div style={{fontSize:20,fontWeight:800,color:V.amber}}>{extData.events.upcoming_events||0}</div>
<div style={{fontSize:10,color:V.textMuted}}>Upcoming Events</div>
</div>}
</div>
{extData.eventCalendar&&extData.eventCalendar.length>0&&<div style={{marginTop:12}}>
{extData.eventCalendar.slice(0,3).map((ev,i)=><div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"6px 0",borderBottom:`1px solid #F3F4F6`,fontSize:11}}>
<span><Badge color={ev.direction==="positive"?V.green:ev.direction==="negative"?V.red:V.amber}>{ev.type.replace(/_/g," ")}</Badge> <span style={{marginLeft:6}}>{ev.name}</span></span>
<span style={{color:V.textLight}}>{ev.date} · {ev.days_away}d away</span>
</div>)}
</div>}
{extData.shareOfVoice&&Object.keys(extData.shareOfVoice).length>0&&<div style={{marginTop:12}}>
<div style={{fontSize:10,fontWeight:600,color:V.textMuted,marginBottom:6}}>Share of Voice by Channel</div>
{Object.entries(extData.shareOfVoice).slice(0,5).map(([ch,sov],i)=><div key={i} style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,fontSize:11}}>
<span style={{width:80,color:CH[ch]?.color,fontWeight:500}}>{CH[ch]?.label?.slice(0,12)||ch}</span>
<div style={{flex:1,height:6,background:"#F3F4F6",borderRadius:3}}><div style={{height:"100%",background:sov.share_of_voice>0.3?V.green:V.red,borderRadius:3,width:`${Math.min(100,sov.share_of_voice*100)}%`}}/></div>
<span style={{width:35,textAlign:"right",fontWeight:600,color:sov.share_of_voice>0.3?V.green:V.red}}>{(sov.share_of_voice*100).toFixed(0)}%</span>
</div>)}
</div>}
</Card>}

{/* External Data Upload */}
{apiMode&&!(extData.competitive||extData.events||extData.trends)&&<Card style={{marginBottom:20,background:V.bg,border:`1px dashed ${V.cardBorder}`}}>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
<div><div style={{fontSize:13,fontWeight:600,color:V.text,marginBottom:4}}>Add Market Intelligence</div>
<div style={{fontSize:11,color:V.textMuted}}>Upload competitive data, market events, or industry trends to enhance recommendations</div></div>
<div style={{display:"flex",gap:8}}>
<Btn onClick={()=>uploadCSV("competitive")}><Layers size={12}/>Competitive</Btn>
<Btn onClick={()=>uploadCSV("events")}><AlertCircle size={12}/>Events</Btn>
<Btn onClick={()=>uploadCSV("trends")}><TrendingUp size={12}/>Trends</Btn>
</div></div></Card>}

{/* Charts */}
<div style={{display:"grid",gridTemplateColumns:"3fr 2fr",gap:14,marginBottom:24}}>
<Card><SectionLabel>Spend vs Revenue — Monthly Trend</SectionLabel>
<ResponsiveContainer width="100%" height={240}><ComposedChart data={mT}><defs><linearGradient id="gRev" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={V.teal} stopOpacity={.12}/><stop offset="95%" stopColor={V.teal} stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#E8E6E1"/><XAxis dataKey="month" tick={{fill:V.textMuted,fontSize:11,fontFamily:"Outfit"}}/><YAxis tick={{fill:V.textMuted,fontSize:11,fontFamily:"Outfit"}} tickFormatter={v=>F(v)}/><Tooltip contentStyle={tt} formatter={v=>F(v)} labelStyle={{fontWeight:600}}/><Legend wrapperStyle={{fontSize:12,fontFamily:"Outfit"}}/><Area dataKey="rv" fill="url(#gRev)" stroke={V.teal} strokeWidth={2.5} name="Revenue" dot={{r:3,fill:V.teal}}/><Bar dataKey="s" fill={`${V.blue}18`} stroke={`${V.blue}30`} radius={[4,4,0,0]} name="Spend"/></ComposedChart></ResponsiveContainer>
</Card>
<Card><SectionLabel>Online vs Offline Split</SectionLabel>
{oVo.online&&<div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:20}}>
{[{l:"Online",v:oVo.online,c:V.blue,ic:Monitor},{l:"Offline",v:oVo.offline,c:V.violet,ic:MapPin}].map(x=><div key={x.l} style={{background:`${x.c}08`,borderRadius:12,padding:16,textAlign:"center",border:`1px solid ${x.c}15`}}>
<div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:5,marginBottom:6}}><x.ic size={14} color={x.c}/><span style={{fontSize:10,color:V.textMuted,textTransform:"uppercase",letterSpacing:1,fontWeight:600}}>{x.l}</span></div>
<div style={{fontSize:22,fontWeight:800,color:x.c}}>{F(x.v.rv)}</div>
<div style={{fontSize:11,color:V.textMuted,marginTop:3}}>ROI {FX(x.v.roi)} · CAC {F(x.v.cac)}</div>
</div>)}
</div>
<div style={{fontSize:12,color:V.textMuted,lineHeight:2}}>
{[["Total Spend",F(oVo.online.s),F(oVo.offline.s)],["ROAS",FX(oVo.online.roas),FX(oVo.offline.roas)]].map(([l,a,b],i)=><div key={i} style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",borderBottom:`1px solid #F3F4F6`,padding:"4px 0"}}><span style={{fontWeight:500,color:V.textMuted}}>{l}</span><span style={{textAlign:"center",color:V.text,fontWeight:500}}>{a}</span><span style={{textAlign:"center",color:V.text,fontWeight:500}}>{b}</span></div>)}
</div></div>}
</Card>
</div>

{/* Top channels + actions */}
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
<Card><SectionLabel>Top Channels by ROI</SectionLabel>
{chD.slice(0,6).map((c,i)=><div key={c.ch} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"10px 0",borderBottom:i<5?`1px solid #F3F4F6`:"none",cursor:"pointer"}} onClick={()=>{setSelCh(c.ch);setTab("deepdive")}}>
<div style={{display:"flex",gap:10,alignItems:"center"}}><div style={{width:10,height:10,borderRadius:5,background:c.col}}/><span style={{fontWeight:500,fontSize:13}}>{FN(c.ch)}</span><Badge color={c.ct==="online"?V.blue:V.violet}>{c.ct}</Badge></div>
<div style={{display:"flex",gap:18,fontSize:12,fontFamily:"'Outfit',sans-serif"}}><span style={{color:V.textMuted}}>{F(c.s)}</span><span style={{color:V.teal,fontWeight:700,fontSize:13}}>{FX(c.roi)}</span><span style={{color:V.textMuted}}>{F(c.cac)} CAC</span></div>
</div>)}</Card>
<Card><SectionLabel>Priority Actions</SectionLabel>
{recs.slice(0,6).map((r,i)=><div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"9px 0",borderBottom:i<5?`1px solid #F3F4F6`:"none",cursor:"pointer",fontSize:12}} onClick={()=>setTab("recommendations")}>
<Badge color={r.type==="SCALE"?V.green:r.type==="REDUCE"?V.red:r.type==="FIX"?V.amber:V.blue} filled>{r.type}</Badge>
<span style={{color:V.textMuted,flex:1}}>{FN(r.ch)}{r.camp?` · ${r.camp}`:""}</span>
{r.impact>0&&<span style={{color:V.green,fontWeight:700}}>+{F(r.impact)}</span>}
{r.impact<0&&<span style={{color:V.red,fontWeight:600}}>{F(r.impact)}</span>}
</div>)}</Card>
</div>
</div>}

{/* ═══ PERFORMANCE ═══ */}
{tab==="performance"&&D&&<div className="fade-in">
<div style={{marginBottom:24}}><h2 style={{fontSize:26,fontWeight:800,letterSpacing:-.5}}>Performance Analysis</h2><p style={{color:V.textMuted,fontSize:14,marginTop:6,fontFamily:"'Outfit'"}}>Where is performance strong, weak, or inconsistent across channels and campaigns?</p></div>
<InsightStrip items={(insights.channel_stories||[]).slice(0,3).map(s=>({type:"insight",headline:s.channel?.replace("_"," "),detail:s.narratives?.[0]?.text||""}))}/>
<div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:12,marginBottom:24}}>
<KPI label="Spend" value={F(kp.s)} color={V.blue}/><KPI label="Revenue" value={F(kp.rv)} color={V.green}/><KPI label="ROI" value={FX(kp.roi)} color={V.teal}/><KPI label="ROAS" value={FX(kp.roas)} color={V.violet}/><KPI label="CAC" value={F(kp.cac)} color={V.amber}/>
</div>
<Card style={{marginBottom:16}}><div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14}}><SectionLabel>Attribution Model Comparison</SectionLabel>
<div style={{display:"flex",gap:4}}>{["linear","last_touch","position_based","markov"].map(m=><Btn key={m} primary={atM===m} onClick={()=>setAtM(m)} style={{fontSize:10,padding:"5px 12px"}}>{m.replace(/_/g," ")}</Btn>)}</div></div>
<table><thead><tr><th>Channel</th><th>Type</th><th style={{textAlign:"right"}}>Last Touch</th><th style={{textAlign:"right"}}>Linear</th><th style={{textAlign:"right"}}>Position</th><th style={{textAlign:"right"}}>Markov</th></tr></thead>
<tbody>{Object.keys(CH).map(ch=>{const lt=D.attr.last_touch?.[ch]||0,ln=D.attr.linear?.[ch]||0,pb=D.attr.position_based?.[ch]||0,mk=D.attr.markov?.[ch]||0;return<tr key={ch}><td><span style={{color:CH[ch]?.color,fontWeight:600}}>{FN(ch)}</span></td><td><Badge color={CH[ch]?.type==="online"?V.blue:V.violet}>{CH[ch]?.type}</Badge></td><td style={{textAlign:"right",fontWeight:atM==="last_touch"?700:400,color:atM==="last_touch"?V.teal:V.text}}>{F(lt)}</td><td style={{textAlign:"right",fontWeight:atM==="linear"?700:400,color:atM==="linear"?V.teal:V.text}}>{F(ln)}</td><td style={{textAlign:"right",fontWeight:atM==="position_based"?700:400,color:atM==="position_based"?V.teal:V.text}}>{F(pb)}</td><td style={{textAlign:"right",fontWeight:atM==="markov"?700:400,color:atM==="markov"?V.teal:V.text}}>{mk?F(mk):"—"}</td></tr>})}</tbody></table></Card>

{extData.benchmarks&&Object.keys(extData.benchmarks).length>0&&<Card style={{marginBottom:16,borderLeft:`4px solid ${V.blue}`}}><SectionLabel>Industry Benchmarks</SectionLabel>
<table><thead><tr><th>Channel</th><th style={{textAlign:"right"}}>Our CTR</th><th style={{textAlign:"right"}}>Benchmark CTR</th><th style={{textAlign:"right"}}>Our CVR</th><th style={{textAlign:"right"}}>Benchmark CVR</th><th style={{textAlign:"right"}}>Our CAC</th><th style={{textAlign:"right"}}>Benchmark CAC</th></tr></thead>
<tbody>{Object.entries(extData.benchmarks).map(([ch,bm])=>{const m=chD.find(c=>c.ch===ch)||{};return<tr key={ch}>
<td style={{color:CH[ch]?.color,fontWeight:600}}>{FN(ch)}</td>
<td style={{textAlign:"right"}}>{((m.cl||0)/Math.max(m.im||1,1)*100).toFixed(2)}%</td>
<td style={{textAlign:"right",color:V.textLight}}>{bm.ctr?(bm.ctr*100).toFixed(2)+"%":"—"}</td>
<td style={{textAlign:"right"}}>{((m.cv||0)/Math.max(m.cl||1,1)*100).toFixed(2)}%</td>
<td style={{textAlign:"right",color:V.textLight}}>{bm.cvr?(bm.cvr*100).toFixed(2)+"%":"—"}</td>
<td style={{textAlign:"right"}}>{F(m.cac)}</td>
<td style={{textAlign:"right",color:V.textLight}}>{bm.cac?F(bm.cac):"—"}</td>
</tr>})}</tbody></table></Card>}

<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:16}}>
<Card><SectionLabel>ROI by Channel</SectionLabel><ResponsiveContainer width="100%" height={280}><BarChart data={chD} layout="vertical"><CartesianGrid strokeDasharray="3 3" stroke="#E8E6E1"/><XAxis type="number" tick={{fill:V.textMuted,fontSize:11}} tickFormatter={v=>FX(v)}/><YAxis dataKey="ch" type="category" tick={{fill:V.textMuted,fontSize:10}} width={100} tickFormatter={v=>FN(v)}/><Tooltip contentStyle={tt} formatter={v=>FX(v)}/><Bar dataKey="roi" radius={[0,6,6,0]} name="ROI">{chD.map((c,i)=><Cell key={i} fill={c.col}/>)}</Bar></BarChart></ResponsiveContainer></Card>
<Card><SectionLabel>Channel × Campaign Matrix</SectionLabel><div style={{overflowX:"auto",maxHeight:280}}><table><thead><tr><th>Campaign</th><th style={{textAlign:"right"}}>Spend</th><th style={{textAlign:"right"}}>Revenue</th><th style={{textAlign:"right"}}>ROI</th><th style={{textAlign:"right"}}>CAC</th></tr></thead><tbody>{cpD.slice(0,12).map(c=><tr key={`${c.ch}-${c.camp}`} style={{cursor:"pointer"}} onClick={()=>{setSelCh(c.ch);setTab("deepdive")}}><td><span style={{fontWeight:500}}>{c.camp}</span><span style={{fontSize:10,color:c.col,marginLeft:6}}>{FN(c.ch)}</span></td><td style={{textAlign:"right"}}>{F(c.s)}</td><td style={{textAlign:"right"}}>{F(c.rv)}</td><td style={{textAlign:"right",color:c.roi>3?V.green:c.roi>1.5?V.teal:V.red,fontWeight:700}}>{FX(c.roi)}</td><td style={{textAlign:"right"}}>{F(c.cac)}</td></tr>)}</tbody></table></div></Card>
</div></div>}

{/* ═══ DEEP DIVE ═══ */}
{tab==="deepdive"&&D&&<div className="fade-in">
<div style={{marginBottom:24}}><h2 style={{fontSize:26,fontWeight:800,letterSpacing:-.5}}>Channel Deep Dive</h2><p style={{color:V.textMuted,fontSize:14,marginTop:6,fontFamily:"'Outfit'"}}>Understand why a channel is performing the way it is</p></div>
<div style={{display:"flex",gap:12,marginBottom:24}}><select value={selCh||""} onChange={e=>setSelCh(e.target.value)} style={{padding:"10px 14px",fontSize:13,borderRadius:10}}><option value="">Select a channel...</option>{Object.keys(CH).map(ch=><option key={ch} value={ch}>{FN(ch)}</option>)}</select></div>
{selCh&&(()=>{const cr=fd.filter(r=>r.ch===selCh);const tS2=cr.reduce((a,r)=>a+r.spend,0),tR2=cr.reduce((a,r)=>a+r.rev,0);const mo={};cr.forEach(r=>{if(!mo[r.month])mo[r.month]={month:r.ml,s:0,rv:0};mo[r.month].s+=r.spend;mo[r.month].rv+=r.rev});const cv=D.curves[selCh];const fn={"Impressions":0,"Clicks":0,"Leads":0,"MQLs":0,"SQLs":0,"Conversions":0};cr.forEach(r=>{fn.Impressions+=r.imps;fn.Clicks+=r.clicks;fn.Leads+=r.leads;fn.MQLs+=r.mqls;fn.SQLs+=r.sqls;fn.Conversions+=r.conv});
return<><div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12,marginBottom:20}}>
<KPI label="Spend" value={F(tS2)} color={V.blue}/><KPI label="Revenue" value={F(tR2)} color={V.green}/><KPI label="ROI" value={FX((tR2-tS2)/tS2)} color={V.teal}/><KPI label="Conversions" value={cr.reduce((a,r)=>a+r.conv,0).toLocaleString()} color={V.blue}/>
</div>
{channelTrends[selCh]&&<InsightStrip items={[
  channelTrends[selCh]?.qoq?.revenue?.direction!=="flat"?{type:channelTrends[selCh].qoq.revenue.direction==="up"?"positive":"warning",headline:`QoQ Revenue: ${channelTrends[selCh].qoq.revenue.change_pct>0?"+":""}${channelTrends[selCh].qoq.revenue.change_pct}%`,detail:`${channelTrends[selCh].qoq.revenue.direction==="up"?"Improving":"Declining"} quarter-over-quarter`}:null,
  channelTrends[selCh]?.yoy?.revenue?{type:channelTrends[selCh].yoy.revenue.direction==="up"?"positive":"warning",headline:`YoY Revenue: ${channelTrends[selCh].yoy.revenue.change_pct>0?"+":""}${channelTrends[selCh].yoy.revenue.change_pct}%`,detail:`Year-over-year trend`}:null,
  channelTrends[selCh]?.trailing?.roi?{type:channelTrends[selCh].trailing.roi.direction==="up"?"positive":"negative",headline:`Trailing ROI: ${channelTrends[selCh].trailing.roi.direction}`,detail:`Last 3 months vs prior 3 months: ${channelTrends[selCh].trailing.roi.change_pct>0?"+":""}${channelTrends[selCh].trailing.roi.change_pct}%`}:null,
].filter(Boolean)}/>}
{extData.shareOfVoice?.[selCh]&&<Card style={{marginBottom:14,borderLeft:`4px solid ${V.blue}`}}>
<SectionLabel>Competitive Positioning</SectionLabel>
<div style={{display:"flex",gap:20,fontSize:12}}>
<div><span style={{color:V.textMuted}}>Our Spend:</span> <span style={{fontWeight:700}}>{F(extData.shareOfVoice[selCh].our_spend)}</span></div>
<div><span style={{color:V.textMuted}}>Competitor Spend:</span> <span style={{fontWeight:700}}>{F(extData.shareOfVoice[selCh].competitor_spend)}</span></div>
<div><span style={{color:V.textMuted}}>Share of Voice:</span> <span style={{fontWeight:700,color:extData.shareOfVoice[selCh].share_of_voice>0.3?V.green:V.red}}>{(extData.shareOfVoice[selCh].share_of_voice*100).toFixed(0)}%</span></div>
</div></Card>}
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:16}}>
<Card><SectionLabel>Revenue & Spend Trend</SectionLabel><ResponsiveContainer width="100%" height={220}><ComposedChart data={Object.values(mo)}><CartesianGrid strokeDasharray="3 3" stroke="#E8E6E1"/><XAxis dataKey="month" tick={{fill:V.textMuted,fontSize:11}}/><YAxis tick={{fill:V.textMuted,fontSize:11}} tickFormatter={v=>F(v)}/><Tooltip contentStyle={tt} formatter={v=>F(v)}/><Legend wrapperStyle={{fontSize:11}}/><Bar dataKey="s" fill={`${V.blue}15`} stroke={`${V.blue}30`} radius={[3,3,0,0]} name="Spend"/><Line dataKey="rv" stroke={V.teal} strokeWidth={2.5} dot={{r:3,fill:V.teal}} name="Revenue"/></ComposedChart></ResponsiveContainer></Card>
{cv&&<Card><SectionLabel>Response Curve (Diminishing Returns)</SectionLabel><div style={{fontSize:11,color:V.textMuted,marginBottom:8}}>Headroom: <span style={{color:cv.hd>30?V.green:V.amber,fontWeight:700}}>{cv.hd.toFixed(0)}%</span> · Marginal ROI: <span style={{color:V.teal,fontWeight:700}}>{FX(cv.mROI)}</span></div><ResponsiveContainer width="100%" height={190}><ComposedChart data={cv.cp}><CartesianGrid strokeDasharray="3 3" stroke="#E8E6E1"/><XAxis dataKey="spend" tick={{fill:V.textMuted,fontSize:10}} tickFormatter={v=>F(v)}/><YAxis tick={{fill:V.textMuted,fontSize:10}} tickFormatter={v=>F(v)}/><Tooltip contentStyle={tt} formatter={v=>F(v)}/><Line dataKey="revenue" stroke={V.teal} strokeWidth={2.5} dot={false} name="Predicted Revenue"/><ReferenceLine x={Math.round(cv.avgSpend)} stroke={V.amber} strokeDasharray="5 5" label={{value:"Current",fill:V.amber,fontSize:10}}/></ComposedChart></ResponsiveContainer></Card>}
</div>
<Card><SectionLabel>Conversion Funnel</SectionLabel><div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:8}}>{Object.entries(fn).map(([stage,val],i,arr)=>{const rate=i>0&&arr[i-1][1]>0?((val/arr[i-1][1])*100).toFixed(1)+"%":null;return<div key={stage} style={{textAlign:"center",padding:12,background:V.bg,borderRadius:10,border:`1px solid ${V.cardBorder}`}}>
<div style={{fontSize:10,color:V.textMuted,textTransform:"uppercase",letterSpacing:.5,marginBottom:6}}>{stage}</div>
<div style={{fontSize:18,fontWeight:700,color:V.text}}>{val>=1e6?`${(val/1e6).toFixed(1)}M`:val>=1e3?`${(val/1e3).toFixed(0)}K`:val}</div>
{rate&&<div style={{fontSize:11,color:parseFloat(rate)<15?V.red:V.textMuted,marginTop:4,fontWeight:500}}>{rate}</div>}
{i<arr.length-1&&<div style={{color:V.textLight,marginTop:2}}>→</div>}
</div>})}</div></Card>
</>})()}
{!selCh&&<Card style={{textAlign:"center",padding:60}}><Search size={44} color="#D1D5DB" style={{margin:"0 auto 14px"}}/><div style={{fontSize:18,fontWeight:600,color:V.textMuted}}>Select a channel to explore</div><p style={{fontSize:13,color:V.textLight,marginTop:6}}>Use the dropdown above for detailed channel and campaign analysis</p></Card>}
</div>}

{/* ═══ LEAKAGE ═══ */}
{tab==="pillars"&&D&&<div className="fade-in">
<div style={{marginBottom:24}}><h2 style={{fontSize:26,fontWeight:800,letterSpacing:-.5}}>Value Leakage Analysis</h2><p style={{color:V.textMuted,fontSize:14,marginTop:6}}>How much value are we losing from wrong allocation and poor execution?</p></div>
<InsightStrip items={(insights.risk_narratives||[]).map(r=>({type:"warning",headline:r.headline,detail:r.detail}))}/>
<div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12,marginBottom:24}}>
<KPI label="Total Value at Risk" value={F(D.pl.totalRisk)} color={V.red} icon={AlertTriangle} big/><KPI label="Revenue Leakage" value={F(D.pl.leak.total)} color={V.red} sub={{t:`${D.pl.leak.pct.toFixed(1)}% of revenue`,c:V.red}}/><KPI label="CX Suppression" value={F(D.pl.exp.total)} color={V.amber} sub={{t:`${D.pl.exp.items.length} campaigns`,c:V.amber}}/><KPI label="Avoidable Cost" value={F(D.pl.cost.total)} color={V.violet}/>
</div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:16}}>
<Card style={{borderLeft:`4px solid ${V.red}`}}><SectionLabel>Revenue Leakage by Channel</SectionLabel>{D.pl.leak.byCh.slice(0,6).map((l,i)=><div key={i} style={{marginBottom:12}}><div style={{display:"flex",justifyContent:"space-between",fontSize:12,marginBottom:4}}><span style={{display:"flex",gap:6,alignItems:"center"}}><div style={{width:8,height:8,borderRadius:4,background:CH[l.channel]?.color}}/>{FN(l.channel)}</span><span style={{fontWeight:700,color:V.red}}>{F(l.leakage)}</span></div><div style={{height:6,background:"#F3F4F6",borderRadius:3}}><div style={{height:"100%",background:V.red,borderRadius:3,width:`${Math.min(100,l.leakage/Math.max(D.pl.leak.byCh[0]?.leakage||1,1)*100)}%`,transition:"width .5s"}}/></div><div style={{fontSize:10,color:V.textLight,marginTop:2}}>{l.type==="underfunded"?"Underfunded high-performer":"Misallocated budget"}</div></div>)}</Card>
<Card style={{borderLeft:`4px solid ${V.amber}`}}><SectionLabel>CX Suppression — Friction Points</SectionLabel>{D.pl.exp.items.slice(0,5).map((s,i)=><div key={i} style={{padding:"10px 0",borderBottom:`1px solid #F3F4F6`,fontSize:12}}><div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}><span style={{fontWeight:600}}>{s.camp}</span><span style={{color:V.amber,fontWeight:700}}>{F(s.sR)}</span></div><div style={{fontSize:11,color:V.textLight}}>CVR {(s.cvr*100).toFixed(2)}% vs median · Bounce {(s.br*100).toFixed(0)}%</div></div>)}</Card>
</div>
<Card style={{borderLeft:`4px solid ${V.green}`,background:`linear-gradient(135deg,${V.greenLight},#fff)`}}><SectionLabel>Correction Potential</SectionLabel><div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:20,textAlign:"center"}}>{[{l:"Reallocation Uplift",v:D.pl.leak.total*.6,c:V.green},{l:"CX Fix Recovery",v:D.pl.exp.total*.4,c:V.amber},{l:"Cost Savings",v:D.pl.cost.total*.7,c:V.violet}].map(it=><div key={it.l}><div style={{fontSize:28,fontWeight:800,color:it.c}}>{F(it.v)}</div><div style={{fontSize:12,color:V.textMuted,marginTop:4}}>{it.l}</div></div>)}</div><div style={{borderTop:`1px solid ${V.cardBorder}`,paddingTop:14,marginTop:20,display:"flex",justifyContent:"space-between",alignItems:"center"}}><span style={{fontSize:14,fontWeight:600,color:V.textMuted}}>Total Recoverable Value</span><span style={{fontSize:26,fontWeight:800,color:V.green}}>{F(D.pl.leak.total*.6+D.pl.exp.total*.4+D.pl.cost.total*.7)}</span></div></Card>
</div>}

{/* ═══ RECOMMENDATIONS ═══ */}
{tab==="recommendations"&&D&&<div className="fade-in">
<div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",marginBottom:24}}><div><h2 style={{fontSize:26,fontWeight:800,letterSpacing:-.5}}>Recommendations & Insights</h2><p style={{color:V.textMuted,fontSize:14,marginTop:6}}>AI-backed actions with historical context, QoQ/YoY trends, and model provenance</p></div><div style={{display:"flex",gap:5}}>{["ALL","REALLOCATE","DECLINING","FIX_CX","HIDDEN_VALUE","SCALE","REDUCE","FIX","MAINTAIN","RETARGET"].map(t=><Btn key={t} primary={recFilter===t} onClick={()=>setRecFilter(t)} style={{fontSize:10,padding:"6px 12px"}}>{t}</Btn>)}</div></div>
{smartRecs.length>0&&<><div style={{fontSize:10,fontWeight:700,color:V.teal,textTransform:"uppercase",letterSpacing:1.2,marginBottom:12}}>Strategic Recommendations (with context)</div>
<div style={{display:"grid",gridTemplateColumns:"1fr",gap:14,marginBottom:28}}>
{smartRecs.filter(r=>recFilter==="ALL"||r.type===recFilter).slice(0,8).map((r,i)=><SmartRecCard key={i} r={r} i={i}/>)}
</div></>}
<div style={{fontSize:10,fontWeight:700,color:V.textMuted,textTransform:"uppercase",letterSpacing:1.2,marginBottom:12}}>Channel & Campaign Actions</div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
{recs.filter(r=>recFilter==="ALL"||r.type===recFilter).slice(0,12).map((r,i)=><Card key={i} style={{borderLeft:`4px solid ${r.type==="SCALE"?V.green:r.type==="REDUCE"?V.red:r.type==="FIX"?V.amber:V.blue}`,animation:`fadeIn .3s ease ${i*.05}s both`}}>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
<div style={{display:"flex",gap:8,alignItems:"center"}}><Badge color={r.type==="SCALE"?V.green:r.type==="REDUCE"?V.red:r.type==="FIX"?V.amber:V.blue} filled>{r.type}</Badge><span style={{fontSize:13,fontWeight:600,color:CH[r.ch]?.color}}>{FN(r.ch)}</span></div>
<Badge color={r.conf==="High"?V.green:V.amber}>{r.conf} confidence</Badge></div>
{r.camp&&<div style={{fontSize:11,color:V.textLight,marginBottom:6}}>Campaign: {r.camp}</div>}
<div style={{fontSize:13,color:V.textMuted,lineHeight:1.6,marginBottom:10}}>{r.rationale}</div>
<div style={{background:V.bg,borderRadius:10,padding:12,fontSize:12,border:`1px solid ${V.cardBorder}`}}>
<div style={{fontWeight:600,color:V.text,marginBottom:4}}>{r.action}</div>
<div style={{display:"flex",gap:20,fontSize:12}}>{r.impact!==0&&<span style={{color:r.impact>0?V.green:V.red,fontWeight:700}}>Impact: {r.impact>0?"+":""}{F(r.impact)}</span>}<span style={{color:V.textMuted}}>Effort: {r.effort}</span></div>
</div></Card>)}
</div></div>}

{/* ═══ OPTIMIZER ═══ */}
{tab==="optimizer"&&D&&<div className="fade-in">
<div style={{marginBottom:24}}><h2 style={{fontSize:26,fontWeight:800,letterSpacing:-.5}}>Budget Optimization</h2><p style={{color:V.textMuted,fontSize:14,marginTop:6}}>Find the best omnichannel mix under your constraints</p></div>
<div style={{display:"grid",gridTemplateColumns:"260px 1fr",gap:20}}>
<div><Card style={{marginBottom:14}}>
<SectionLabel>Parameters</SectionLabel>
<div style={{marginBottom:16}}><label style={{fontSize:11,color:V.textMuted,fontWeight:600,display:"block",marginBottom:6}}>Total Budget</label><input type="range" min={.5} max={2} step={.05} value={bM} onChange={e=>setBM(parseFloat(e.target.value))}/><div style={{fontSize:20,fontWeight:800,textAlign:"center",color:V.teal,marginTop:6}}>{F(D.tS*bM)}</div><div style={{fontSize:11,textAlign:"center",color:V.textMuted}}>{FP((bM-1)*100)} vs current</div></div>
<div style={{marginBottom:16}}><label style={{fontSize:11,color:V.textMuted,fontWeight:600,display:"block",marginBottom:8}}>Objective</label>{[["balanced","Balanced"],["maximize_revenue","Max Revenue"],["maximize_roi","Max ROI"],["minimize_cac","Min CAC"]].map(([k,l])=><label key={k} style={{display:"flex",alignItems:"center",gap:8,fontSize:12,marginBottom:6,cursor:"pointer",color:obj===k?V.teal:V.textMuted,fontWeight:obj===k?600:400}}><input type="radio" checked={obj===k} onChange={()=>setObj(k)} style={{accentColor:V.teal}}/>{l}</label>)}</div>
{obj==="balanced"&&<div style={{marginBottom:16}}><label style={{fontSize:11,color:V.textMuted,fontWeight:600,display:"block",marginBottom:6}}>Objective Weights</label>
{Object.entries(objWeights).map(([k,v])=><div key={k} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginBottom:4}}><span style={{color:V.textMuted,width:55,textTransform:"capitalize"}}>{k}</span><input type="range" min={0} max={100} value={v} onChange={e=>setObjWeights(p=>({...p,[k]:parseInt(e.target.value)}))} style={{flex:1,height:14,accentColor:V.teal}}/><span style={{color:V.teal,width:30,fontWeight:700,textAlign:"right"}}>{v}%</span></div>)}</div>}
{/* Model Control Panel */}
<div style={{marginBottom:16,border:`1px solid ${modelPanelOpen?V.teal+"30":V.cardBorder}`,borderRadius:10,overflow:"hidden",transition:"all .2s"}}>
<button onClick={()=>setModelPanelOpen(!modelPanelOpen)} style={{display:"flex",justifyContent:"space-between",alignItems:"center",width:"100%",padding:"10px 12px",background:modelPanelOpen?V.tealLight:"transparent",border:"none",cursor:"pointer",fontFamily:"inherit",fontSize:12,fontWeight:600,color:modelPanelOpen?V.teal:V.textMuted}}>
<span>Models & Methodology</span>
<ChevronDown size={14} style={{transform:modelPanelOpen?"rotate(180deg)":"none",transition:"transform .2s"}}/>
</button>
{modelPanelOpen&&<div style={{padding:"10px 12px",borderTop:`1px solid ${V.cardBorder}`,fontSize:11}}>
{modelRunning&&<div style={{background:V.tealLight,color:V.teal,padding:"6px 10px",borderRadius:6,marginBottom:10,fontSize:11,display:"flex",alignItems:"center",gap:6}}><RefreshCw size={12} style={{animation:"spin 1s linear infinite"}}/>Re-running engines with new models...</div>}

<div style={{marginBottom:14}}><div style={{fontWeight:700,color:V.text,marginBottom:6}}>Attribution</div>
{[["last_touch","Last Touch"],["linear","Linear"],["position_based","Position-Based"],["markov","Markov Chain"],["shapley","Shapley Values"]].map(([k,l])=><label key={k} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginBottom:4,cursor:"pointer",color:modelSel.attribution===k?V.teal:V.textMuted,fontWeight:modelSel.attribution===k?600:400}}><input type="radio" name="attr" checked={modelSel.attribution===k} onChange={()=>changeModel("attribution",k)} style={{accentColor:V.teal}}/>{l}</label>)}
{modelDiag.attribution&&<div style={{fontSize:10,color:V.textLight,marginTop:4,padding:"4px 8px",background:V.bg,borderRadius:4}}>Active: {modelSel.attribution.replace(/_/g," ")} {modelDiag.attribution?.converged!==false?"✅":"⚠️"}</div>}
</div>

<div style={{marginBottom:14}}><div style={{fontWeight:700,color:V.text,marginBottom:6}}>Response Curves</div>
{[["power_law","Power-Law (y=ax^b)"],["hill","Hill Saturation (y=ax^b/(K^b+x^b))"],["auto","Auto (best R² per channel)"]].map(([k,l])=><label key={k} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginBottom:4,cursor:"pointer",color:modelSel.response_curves===k?V.teal:V.textMuted,fontWeight:modelSel.response_curves===k?600:400}}><input type="radio" name="rc" checked={modelSel.response_curves===k} onChange={()=>{changeModel("response_curves",k);setHillMode(k==="hill"?true:k==="auto"?"auto":false)}} style={{accentColor:V.teal}}/>{l}</label>)}
{modelDiag.response_curves&&<div style={{fontSize:10,color:V.textLight,marginTop:4,padding:"4px 8px",background:V.bg,borderRadius:4}}>Active: {modelSel.response_curves} · {modelDiag.response_curves?.channels||0} channels · Avg R²: {modelDiag.response_curves?.avg_r2||0}</div>}
</div>

<div style={{marginBottom:14}}><div style={{fontWeight:700,color:V.text,marginBottom:6}}>Marketing Mix Model (MMM)</div>
{[["auto","Auto (Bayesian → MLE → OLS)"],["bayesian","Bayesian (PyMC NUTS)"],["mle","MLE (scipy L-BFGS-B)"],["ols","OLS + Bootstrap"]].map(([k,l])=><label key={k} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginBottom:4,cursor:"pointer",color:modelSel.mmm===k?V.teal:V.textMuted,fontWeight:modelSel.mmm===k?600:400}}><input type="radio" name="mmm" checked={modelSel.mmm===k} onChange={()=>changeModel("mmm",k)} style={{accentColor:V.teal}}/>{l}</label>)}
{modelDiag.mmm&&<div style={{fontSize:10,color:V.textLight,marginTop:4,padding:"4px 8px",background:V.bg,borderRadius:4}}>Active: {modelDiag.mmm?.method||"not run"} · R²: {modelDiag.mmm?.r2||"N/A"}</div>}
</div>

<div style={{marginBottom:14}}><div style={{fontWeight:700,color:V.text,marginBottom:6}}>Forecasting</div>
{[["prophet","Prophet (seasonality + holidays)"],["arima","ARIMA (classical time-series)"],["linear","Linear Fallback"]].map(([k,l])=><label key={k} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginBottom:4,cursor:"pointer",color:modelSel.forecasting===k?V.teal:V.textMuted,fontWeight:modelSel.forecasting===k?600:400}}><input type="radio" name="fc" checked={modelSel.forecasting===k} onChange={()=>changeModel("forecasting",k)} style={{accentColor:V.teal}}/>{l}</label>)}
</div>

<div><div style={{fontWeight:700,color:V.text,marginBottom:6}}>Optimizer</div>
{[["slsqp","SLSQP Constrained Optimization"],["pareto","Multi-Objective Pareto"]].map(([k,l])=><label key={k} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginBottom:4,cursor:"pointer",color:modelSel.optimizer===k?V.teal:V.textMuted,fontWeight:modelSel.optimizer===k?600:400}}><input type="radio" name="opt" checked={modelSel.optimizer===k} onChange={()=>changeModel("optimizer",k)} style={{accentColor:V.teal}}/>{l}</label>)}
{modelDiag.optimizer&&<div style={{fontSize:10,color:V.textLight,marginTop:4,padding:"4px 8px",background:V.bg,borderRadius:4}}>Converged: {modelDiag.optimizer?.converged?"✅":"⚠️ (using current allocation)"}</div>}
</div>
</div>}
</div>
<div style={{marginBottom:16}}><label style={{fontSize:11,color:V.textMuted,fontWeight:600,display:"block",marginBottom:8}}>Channel Locks</label>{Object.keys(CH).map(ch=><div key={ch} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"4px 0",fontSize:11}}><span style={{color:V.textMuted}}>{CH[ch].label.slice(0,14)}</span><button onClick={()=>setCons(c=>({...c,[ch]:{...c[ch],locked:!c[ch]?.locked,lockedAmount:D.opt.channels.find(x=>x.channel===ch)?.cS}}))} style={{background:"none",border:"none",cursor:"pointer",color:cons[ch]?.locked?V.teal:V.textLight}}>{cons[ch]?.locked?<Lock size={13}/>:<Unlock size={13}/>}</button></div>)}</div>
<Btn primary onClick={reOpt} style={{width:"100%",justifyContent:"center"}}><Play size={14}/>Run Optimizer</Btn>
<div style={{display:"flex",gap:6,marginTop:10}}>
<Btn onClick={saveScenario} style={{flex:1,justifyContent:"center",fontSize:10}}><Download size={12}/>Save Scenario</Btn>
<Btn onClick={()=>{loadScenarios();setShowScenarios(!showScenarios)}} style={{flex:1,justifyContent:"center",fontSize:10}}><Layers size={12}/>Compare</Btn>
</div>
</Card>
{showScenarios&&scenarios.length>0&&<Card style={{marginBottom:14}}>
<SectionLabel>Saved Scenarios</SectionLabel>
{scenarios.map(s=><div key={s.id} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"6px 0",borderBottom:`1px solid #F3F4F6`,fontSize:11}}>
<div><div style={{fontWeight:600,color:V.text}}>{s.name}</div>
<div style={{fontSize:10,color:V.textLight}}>{s.description||"No description"}</div>
{s.parameters&&<div style={{fontSize:10,color:V.textMuted,marginTop:2}}>Budget: {F(s.parameters.total_budget)} · Model: {s.parameters.model_type||"auto"}</div>}
</div>
<button onClick={()=>deleteScenario(s.id)} style={{background:"none",border:"none",color:V.textLight,cursor:"pointer",fontSize:10}}>✕</button>
</div>)}
</Card>}
</div>
<div>
<div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12,marginBottom:16}}>
<KPI label="Current Revenue" value={F(D.opt.summary.cRev)} color={V.textLight}/><KPI label="Optimized Revenue" value={F(D.opt.summary.oRev)} color={V.green}/><KPI label="Uplift" value={FP(D.opt.summary.uplift)} color={D.opt.summary.uplift>0?V.green:V.red}/><KPI label="Optimized ROI" value={FX(D.opt.summary.oROI)} color={V.teal}/>
</div>
<InsightStrip items={[
...(D.opt.summary.uplift>5?[{type:"positive",headline:"Reallocation opportunity",detail:`Optimized mix improves revenue by ${FP(D.opt.summary.uplift)} without increasing total spend. ${D.opt.channels.filter(c=>c.chg>10).length} channels increase, ${D.opt.channels.filter(c=>c.chg<-10).length} decrease.`}]:[]),
...(modelDiag.optimizer?.converged===false?[{type:"warning",headline:"Optimizer did not converge",detail:"SLSQP hit a singular matrix. Showing current allocation as baseline. Try changing budget or unlocking channels."}]:[]),
].slice(0,2)}/>
<Card style={{marginBottom:14}}><SectionLabel>Current vs Optimized Allocation</SectionLabel><ResponsiveContainer width="100%" height={260}><BarChart data={D.opt.channels.map(c=>({ch:CH[c.channel]?.label?.slice(0,12),current:c.cS,optimized:c.oS}))}><CartesianGrid strokeDasharray="3 3" stroke="#E8E6E1"/><XAxis dataKey="ch" tick={{fill:V.textMuted,fontSize:10}}/><YAxis tick={{fill:V.textMuted,fontSize:11}} tickFormatter={v=>F(v)}/><Tooltip contentStyle={tt} formatter={v=>F(v)}/><Legend wrapperStyle={{fontSize:11}}/><Bar dataKey="current" fill="#E8E6E1" name="Current" radius={[4,4,0,0]}/><Bar dataKey="optimized" fill={V.teal} name="Optimized" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></Card>
<Card><SectionLabel>Allocation Detail</SectionLabel><table><thead><tr><th>Channel</th><th style={{textAlign:"right"}}>Current</th><th style={{textAlign:"right"}}>Optimized</th><th style={{textAlign:"right"}}>Change</th><th style={{textAlign:"right"}}>Proj Revenue</th><th style={{textAlign:"right"}}>Marginal ROI</th></tr></thead><tbody>{D.opt.channels.sort((a,b)=>b.chg-a.chg).map(c=><tr key={c.channel} style={{opacity:c.locked?0.5:1}}><td><span style={{color:CH[c.channel]?.color,fontWeight:600}}>{FN(c.channel)}</span>{c.locked&&<Lock size={10} color={V.teal} style={{marginLeft:4}}/>}</td><td style={{textAlign:"right"}}>{F(c.cS)}</td><td style={{textAlign:"right",fontWeight:600}}>{F(c.oS)}</td><td style={{textAlign:"right",color:c.chg>0?V.green:V.red,fontWeight:700}}>{FP(c.chg)}</td><td style={{textAlign:"right"}}>{F(c.oR)}</td><td style={{textAlign:"right",color:V.teal,fontWeight:600}}>{FX(c.mROI)}</td></tr>)}</tbody></table></Card>

{/* Sensitivity Analysis */}
<Card style={{marginTop:14}}><SectionLabel>Budget Sensitivity</SectionLabel><p style={{fontSize:11,color:V.textMuted,marginBottom:10}}>Projected revenue at different budget levels using {hillMode===true?"Hill":hillMode==="auto"?"Auto-Select":"Power-Law"} response curves</p>
<table><thead><tr><th>Budget Change</th><th style={{textAlign:"right"}}>Total Budget</th><th style={{textAlign:"right"}}>Projected Revenue</th><th style={{textAlign:"right"}}>ROI</th><th style={{textAlign:"right"}}>Marginal Efficiency</th></tr></thead>
<tbody>{[-30,-20,-10,0,10,20,30,50].map(pct=>{const b=D.tS*(1+pct/100);const predRev=D.opt.channels.reduce((sum,c)=>{const ch=c.channel;const cv=D.curves?.[ch];if(!cv)return sum+c.oR*(1+pct/100);const s=(c.oS||c.cS)*(1+pct/100);const K=cv.avgSpend||1;const r=hillMode===true?((cv.a||1)*10*Math.pow(Math.max(s/12,1),cv.b||.5))/(Math.pow(K,cv.b||.5)+Math.pow(Math.max(s/12,1),cv.b||.5))*12:(cv.a||1)*Math.pow(Math.max(s/12,1),cv.b||.5)*12;return sum+r},0);const roi=(predRev-b)/Math.max(b,1);return<tr key={pct} style={{background:pct===0?V.cardBorder+"33":"transparent",fontWeight:pct===0?700:400}}><td style={{color:pct>0?V.green:pct<0?V.red:V.text}}>{pct>0?"+":""}{pct}%</td><td style={{textAlign:"right"}}>{F(b)}</td><td style={{textAlign:"right"}}>{F(predRev)}</td><td style={{textAlign:"right"}}>{FX(roi)}</td><td style={{textAlign:"right",color:pct===0?V.textMuted:roi>(D.opt.summary.oROI||0)?V.green:V.red}}>{pct===0?"Base":roi>(D.opt.summary.oROI||0)?"↑ Efficient":"↓ Diminishing"}</td></tr>})}</tbody></table></Card>

{/* Marginal ROI Table */}
{D.curves&&Object.keys(D.curves).length>0&&<Card style={{marginTop:14}}><SectionLabel>Marginal ROI at Spend Levels</SectionLabel><p style={{fontSize:11,color:V.textMuted,marginBottom:10}}>Shows diminishing returns as spend increases per channel ({hillMode===true?"Hill":hillMode==="auto"?"Auto-Select":"Power-Law"} model)</p>
<table><thead><tr><th>Channel</th>{[.5,.75,1,1.25,1.5,2].map(m=><th key={m} style={{textAlign:"right"}}>{m===1?"Current":`${Math.round(m*100)}%`}</th>)}</tr></thead>
<tbody>{Object.entries(D.curves).map(([ch,cv])=><tr key={ch}><td style={{color:CH[ch]?.color,fontWeight:600}}>{CH[ch]?.label?.slice(0,14)||FN(ch)}</td>{[.5,.75,1,1.25,1.5,2].map(m=>{const s=(cv.avgSpend||1000)*m;const mROI=(cv.a||1)*(cv.b||.5)*Math.pow(Math.max(s,1),(cv.b||.5)-1);return<td key={m} style={{textAlign:"right",fontWeight:m===1?700:400,color:mROI>1?V.green:mROI>.5?V.amber:V.red}}>{mROI.toFixed(2)}x</td>})}</tr>)}</tbody></table></Card>}

{/* Payback Period */}
<Card style={{marginTop:14}}><SectionLabel>Payback Period by Channel</SectionLabel>
<table><thead><tr><th>Channel</th><th>Confidence</th><th style={{textAlign:"right"}}>Optimized Spend</th><th style={{textAlign:"right"}}>Proj Revenue</th><th style={{textAlign:"right"}}>Base ROI</th><th style={{textAlign:"right"}}>Marginal ROI</th><th style={{textAlign:"right"}}>Payback</th></tr></thead>
<tbody>{D.opt.channels.sort((a,b)=>a.mROI-b.mROI).map(c=>{const pb=c.mROI>0?Math.max(1,Math.round(12/c.mROI)):99;return<tr key={c.channel}><td style={{color:CH[c.channel]?.color,fontWeight:600}}>{FN(c.channel)}</td><td><Badge color={CH[c.channel]?.type==="online"?V.green:V.amber}>{CH[c.channel]?.type==="online"?"High":"Model-Est"}</Badge></td><td style={{textAlign:"right"}}>{F(c.oS)}</td><td style={{textAlign:"right"}}>{F(c.oR)}</td><td style={{textAlign:"right"}}>{FX(c.oROI)}</td><td style={{textAlign:"right",color:V.teal,fontWeight:600}}>{FX(c.mROI)}</td><td style={{textAlign:"right",fontWeight:700,color:pb<=6?V.green:pb<=12?V.amber:V.red}}>{pb<=12?`${pb} mo`:"12+ mo"}</td></tr>})}</tbody></table></Card>
</div></div></div>}

{/* ═══ BUSINESS CASE ═══ */}
{tab==="business"&&D&&<div className="fade-in">
<div style={{marginBottom:24}}><h2 style={{fontSize:26,fontWeight:800,letterSpacing:-.5}}>Business Case & Impact</h2><p style={{color:V.textMuted,fontSize:14,marginTop:6}}>Translate the optimized plan into a defensible leadership narrative</p></div>
<div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12,marginBottom:24}}>
<KPI label="Revenue Uplift" value={F(D.opt.summary.oRev-D.opt.summary.cRev)} color={V.green} icon={TrendingUp} big sub={{t:FP(D.opt.summary.uplift),c:V.green}}/><KPI label="Value at Risk" value={F(D.pl.totalRisk)} color={V.red} icon={AlertTriangle} big/><KPI label="ROI Improvement" value={`${FX(D.opt.summary.cROI)} → ${FX(D.opt.summary.oROI)}`} color={V.teal} big/><KPI label="Recoverable Value" value={F(D.pl.leak.total*.6+D.pl.exp.total*.4+D.pl.cost.total*.7)} color={V.green} icon={Award} big/>
</div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:16}}>
<Card><SectionLabel>Implementation Roadmap</SectionLabel>
{[{p:"Immediate (0–30 days)",items:recs.filter(r=>r.effort==="Low").slice(0,3),c:V.green,ic:Zap},{p:"Short-term (30–90 days)",items:recs.filter(r=>r.effort==="Medium").slice(0,3),c:V.amber,ic:TrendingUp},{p:"Strategic (90+ days)",items:recs.filter(r=>r.effort==="High"||r.effort==="None").slice(0,2),c:V.violet,ic:Target}].map(ph=><div key={ph.p} style={{marginBottom:18}}>
<div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}><div style={{width:24,height:24,borderRadius:6,background:ph.c,display:"flex",alignItems:"center",justifyContent:"center"}}><ph.ic size={12} color="#fff"/></div><span style={{fontSize:12,fontWeight:700,color:ph.c}}>{ph.p}</span></div>
{ph.items.map((r,i)=><div key={i} style={{padding:"7px 0",borderBottom:`1px solid #F3F4F6`,fontSize:12,display:"flex",gap:8,alignItems:"center"}}>
<Badge color={r.type==="SCALE"?V.green:r.type==="REDUCE"?V.red:V.amber} filled>{r.type}</Badge>
<span style={{color:V.textMuted,flex:1}}>{FN(r.ch)}</span>
{r.impact>0&&<span style={{color:V.green,fontWeight:700,fontSize:11}}>+{F(r.impact)}</span>}
</div>)}</div>)}</Card>
<Card><SectionLabel>Value Correction Breakdown</SectionLabel>
{[{l:"Reallocation Revenue Uplift",v:D.pl.leak.total*.6,c:V.green},{l:"CX Fix Recovery",v:D.pl.exp.total*.4,c:V.amber},{l:"Cost Efficiency Savings",v:D.pl.cost.total*.7,c:V.violet}].map(it=><div key={it.l} style={{marginBottom:14}}>
<div style={{display:"flex",justifyContent:"space-between",fontSize:12,marginBottom:5}}><span style={{color:V.textMuted}}>{it.l}</span><span style={{fontWeight:700,color:it.c}}>{F(it.v)}</span></div>
<div style={{height:8,background:"#F3F4F6",borderRadius:4}}><div style={{height:"100%",background:it.c,borderRadius:4,width:`${Math.min(100,it.v/Math.max(D.pl.totalRisk,1)*150)}%`,transition:"width .6s"}}/></div>
</div>)}
<div style={{borderTop:`2px solid ${V.cardBorder}`,paddingTop:14,marginTop:8,display:"flex",justifyContent:"space-between",alignItems:"center"}}><span style={{fontSize:15,fontWeight:600,color:V.textMuted}}>Total Recoverable</span><span style={{fontSize:28,fontWeight:800,color:V.teal}}>{F(D.pl.leak.total*.6+D.pl.exp.total*.4+D.pl.cost.total*.7)}</span></div>
</Card></div>
<Card style={{background:`linear-gradient(135deg,${V.tealLight},#fff)`,border:`1px solid ${V.teal}20`}}>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
<div><div style={{fontSize:14,fontWeight:700,color:V.teal,marginBottom:4,fontFamily:"'DM Sans',sans-serif"}}>Export & Action Pack</div><div style={{fontSize:12,color:V.textMuted}}>Generate allocation plan, executive summary, or recommendation document</div></div>
<div style={{display:"flex",gap:10}}><Btn onClick={exportCSV}><Download size={13}/>CSV Plan</Btn><Btn primary onClick={exportExecSummary}><FileText size={13}/>Executive Summary</Btn></div>
</div></Card>

{/* External Data Upload — Business Case */}
{apiMode&&<Card style={{marginTop:14,background:V.bg,border:`1px dashed ${V.cardBorder}`}}>
<div style={{fontSize:12,fontWeight:600,color:V.text,marginBottom:8}}>Enrich with Market Data</div>
<div style={{fontSize:11,color:V.textMuted,marginBottom:12}}>Upload external data to add competitive context, market events, and industry benchmarks to your business case</div>
<div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
<Btn onClick={()=>uploadCSV("competitive")}><Layers size={12}/>Competitive Intel{extData.competitive?" ✅":""}</Btn>
<Btn onClick={()=>uploadCSV("events")}><AlertCircle size={12}/>Market Events{extData.events?" ✅":""}</Btn>
<Btn onClick={()=>uploadCSV("trends")}><TrendingUp size={12}/>Trends & Benchmarks{extData.trends?" ✅":""}</Btn>
</div>
{extData.costAdjustments&&Object.keys(extData.costAdjustments).length>0&&<div style={{marginTop:12,padding:12,background:"#fff",borderRadius:8,border:`1px solid ${V.cardBorder}`}}>
<div style={{fontSize:10,fontWeight:700,color:V.textMuted,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>Cost Trend Alerts</div>
{Object.entries(extData.costAdjustments).map(([ch,adj],i)=><div key={i} style={{display:"flex",justifyContent:"space-between",fontSize:11,padding:"4px 0",borderBottom:`1px solid #F3F4F6`}}>
<span style={{color:CH[ch]?.color,fontWeight:500}}>{FN(ch)}</span>
<span style={{color:adj.yoy_change_pct>10?V.red:adj.yoy_change_pct<-5?V.green:V.textMuted,fontWeight:600}}>{adj.yoy_change_pct>0?"+":""}{adj.yoy_change_pct}% YoY</span>
</div>)}
</div>}
</Card>}

<div style={{marginTop:16,padding:16,background:V.bg,borderRadius:12,border:`1px solid ${V.cardBorder}`}}>
<div style={{fontSize:10,fontWeight:700,color:V.textLight,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>Methodology & Confidence</div>
<div style={{fontSize:11,color:V.textLight,lineHeight:1.8}}>
{apiMode?"Models powered by backend engines: PyMC Bayesian MMM, scipy response curves (curve_fit), SLSQP constrained optimization, Prophet/ARIMA forecasting, Markov chain attribution with bootstrap CIs. All recommendations backed by statistical significance tests.":"Demo mode: response curves via log-linear regression, greedy optimizer, rule-based recommendations. Connect to backend API for production-grade PyMC MMM, scipy optimization, and Prophet forecasting with statistical validation."}
</div></div>
</div>}

</div>
{/* Footer */}
<div style={{borderTop:`1px solid ${V.cardBorder}`,padding:"14px 32px",display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:11,color:V.textLight}}>
<span>Yield Intelligence Platform</span>
<span>{apiMode?"Backend API Connected · 48 Endpoints":"Demo Mode — Connect API for full analytics"}</span>
</div>
</main></div>)}
