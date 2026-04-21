/**
 * Frontend mock data engine.
 *
 * Used as a fallback when the backend API is unavailable (e.g. static demo
 * deploy, or during local frontend-only development). Produces the same
 * shape of data the backend produces, so the UI renders correctly either way.
 *
 * History note: this was previously inline in app.jsx as ~8 one-line minified
 * functions. Extracted here for maintainability. The constants (CH, CAMPS, MO,
 * SEA, REG, PROD) have been re-expanded for readability. The functions (gen,
 * runAttr, fitC, optim, diag, pil) are left in their original one-line form
 * because they have no test coverage and rewriting them is a medium-risk
 * change that should be done behind a live UI, which this working session
 * doesn't have. TODO: re-expand functions in a subsequent session with
 * npm run dev running.
 */

// ══════════════════════════════════════════════════════════════════
//   CHANNEL TAXONOMY
// ══════════════════════════════════════════════════════════════════

// Per-channel display metadata and response-curve parameters used by the
// frontend-only fallback curve fitting. Keys match the backend channel IDs
// exactly so the UI behaves identically in API mode vs demo mode.
//
//   type:  "online" | "offline" — drives confidence tier
//   color: canonical chart color (Tailwind palette)
//   sat:   saturation point for the frontend-only fallback fit (null = no sat)
//   a:     power-law exponent for the fallback fit
//   label: display label shown in UI
//   icon:  name of the Lucide icon used in the channel chip
export const CH = {
  paid_search:    { type: "online",  color: "#2563EB", sat: 150000, a: 0.55, label: "Paid Search",      icon: "Search" },
  organic_search: { type: "online",  color: "#059669", sat: null,   a: 0.70, label: "Organic Search",   icon: "Globe" },
  social_paid:    { type: "online",  color: "#7C3AED", sat: 120000, a: 0.50, label: "Social Paid",      icon: "Users" },
  display:        { type: "online",  color: "#D97706", sat: 80000,  a: 0.45, label: "Display",          icon: "Monitor" },
  email:          { type: "online",  color: "#0891B2", sat: 40000,  a: 0.60, label: "Email",            icon: "Mail" },
  video_youtube:  { type: "online",  color: "#DC2626", sat: 100000, a: 0.48, label: "Video / YouTube",  icon: "Tv" },
  events:         { type: "offline", color: "#BE185D", sat: 200000, a: 0.65, label: "Events",           icon: "MapPin" },
  direct_mail:    { type: "offline", color: "#65A30D", sat: 60000,  a: 0.42, label: "Direct Mail",      icon: "FileSpreadsheet" },
  tv_national:    { type: "offline", color: "#7E22CE", sat: 300000, a: 0.35, label: "TV National",      icon: "Tv" },
  radio:          { type: "offline", color: "#EA580C", sat: 80000,  a: 0.38, label: "Radio",            icon: "Radio" },
  ooh:            { type: "offline", color: "#0D9488", sat: 100000, a: 0.32, label: "OOH / Billboard",  icon: "Megaphone" },
  call_center:    { type: "offline", color: "#475569", sat: 50000,  a: 0.55, label: "Call Center",      icon: "Phone" },
};

// Campaigns that exist per channel in the demo dataset.
export const CAMPS = {
  paid_search:    ["PS Brand", "PS Generic", "PS Competitor", "PS Product"],
  organic_search: ["SEO Blog", "SEO Product Pages"],
  social_paid:    ["Meta Awareness", "Meta Retargeting", "LinkedIn LeadGen", "TikTok Brand"],
  display:        ["Programmatic", "Display Retargeting", "Native Ads"],
  email:          ["Newsletter", "Nurture", "Promo Blast", "Winback"],
  video_youtube:  ["Pre-Roll", "Discovery", "Shorts"],
  events:         ["Trade Show", "Webinar", "Conference"],
  direct_mail:    ["Catalog", "PostCard"],
  tv_national:    ["TV Brand Q1", "TV Product Launch"],
  radio:          ["Radio Regional", "Radio Sponsorship"],
  ooh:            ["Billboard Highway", "Transit Ads"],
  call_center:    ["Inbound Sales", "Outbound Campaign"],
};

// Month names used as labels on monthly-axis charts.
export const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Shared seasonality multiplier applied to frontend-fallback mock data
// generation. Much coarser than the backend's per-channel patterns; this
// is only used when the frontend runs standalone.
export const SEA = [0.85, 0.8, 0.95, 1.05, 1.1, 1.0, 0.9, 0.88, 1.05, 1.15, 1.25, 1.3];

export const REG  = ["North", "South", "East", "West"];
export const PROD = ["Product A", "Product B", "Product C"];


// ══════════════════════════════════════════════════════════════════
//   DATA GENERATION & ANALYTICS
// ══════════════════════════════════════════════════════════════════
//
// These functions mirror (coarsely) what the backend engines do, so the UI
// has something to render when API mode is unavailable. Each function is
// left in its original minified form because reformatting without the
// ability to run the UI is risky. They are self-contained (no React or
// recharts deps) so moving them across file boundaries is safe.

// Seeded pseudorandom generator (LCG via Park-Miller). Used so the demo
// data is deterministic across reloads.
export function sr(s){let x=s;return()=>{x=(x*16807)%2147483647;return(x-1)/2147483646}}

// Generate a full synthetic campaign-performance dataset and user-journey list.
// Returns { rows, js } matching the backend's campaign_performance/user_journeys shape.
export function gen(){const r=sr(42),n=(v,p=.1)=>Math.max(0,v*(1+(r()-.5)*2*p));const rows=[],js=[];const bS={paid_search:11e3,organic_search:700,social_paid:8500,display:5500,email:1600,video_youtube:6500,events:14e3,direct_mail:4500,tv_national:25e3,radio:6e3,ooh:8e3,call_center:3e3};const bCT={paid_search:.045,organic_search:.035,social_paid:.012,display:.004,email:.22,video_youtube:.008,events:.5,direct_mail:.15,tv_national:0,radio:0,ooh:0,call_center:.4};const bCV={paid_search:.03,organic_search:.035,social_paid:.014,display:.006,email:.045,video_youtube:.009,events:.065,direct_mail:.018,tv_national:.001,radio:.002,ooh:.001,call_center:.04};const aov={paid_search:380,organic_search:440,social_paid:260,display:175,email:320,video_youtube:230,events:1100,direct_mail:350,tv_national:500,radio:300,ooh:400,call_center:600};const imp={paid_search:8,organic_search:12,social_paid:15,display:25,email:3,video_youtube:10,events:.5,direct_mail:.8,tv_national:0,radio:0,ooh:0,call_center:0};const bnc={paid_search:.38,organic_search:.42,social_paid:.55,display:.65,email:.3,video_youtube:.5,events:.15,direct_mail:.45,tv_national:0,radio:0,ooh:0,call_center:.2};const fr={paid_search:.12,organic_search:.09,social_paid:.06,display:.025,email:.18,video_youtube:.04,events:.45,direct_mail:.1,tv_national:0,radio:0,ooh:0,call_center:.3};const np2={paid_search:35,organic_search:52,social_paid:28,display:18,email:42,video_youtube:30,events:65,direct_mail:25,tv_national:40,radio:30,ooh:20,call_center:45};
Object.entries(CH).forEach(([ch,ci])=>{CAMPS[ch].forEach(camp=>{MO.forEach((mo,mi)=>{REG.forEach(reg=>{const rm={North:1.1,South:.9,East:1,West:1.05}[reg],cm=.7+(camp.length%5)*.12;let sp=n(bS[ch]*SEA[mi]*rm*cm,.12);if(ch==="organic_search")sp=n(700*rm,.05);const ef=ci.sat?ci.sat*Math.pow(sp/ci.sat,ci.a):sp;const im2=n(ef*imp[ch],.15),cl=n(im2*bCT[ch],.12),le=n(cl*.07,.15),mq=n(le*.45,.1),sq=n(mq*.38,.1),cv=Math.max(0,Math.round(n(sq*bCV[ch]*SEA[mi]*8,.18))),rv=cv*n(aov[ch],.1);let b=bnc[ch];if(camp.includes("Retarget"))b*=.75;if(camp.includes("Awareness")||camp.includes("Brand"))b*=1.15;let f=fr[ch];if(camp==="TikTok Brand"||camp==="Native Ads")f*=.4;rows.push({month:`2025-${String(mi+1).padStart(2,"0")}`,ml:mo,ch,ct:ci.type,camp,reg,prod:PROD[Math.floor(r()*3)],spend:Math.round(sp),imps:Math.round(im2),clicks:Math.round(cl),leads:Math.round(le),mqls:Math.round(mq),sqls:Math.round(sq),conv:cv,rev:Math.round(rv),br:Math.min(1,Math.max(0,n(b,.1))),sd:Math.max(0,n(150,.2)),fc:Math.min(1,Math.max(0,f)),nps:Math.round(n(np2[ch],.05)),conf:ci.type==="online"?"High":(ch==="events"||ch==="direct_mail")?"Model-Est":"Medium"})})})})});
const chL=Object.keys(CH);for(let j=0;j<3e3;j++){const nt=[1,2,3,4,5][Math.floor(r()*5)],cv2=r()<.35,jR=cv2?n([400,800,1500,3e3][Math.floor(r()*4)],.3):0,tps=[];for(let t=0;t<nt;t++){const c=chL[Math.floor(r()*chL.length)];tps.push({ch:c,camp:CAMPS[c][Math.floor(r()*CAMPS[c].length)],o:t+1})}js.push({id:`J${j}`,tps,cv:cv2,rv:Math.round(jR),nt})}return{rows,js}}

// Run three baseline attribution models (last touch, linear, position-based 40/20/40)
// over a list of journeys. Returns { last_touch: {ch: rev}, linear: {...}, position_based: {...} }.
export function runAttr(js){const m={last_touch:{},linear:{},position_based:{}};js.filter(j=>j.cv).forEach(j=>{j.tps.forEach((tp,i)=>{const k=tp.ch;if(i===j.nt-1)m.last_touch[k]=(m.last_touch[k]||0)+j.rv;m.linear[k]=(m.linear[k]||0)+j.rv/j.nt;let w=1;if(j.nt===1)w=1;else if(j.nt===2)w=.5;else if(i===0)w=.4;else if(i===j.nt-1)w=.4;else w=.2/(j.nt-2);m.position_based[k]=(m.position_based[k]||0)+j.rv*w})});return m}

// Fit per-channel power-law response curves to monthly aggregated data.
// Returns { ch: { a, b, avgSpend, satSpend, mROI, hd, cp } }.
export function fitC(rows){const c={};Object.keys(CH).forEach(ch=>{const d={};rows.filter(r=>r.ch===ch).forEach(r=>{if(!d[r.month])d[r.month]={s:0,r:0};d[r.month].s+=r.spend;d[r.month].r+=r.rev});const pts=Object.values(d);if(pts.length<3)return;const xs=pts.map(p=>p.s),ys=pts.map(p=>p.r),lx=xs.map(x=>Math.log(Math.max(x,1))),ly=ys.map(y=>Math.log(Math.max(y,1))),mx=lx.reduce((a,b)=>a+b,0)/lx.length,my=ly.reduce((a,b)=>a+b,0)/ly.length;let nm=0,dn=0;lx.forEach((l,i)=>{nm+=(l-mx)*(ly[i]-my);dn+=(l-mx)**2});const b=dn>0?Math.min(.95,Math.max(.1,nm/dn)):.5,a=Math.exp(my-b*mx),ax=xs.reduce((a2,b2)=>a2+b2,0)/xs.length,sat=Math.pow(a*b,1/(1-b)),mR=a*b*Math.pow(Math.max(ax,1),b-1),hd=Math.max(0,(sat-ax)/sat*100),mx2=Math.max(...xs)*1.5,cp=[];for(let i=0;i<=40;i++){const x=(mx2/40)*i;cp.push({spend:Math.round(x),revenue:Math.round(a*Math.pow(Math.max(x,1),b))})}c[ch]={a,b,avgSpend:ax,satSpend:sat,mROI:mR,hd,cp}});return c}

// Greedy marginal-ROI equalisation optimizer. Returns { channels: [...], summary: {...} }.
// Simpler than the backend SLSQP but good enough for demo mode.
export function optim(curves,budget,obj="balanced",constraints={}){const chs=Object.keys(curves);const pred=(ch,s)=>{const c=curves[ch];return c.a*Math.pow(Math.max(s/12,1),c.b)*12};const cur={};chs.forEach(ch=>{cur[ch]=curves[ch].avgSpend*12});const cT=Object.values(cur).reduce((a,b)=>a+b,0),sc=budget/cT;let al={};chs.forEach(ch=>{al[ch]=cur[ch]*sc});Object.entries(constraints).forEach(([ch,c])=>{if(c.locked&&c.lockedAmount!=null)al[ch]=c.lockedAmount});const step=budget*.005;for(let i=0;i<200;i++){const unlocked=chs.filter(ch=>!constraints[ch]?.locked);if(unlocked.length<2)break;let mg=unlocked.map(ch=>{const c=curves[ch];return{ch,m:c.a*c.b*Math.pow(Math.max(al[ch]/12,1),c.b-1)}});mg.sort((a,b)=>b.m-a.m);if(mg[0].m/mg[mg.length-1].m<1.05)break;const worst=mg[mg.length-1],best=mg[0];const minA=constraints[worst.ch]?.min??budget*.02,maxA=constraints[best.ch]?.max??budget*.4;if(al[worst.ch]-step<minA||al[best.ch]+step>maxA)continue;al[worst.ch]-=step;al[best.ch]+=step}const res=chs.map(ch=>{const oR=pred(ch,al[ch]),cR=pred(ch,cur[ch]),c=curves[ch],mR=c.a*c.b*Math.pow(Math.max(al[ch]/12,1),c.b-1);return{channel:ch,cS:Math.round(cur[ch]),oS:Math.round(al[ch]),chg:((al[ch]-cur[ch])/cur[ch]*100),cR:Math.round(cR),oR:Math.round(oR),rChg:Math.round(oR-cR),cROI:(cR-cur[ch])/cur[ch],oROI:(oR-al[ch])/al[ch],mROI:mR,locked:!!constraints[ch]?.locked}});const cRev=res.reduce((a,c)=>a+c.cR,0),oRev=res.reduce((a,c)=>a+c.oR,0);return{channels:res,summary:{cRev,oRev,uplift:((oRev-cRev)/cRev*100),cROI:(cRev-budget)/budget,oROI:(oRev-budget)/budget}}}

// Rule-based diagnostic recommendation generator (SCALE / REDUCE / RETARGET / FIX / MAINTAIN).
export function diag(rows,curves,attr){const recs=[];const cm={};rows.forEach(r=>{if(!cm[r.ch])cm[r.ch]={s:0,r:0,cl:0,im:0,cv:0,le:0,mq:0,sq:0};const m=cm[r.ch];m.s+=r.spend;m.r+=r.rev;m.cl+=r.clicks;m.im+=r.imps;m.cv+=r.conv;m.le+=r.leads;m.mq+=r.mqls;m.sq+=r.sqls});Object.entries(cm).forEach(([ch,m])=>{m.roi=(m.r-m.s)/m.s;m.cac=m.s/Math.max(m.cv,1)});const rois=Object.values(cm).map(m=>m.roi).sort((a,b)=>a-b),medROI=rois[Math.floor(rois.length/2)];const cacs=Object.values(cm).map(m=>m.cac).sort((a,b)=>a-b),medCAC=cacs[Math.floor(cacs.length/2)];Object.entries(cm).forEach(([ch,m])=>{const cv=curves[ch];if(!cv)return;if(m.roi>medROI*1.3&&cv.hd>20&&cv.mROI>1.5){const ip=Math.min(cv.hd*.5,40);recs.push({type:"SCALE",ch,rationale:`${CH[ch]?.label} ROI ${m.roi.toFixed(1)}x with ${cv.hd.toFixed(0)}% headroom. Marginal ROI ${cv.mROI.toFixed(1)}x.`,action:`Increase spend by ${ip.toFixed(0)}%`,impact:Math.round(m.s*ip/100*cv.mROI*.8),conf:"High",effort:"Low"})}if(cv.mROI<1.5&&cv.hd<15){recs.push({type:"REDUCE",ch,rationale:`${CH[ch]?.label} marginal ROI ${cv.mROI.toFixed(2)}x below hurdle. Near saturation.`,action:"Reduce 15–25%, reallocate to higher-yield channels",impact:Math.round(-m.s*.2*cv.mROI),conf:"High",effort:"Low"})}if(m.cac>medCAC*1.5){recs.push({type:"RETARGET",ch,rationale:`${CH[ch]?.label} CAC $${m.cac.toFixed(0)} is ${(m.cac/medCAC).toFixed(1)}× median.`,action:"Tighten audience targeting, review bids",impact:Math.round((m.cac-medCAC)*m.cv*.3),conf:"Medium",effort:"Medium"})}});const cpm={};rows.forEach(r=>{const k=`${r.ch}|||${r.camp}`;if(!cpm[k])cpm[k]={ch:r.ch,camp:r.camp,cl:0,im:0,cv:0,s:0};const m=cpm[k];m.cl+=r.clicks;m.im+=r.imps;m.cv+=r.conv;m.s+=r.spend});const ctrs=Object.values(cpm).map(m=>m.cl/Math.max(m.im,1)).sort((a,b)=>a-b);const cvrs=Object.values(cpm).map(m=>m.cv/Math.max(m.cl,1)).sort((a,b)=>a-b);const mCTR=ctrs[Math.floor(ctrs.length/2)],mCVR=cvrs[Math.floor(cvrs.length/2)];Object.values(cpm).forEach(m=>{const ctr=m.cl/Math.max(m.im,1),cvr=m.cv/Math.max(m.cl,1);if(ctr>mCTR*1.5&&cvr<mCVR*.6){recs.push({type:"FIX",ch:m.ch,camp:m.camp,rationale:`${m.camp}: CTR ${(ctr*100).toFixed(1)}% but CVR ${(cvr*100).toFixed(2)}%. Landing page friction.`,action:"Audit landing page, test CTAs, review form UX",impact:Math.round(m.cl*(mCVR-cvr)*350*.4),conf:"High",effort:"Medium"})}});if(attr.last_touch&&attr.linear){Object.keys(attr.last_touch).forEach(ch=>{const lt=attr.last_touch[ch]||0,ln=attr.linear[ch]||0;if(lt>0&&ln/lt>1.4)recs.push({type:"MAINTAIN",ch,rationale:`${CH[ch]?.label}: last-touch $${(lt/1e3).toFixed(0)}K vs linear $${(ln/1e3).toFixed(0)}K — strong assist.`,action:"Maintain spend; don't cut on last-touch alone",impact:Math.round(ln-lt),conf:"Medium",effort:"None"})})}recs.sort((a,b)=>Math.abs(b.impact||0)-Math.abs(a.impact||0));recs.forEach((r,i)=>{r.id=`REC-${String(i+1).padStart(3,"0")}`;r.priority=i+1});return recs}

// Three-pillar value-at-risk calculation (leakage, experience suppression, avoidable cost).
export function pil(rows,opt){const tR=rows.reduce((a,r)=>a+r.rev,0);const oR=opt.summary.oRev;const leak=Math.max(0,oR-tR);const chL=opt.channels.filter(c=>c.rChg>0).map(c=>({channel:c.channel,leakage:c.rChg,type:c.chg>5?"underfunded":"aligned"})).sort((a,b)=>b.leakage-a.leakage);const cpm={};rows.forEach(r=>{const k=`${r.ch}|||${r.camp}`;if(!cpm[k])cpm[k]={ch:r.ch,camp:r.camp,cl:0,cv:0,rv:0,bS:0,cnt:0};const m=cpm[k];m.cl+=r.clicks;m.cv+=r.conv;m.rv+=r.rev;m.bS+=r.br;m.cnt++});const cvrs=Object.values(cpm).map(m=>m.cv/Math.max(m.cl,1)).sort((a,b)=>a-b),mCVR=cvrs[Math.floor(cvrs.length/2)];let tSup=0;const sI=[];Object.values(cpm).forEach(m=>{const cvr=m.cv/Math.max(m.cl,1);if(cvr<mCVR*.7&&m.cl>1e3){const gap=mCVR-cvr,sR=m.cl*gap*(m.rv/Math.max(m.cv,1));tSup+=sR;sI.push({ch:m.ch,camp:m.camp,cvr,sR:Math.round(sR),br:m.bS/m.cnt})}});const chC={};rows.forEach(r=>{if(!chC[r.ch])chC[r.ch]={s:0,c:0};chC[r.ch].s+=r.spend;chC[r.ch].c+=r.conv});const cacs=Object.entries(chC).map(([ch,m])=>({ch,cac:m.s/Math.max(m.c,1),cv:m.c})),mCAC=cacs.map(c=>c.cac).sort((a,b)=>a-b)[Math.floor(cacs.length/2)];let tAv=0;const cI=[];cacs.forEach(c=>{if(c.cac>mCAC*1.3){const ex=(c.cac-mCAC)*c.cv;tAv+=ex;cI.push({ch:c.ch,cac:Math.round(c.cac),av:Math.round(ex)})}});return{leak:{total:Math.round(leak),pct:leak/tR*100,byCh:chL},exp:{total:Math.round(tSup),items:sI.sort((a,b)=>b.sR-a.sR)},cost:{total:Math.round(tAv),items:cI},totalRisk:Math.round(leak+tSup+tAv)}}


// ══════════════════════════════════════════════════════════════════
//   FORMATTERS
// ══════════════════════════════════════════════════════════════════

/** Format a number as a short currency string (e.g. $1.2M, $340K, $85). */
export const F = (n, p = "$") => {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  const s = a >= 1e6 ? `${(a / 1e6).toFixed(1)}M`
          : a >= 1e3 ? `${(a / 1e3).toFixed(0)}K`
                     : a.toFixed(0);
  return `${n < 0 ? "-" : ""}${p}${s}`;
};

/** Format a number as a signed percentage (e.g. +12.3%). */
export const FP = (n) => (n == null || isNaN(n)) ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;

/** Format a number as a multiplier (e.g. 3.42x). */
export const FX = (n) => (n == null || isNaN(n)) ? "—" : `${n.toFixed(2)}x`;

/** Format a channel ID as its display name (e.g. "paid_search" -> "Paid Search"). */
export const FN = (ch) => CH[ch]?.label || ch?.replace(/_/g, " ") || "";
