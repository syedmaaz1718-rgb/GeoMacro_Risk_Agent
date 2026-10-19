/* Geo-Macro Risk Agent - PRO shell */
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const toast=(m,e)=>{const t=$('#toast')||document.body.appendChild(Object.assign(document.createElement('div'),{id:'toast'}));t.textContent=m;t.style.background=e?'#e5484d':'';t.classList.add('show');clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),2600)};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{const s=(Date.now()-new Date(t))/1e3;return s<90?Math.round(s)+'s ago':s<5400?Math.round(s/60)+' min ago':Math.round(s/3600)+'h ago'};
const when=t=>new Date(t).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc84',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming:'GPS degradation cluster',military_aircraft:'Military aircraft density',ais_dark_gap:'Tanker gap from AIS',conflict_news:'Conflict news flow',oil_confirmation:'Brent confirmation',vix_confirmation:'India VIX confirmation',gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea & Bab el-Mandeb',india_pak:'India-Pakistan'};
const PLAY={NORMAL:{t:'No change.',a:'No active escalation signals. Run your normal risk process.'},CAUTION:{t:'Reduce size and widen entries.',a:'Live signals point to developing instability in this region. Do not react to the score alone; check which signals are active below.'},HIGH:{t:'Defensive only. No fresh short-vol.',a:'Multiple independent signals are active. Only reduce risk, do not add to it.'},AVOID:{t:'No fresh positions in linked underlyings.',a:'Severe, broad signal activity. Close or hedge exposed short-vol positions.'}};
async function api(u,o){const r=await fetch(u,o);if(r.status===401){showLogin();throw new Error('login')}if(!r.ok)throw new Error(u+': '+r.status);return r.json()}
const badge=l=>`<span class="badge" style="color:${colr(l)};border-color:${colr(l)}">${l}</span>`;
function ringSVG(v,l,size){size=size||96;const r=size/2-8,c=2*Math.PI*r,off=c*(1-v/100);
 return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><defs><linearGradient id="rg${size}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5eead4"/><stop offset="1" stop-color="#4ea1ff"/></linearGradient></defs><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="7"/><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="url(#rg${size})" stroke-width="7" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 ${size/2} ${size/2})"/></svg>`}
function chartSVG(id,vals,color){const el=document.getElementById(id);if(!el||!vals.length)return;const w=el.clientWidth||700,h=el.clientHeight||240,mx=Math.max(...vals,1),mn=Math.min(...vals,0);
 const px=(mx-mn)||1,pts=vals.map((v,i)=>[i/(vals.length-1)*w,h-(v-mn)/px*(h-24)-8]);
 const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
 el.innerHTML=`<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><defs><linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><path d="${d} L ${w},${h} L 0,${h} Z" fill="url(#g${id})"/><path d="${d}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round"/></svg>`}
const alertRow=a=>`<tr><td>${when(a.t)}</td><td>${esc(RN[a.region]||a.region)}</td><td>${a.score}</td><td>${badge(a.label)}</td><td>${(a.signals||[]).map(s=>esc(SIG[s]||s)).join(', ')||'-'}</td></tr>`;

/* auth */
function showLogin(){$('#login').style.display='grid'}
function hideLogin(){$('#login').style.display='none'}
async function doLogin(e){e.preventDefault();const r=await fetch('/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({password:$('#pw').value})});
 if(r.ok){hideLogin();route()}else{$('#lerr').textContent='Wrong password'}}
async function logout(){await fetch('/auth/logout',{method:'POST'});showLogin()}

/* alert modal */
function narrative(a){
 const w=window.innerWidth<640;
 const sigs=a.details?.signals||[];const seen=new Set();const lines=[];
 const dig=/\d[\d,.]*/;const val=t=>{const m=t.match(dig);return m?m[0]:null};
 const add=(k,t)=>{if(seen.has(k))return;seen.add(k);lines.push({k,t})};
 for(const s of sigs){
  if(s==='gps_jamming'||s==='gps_jamming_watch')add('gps_jamming','GPS accuracy degraded across '+(val(a.details?.aircraft_degraded||'')||'a cluster of')+' aircraft'+(a.details?.gps_jamming?.center?' near '+a.details.gps_jamming.center:''));
  if(s==='military_aircraft')add('military_aircraft','Military-flagged traffic '+ (a.details?.military?.count||'elevated') + (a.details?.military?.trend==='rising'?' and rising':'') + (a.details?.military?.samples?' over '+a.details.military.samples+' sweeps':''));
  if(s==='ais_dark_gap')add('ais_dark_gap',(a.details?.ais?.tankers!=null?a.details.ais.tankers+' tankers visible, ':'')+(a.details?.ais?.ratio!=null?'ratio '+a.details.ais.ratio+' vs baseline '+a.details.ais.baseline:'tanker presence below its recent baseline'));
  if(s==='conflict_news')add('conflict_news',(a.details?.news?.articles||'Multiple')+' conflict-coded articles in the last 6h'+(a.details?.news?.spike?' (above its recent average)':''));
  if(s==='oil_confirmation')add('oil_confirmation','Brent '+ (a.details?.oil?.price||'moved') +'%'+(a.details?.oil?.chg!=null?' ('+a.details.oil.chg+'%)':'')+' confirming the risk');
  if(s==='vix_confirmation')add('vix_confirmation','India VIX at '+(a.details?.vix?.value||'an elevated level')+(a.details?.vix?.chg!=null?' ('+a.details.vix.chg+'%)':''));
 }
 if(a.details?.headline)add('headline','News context: '+a.details.headline);
 return lines.slice(0,5).map(l=>'<li>'+l.t+'</li>').join('');
}
window.openAlert=async id=>{try{const a=await api('/alerts/'+id);
 const dl=$('#dlgBody');const sigNames=(a.signals||[]).map(s=>SIG[s]||s).join(', ');
 dl.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px"><div><div class="eyebrow">${when(a.t)}</div><h2 style="margin:4px 0">${esc(RN[a.region]||a.region)}</h2></div>${badge(a.label)}</div>
 <div class="kv" style="margin:14px 0"><b>Score</b><span>${a.score}</span><b>Signals</b><span>${esc(sigNames)||'-'}</span></div>
 ${a.details?`<div class="eyebrow">Why this fired</div><ul style="margin:8px 0 0 18px;line-height:1.8">${narrative(a)}</ul>`:''}
 <pre>${esc(JSON.stringify(a.details,null,2))}</pre>`;
 $('#dlg').showModal()}catch(e){toast('Could not load alert',1)}};

/* router */
let CLEAN=null;const routes={};
function route(){if(CLEAN){try{CLEAN()}catch(e){}CLEAN=null}
 const h=(location.hash||'#/').slice(2)||'overview';
 document.querySelectorAll('nav.side a[data-r]').forEach(a=>a.classList.toggle('on',a.dataset.r===h));
 const [name,arg]=h.split('/');
 const fn=routes[name]||routes.overview;const v=$('#view');
 v.innerHTML='';window.scrollTo(0,0);
 Promise.resolve(fn(v,arg)).catch(e=>{if(e.message!=='login')v.innerHTML='<div class="panel empty">Could not load this page ('+esc(e.message)+'). The agent may still be starting up.</div>'})}
window.onhashchange=route;
async function ticker(){try{const o=await api('/api/overview');const t=o.tick;
 $('#ticker').innerHTML=`BRENT <b>${t.brent==null?'n/a':t.brent.toFixed(2)}</b><span class="${t.brent_chg>=0?'up':'dn'}">${t.brent==null?'':(t.brent_chg>=0?'+':'')+t.brent_chg.toFixed(2)+'%'}</span>&nbsp;&nbsp;INDIA VIX <b>${t.vix==null?'n/a':t.vix.toFixed(2)}</b><span class="${t.vix_chg>=0?'up':'dn'}">${t.vix==null?'':(t.vix_chg>=0?'+':'')+t.vix_chg.toFixed(2)+'%'}</span>&nbsp;&nbsp;NIFTY <b>${t.spot?t.spot.toLocaleString('en-IN'):'n/a'}</b><span class="${t.spot_chg>=0?'up':'dn'}">${t.spot==null?'':(t.spot_chg>=0?'+':'')+t.spot_chg.toFixed(2)+'%'}</span>`}catch(e){}}

/* boot */
$('#lf').onsubmit=doLogin;
$('#logout').onclick=logout;
$('#dlgClose').onclick=()=>$('#dlg').close();
fetch('/auth/me').then(r=>r.json()).then(m=>{if(m.auth_required&&!m.authenticated)showLogin();else route()}).catch(()=>route());
setInterval(()=>{const h=location.hash;if(['','#/','#/briefing','#/feeds'].includes(h))route()},60000);

routes.overview=async v=>{
v.innerHTML=`
<div class="pro-hero">
 <div class="mapbox"><div id="promap"></div></div>
 <div class="scrim"></div>
 <div class="pro-stance">
  <div class="eyebrow">Overall stance &middot; updated <span id="upd"></span></div>
  <div class="pro-score"><div class="n" id="score">-</div><span class="pro-band" id="band">-</span></div>
  <p id="stance"></p>
 </div>
 <div class="pro-markets" id="markets"></div>
 <div class="pro-heronav" id="heronav"></div>
</div>
<div class="pro-grid" id="regions"></div>
<div class="pro-row">
 <div class="panel"><div class="eyebrow">Latest alerts</div><div id="alerts"></div></div>
 <div class="panel"><div class="eyebrow">What this means for your iron condor</div><div id="play"></div></div>
 <div class="panel"><div class="eyebrow">Conflict headlines</div><div class="news" id="news"></div></div>
</div>
`;

const $=s=>document.querySelector(s);
const BAND={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e'};
const PLAY={NORMAL:['Trade your usual iron condor rules.','Standard lot size','Usual wing width and strike distance','No extra hedge from this indicator'],
CAUTION:['Reduce aggression; avoid very tight strikes.','Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Watch the radar before adding overnight risk'],
HIGH:['Cut size, widen wings, avoid overnight short-option risk.','Cut lot size','Widen wings / move short strikes further out','Prefer closing shorts before the close'],
AVOID:['Stand aside from new short-premium positions.','No new short options','Close or hedge open short-premium risk','Re-enter only when the band drops']};
const ago=t=>{if(!t)return'-';const s=(Date.now()-new Date(t))/1e3;if(s<60)return'just now';if(s<3600)return Math.floor(s/60)+' min ago';if(s<86400)return Math.floor(s/3600)+' h ago';return Math.floor(s/86400)+' d ago'};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const spark=(vals,c)=>{if(!vals||vals.length<2)return'';const w=260,h=44,mn=Math.min(...vals),mx=Math.max(...vals),rg=mx-mn||1;
 const pts=vals.map((v,i)=>[i/(vals.length-1)*w,h-6-((v-mn)/rg)*(h-12)]);
 const d='M'+pts.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' L');
 return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:44px"><path d="${d}" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" opacity=".9"/></svg>`};
async function main(){
 const o=await(await fetch('/api/overview')).json();
 const band=o.overall, bc=BAND[band]||'#5eead4';
 document.documentElement.style.setProperty('--bandc',bc);
 $('#score').innerHTML=`${o.max_score}<small> / 100</small>`;
 const bd=$('#band');bd.textContent=band;bd.style.background=bc;bd.style.boxShadow=`0 0 24px ${bc}88`;
 $('#upd').textContent=ago(o.now);
 const pl=PLAY[band]||PLAY.NORMAL;
 $('#stance').textContent=pl[0];
 $('#play').innerHTML=pl.slice(1).map((x,i)=>`<div class="play"><b>${i+1}</b><span>${x}</span></div>`).join('')+`<p class="empty" style="padding:12px 2px 0">Volatility and gap-risk indicator only. It does not predict direction.</p>`;
 const mk=(n,m)=>{if(!m)return `<div class="glass"><div class="eyebrow">${n}</div><div class="v">-</div><div class="s">waiting for first reading</div></div>`;
  const up=m.pct>=0;return `<div class="glass"><div class="eyebrow">${n}</div><div class="v">${Number(m.last).toFixed(2)}</div><div class="d ${up?'up':'dn'}" style="${up?'color:var(--high)':'color:var(--normal)'}">${up?'+':''}${Number(m.pct).toFixed(2)}% vs prev close</div><div class="s">${m.stale?'Market closed, last session value':'Live'} &middot; ${esc(m.symbol)} &middot; ${ago(m.bar_time)}</div></div>`};
 $('#markets').innerHTML=mk('Brent crude',o.market.brent)+mk('India VIX',o.market.india_vix);
 const feeds=(o.feeds||[]);
 const ok=feeds.filter(f=>f.ok).length;
 $('#ticker').innerHTML=`<div class="tick"><span class="live-dot"></span>LIVE &middot; <b>${ok}/${feeds.length}</b> feeds</div>`
  +feeds.map(f=>`<div class="tick"><span class="live-dot ${f.ok?'':'bad'}"></span>${esc(f.feed)}</div>`).join('')
  +`<div class="tick"><b>${new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})}</b> IST</div>`;
 const icons=[['Live map','#/map','#5eead4'],['Strike Guard','#/strike','#f5b544'],['Scenario Lab','#/scenario','#a78bfa'],['Backtest','#/backtest','#3ddc97'],['Gap risk','#/gaps','#ff7a45'],['Feed health','#/feeds','#8592b6']];
 $('#heronav').innerHTML=icons.map(([n,h,c])=>`<a class="hnav" href="${h}"><i style="--c:${c}"></i>${n}</a>`).join('');
 $('#regions').innerHTML=o.regions.map(r=>{const c=BAND[r.label]||'#5eead4';
  return `<a class="pro-rc" style="--c:${c}" href="#/region/${r.region}"><div class="top"><h3>${esc(r.name)}</h3><span class="pro-badge">${r.label}</span></div>
  <div class="sc">${r.score}<small> / 100 &middot; x${r.multiplier}</small></div>${spark(r.spark,c)}
  <div class="pro-chips">${r.active_signals.length?r.active_signals.map(a=>`<span class="chip"><b>${esc(a.type.replace(/_/g,' '))}</b> ${a.score}</span>`).join(''):'<span class="chip">No active signals</span>'}</div>
  <div class="pro-counts"><div>${r.live_counts.gps_aircraft}<span>GPS degraded</span></div><div>${r.live_counts.military_aircraft}<span>Military</span></div><div>${r.live_counts.news_articles}<span>News</span></div><div>${o.ais_enabled?r.live_counts.ais_anomalies:'-'}<span>AIS</span></div></div></a>`}).join('');
 $('#alerts').innerHTML=o.alerts.length?o.alerts.map(a=>{const c=BAND[a.label]||'#5eead4';
  return `<div class="al"><div class="b" style="--c:${c};background:${c}"></div><div><h4>${esc(a.message||'').slice(0,90)||a.label+' &middot; '+a.region}</h4><p>${a.label} &middot; score ${a.score} &middot; ${ago(a.sent_at)}</p></div></div>`}).join('')
  :'<div class="empty">No alerts yet. An alert needs two independent signal types in one region, so a quiet period is expected behaviour.</div>';
 $('#news').innerHTML=o.headlines.slice(0,7).map(h=>`<a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}<span>${esc(h.domain||'')} &middot; ${esc(h.region)} &middot; ${ago(h.time)}</span></a>`).join('')||'<div class="empty">No headlines yet.</div>';
 // map
 const map=L.map('promap',{zoomControl:false,attributionControl:false,zoomSnap:.25}).setView([24,58],4.5);L.control.zoom({position:'bottomright'}).addTo(map);
 L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:9,className:'tiles-dark'}).addTo(map);
 try{const mp=await(await fetch('/api/map?hours=6')).json();
  for(const[k,b]of Object.entries(mp.regions)){L.rectangle([[b[0],b[2]],[b[1],b[3]]],{color:'#5eead4',weight:1,opacity:.35,fillOpacity:.03,dashArray:'5 5'}).addTo(map)}
  const seen={};
  for(const p of mp.points){const key=p.type+p.lat.toFixed(2)+p.lon.toFixed(2);if(seen[key])continue;seen[key]=1;
   const c=p.type==='gps_jamming'?'#f5b544':p.type==='military_aircraft'?'#ff7a45':'#ff4d5e';
   L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',html:`<div class="mrk" style="--c:${c};width:9px;height:9px"><i></i><em></em></div>`,iconSize:[9,9]})}).addTo(map).bindTooltip(p.label||p.type)}
 }catch(e){}
}
main();

};
routes.region=async (v,ARG)=>{
v.innerHTML=`
<h1 class="pro-title" id="name">Region</h1>
<p class="pro-sub" id="sub"></p>
<div class="g2">
 <div class="panel" id="riskpanel"><div class="eyebrow">Risk now</div>
  <div class="stance" style="margin-top:16px"><div class="gauge" id="gauge"></div><div id="play"></div></div></div>
 <div class="panel"><div class="eyebrow">Active signals explained</div><div id="sigs" style="margin-top:6px"></div></div>
</div>
<div class="panel" style="margin-bottom:20px"><div class="eyebrow">Risk score, stored history</div><div id="chart" style="margin-top:10px"></div></div>
<div class="g2">
 <div class="panel"><div class="eyebrow">Signal history</div><div id="shist" style="margin-top:6px"></div></div>
 <div class="panel"><div class="eyebrow">Latest headlines</div><div class="news" id="news" style="margin-top:6px"></div></div>
</div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 const rg=ARG||'hormuz';
 const d=await api('/api/region/'+rg);
 const c=d.current,lab=c?c.label:'NORMAL',sc=c?c.score:0;
 document.title=d.name+' - Geo-Macro Risk Agent';
 $('#name').textContent=d.name;
 $('#sub').textContent=d.why+' · region multiplier x'+d.multiplier+' · box '+d.bbox.join(', ');
 $('#riskpanel').style.background='radial-gradient(560px 320px at 18% 0%, color-mix(in srgb,'+colr(lab)+' 30%, transparent) 0%, transparent 72%), linear-gradient(165deg,rgba(21,29,56,.78),rgba(10,14,30,.9))';
 document.body.style.setProperty('--bandc',colr(lab));
 $('#gauge').innerHTML=ringSVG(sc,lab,170)+'<div class="n"><div>'+sc+'<small>OUT OF 100</small></div></div>';
 $('#play').innerHTML='<div class="big2" style="color:'+colr(lab)+'">'+PLAY[lab].t+'</div><p class="lead" style="margin-top:8px">'+PLAY[lab].a+'</p>'+badge(lab);
 $('#sigs').innerHTML=c&&c.active_signals.length?c.active_signals.map(a=>'<div class="step"><i>'+a.score+'</i><div><b>'+(SIG[a.type]||a.type)+'</b><div>'+esc(a.evidence)+'</div></div></div>').join(''):'<div class="empty">No active signals in this zone right now.</div>';
 $('#chart').innerHTML=chartSVG(d.history);
 $('#shist').innerHTML=d.signals&&d.signals.length?'<table class="tbl"><tr><th>When</th><th>Signal</th><th>Score</th></tr>'+d.signals.slice(0,12).map(g=>'<tr><td>'+ago(g.t)+'</td><td>'+(SIG[g.type]||g.type)+'<div style="color:var(--mute);font-size:11.5px">'+esc(g.reason||'')+'</div></td><td class="n">'+g.score+'</td></tr>').join('')+'</table>':'<div class="empty">No signals recorded yet</div>';
 $('#news').innerHTML=d.news&&d.news.length?d.news.slice(0,8).map(h=>'<a href="'+esc(h.url)+'" target="_blank" rel="noopener">'+esc(h.title)+'<span>'+esc(h.domain)+' · '+ago(h.t)+'</span></a>').join(''):'<div class="empty">No conflict-coded news in the stored window</div>';
}
main();


};
routes.scenario=async v=>{
v.innerHTML=`
<h1 class="pro-title">Scenario Lab</h1>
<p class="pro-sub">Stress the radar with a hypothetical shock and see how the live engine would react. Your real current signals stay in place underneath.</p>
<div class="g2" style="align-items:start">
 <div class="panel"><div class="eyebrow">1 · Pick a scenario</div><div class="pro-chips" id="presets" style="margin:12px 0 20px"></div>
  <div class="eyebrow">2 · Or build your own</div>
  <div style="margin:10px 0"><select id="sr" class="pinp"></select></div>
  <div id="siglist"></div>
  <div style="margin-top:18px"><div class="eyebrow">India VIX shock: <b id="vl" style="color:var(--ink)">+0</b> points</div><input type="range" id="vs" class="rng" min="0" max="20" step="1" value="0" style="margin-top:10px"></div>
  <button class="pbtn" id="run" style="margin-top:20px;width:100%">Run scenario</button></div>
 <div id="res"><div class="panel"><div class="empty">Choose a scenario on the left. Results appear here.</div></div></div>
</div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 const P=await api('/api/scenario/presets'),S=await api('/api/settings');const W=S.weights;let cur=null;
 const nm=t=>SIG[t]||t;
 $('#presets').innerHTML=Object.entries(P).map(([k,p])=>'<button class="chip" data-p="'+k+'">'+esc(p.name)+'</button>').join('');
 $('#sr').innerHTML=Object.keys(RN).slice(0,3).map(k=>'<option value="'+k+'">'+RN[k]+'</option>').join('');
 $('#siglist').innerHTML=Object.keys(W).map(t=>'<label class="tg"><span>'+esc(nm(t))+' <small>'+W[t]+' pts</small></span><input type="checkbox" data-t="'+t+'"></label>').join('');
 function setP(k){const p=P[k];$('#sr').value=p.region;$$('[data-t]').forEach(c=>c.checked=p.signals.includes(c.dataset.t));$('#vs').value=p.vix_pts;$('#vl').textContent='+'+p.vix_pts;$$('#presets .chip').forEach(c=>c.classList.toggle('on',c.dataset.p===k));cur=k}
 async function run(){const sig=$$('[data-t]').filter(c=>c.checked).map(c=>c.dataset.t);if(!sig.length)return;
  const r=await fetch('/api/scenario',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({region:$('#sr').value,signals:sig,vix_pts:+$('#vs').value})});const j=await r.json();if(!r.ok)return;
  const B=j.before,A=j.after,st=j.strikes,story=cur&&P[cur]?P[cur].story:'Custom scenario.';
  const why=A.alert_candidate?'Two or more independent signal types, including at least one physical or news signal, would be active. The engine <b>would send an alert</b>.':A.signal_types.length?'Not enough independent evidence. The engine <b>would not alert</b>: '+(A.signal_types.length<2?'only one signal type':'market signals only count when a physical or news signal is also present')+'.':'Market-only signals do not score on their own, so the engine stays at zero.';
  $('#res').innerHTML='<div class="panel"><div class="eyebrow">'+(cur&&P[cur]?esc(P[cur].name):esc(j.region_name)+' · custom scenario')+'</div><p class="lead" style="margin:8px 0 14px">'+esc(story)+'</p>'
  +'<div class="cmp"><div><div class="eyebrow">Now (live)</div><div class="n" style="color:'+colr(B.label)+'">'+B.score+'</div>'+badge(B.label)+'</div><div class="arrow">&rarr;</div><div><div class="eyebrow">Scenario</div><div class="n" style="color:'+colr(A.label)+'">'+A.score+'</div>'+badge(A.label)+'</div></div>'
  +'<p style="margin-top:16px;font-size:13.5px">'+why+'</p></div>'
  +'<div class="panel" style="margin-top:18px"><div class="eyebrow">Where the points come from (&times; '+A.multiplier+' regional multiplier)</div><div style="margin-top:12px">'
  +(Object.entries(A.contributions).map(([t,x])=>'<div class="cb"><span>'+esc(nm(t))+(j.added.includes(t)?' (hypothetical)':' (live)')+'</span><i style="width:'+Math.min(100,x*2.4)+'%;'+(j.added.includes(t)?'':'background:#8592b6;box-shadow:none')+'"></i><b>'+x+'</b></div>').join('')||'<div class="empty">No scoring signals.</div>')+'</div></div>'
  +(st?'<div class="panel" style="margin-top:18px"><div class="eyebrow">What it means for a NIFTY 7-day iron condor (spot '+st.spot.toLocaleString('en-IN')+')</div><div class="g2" style="margin:14px 0 0"><div class="sg-leg"><small>Now · '+st.now.label+' · '+st.now.k+'&sigma; · VIX '+st.now.vix+'</small><b>'+st.now.short_put+' / '+st.now.short_call+'</b><i>short put / short call</i></div><div class="sg-leg"><small>Scenario · '+st.scenario.label+' · '+st.scenario.k+'&sigma; · VIX '+st.scenario.vix+'</small><b style="color:'+colr(st.scenario.label)+'">'+st.scenario.short_put+' / '+st.scenario.short_call+'</b><i>'+(st.scenario.short_call-st.scenario.short_put-(st.now.short_call-st.now.short_put)>=0?'+':'')+(st.scenario.short_call-st.scenario.short_put-(st.now.short_call-st.now.short_put))+' pts wider in total</i></div></div></div>':'')
  +'<p class="lead" style="font-size:12px;max-width:none;margin-top:14px">Hypothetical. Signals marked hypothetical are assumed, not observed. Scores use this deployment\'s live weights and the same scoring code as the real radar. VIX shock is an assumption you chose. Planning aid, not a forecast or advice.</p>'}
 $('#run').onclick=run;
 $$('#presets .chip').forEach(c=>c.onclick=()=>{setP(c.dataset.p);run()});
 $('#vs').oninput=e=>{$('#vl').textContent='+'+e.target.value;$$('#presets .chip').forEach(c=>c.classList.remove('on'))};
 $$('[data-t]').forEach(c=>c.onchange=()=>$$('#presets .chip').forEach(x=>x.classList.remove('on')));
 const q=new URLSearchParams(location.search).get('preset');if(q&&P[q]){setP(q);run()}
}
main();


};
routes.strike=async v=>{
v.innerHTML=`
<h1 class="pro-title">Strike Guard</h1>
<p class="pro-sub">Where to place short strikes this week once the geopolitical risk score is priced in. Built from live NIFTY spot, live India VIX and this radar's own score.</p>
<div id="body"><div class="empty">Loading live quotes...</div></div>
`;

const $=s=>document.querySelector(s);
const BAND={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e'};
const ago=t=>{if(!t)return'-';const s=(Date.now()-new Date(t))/1e3;if(s<60)return'just now';if(s<3600)return Math.floor(s/60)+' min ago';return Math.floor(s/3600)+' h ago'};
const fmt=n=>Number(n).toLocaleString('en-IN',{maximumFractionDigits:0});
let dte=7;
async function draw(){
 let d;try{d=await(await fetch('/api/strikeguard?dte='+dte)).json();if(d.detail)throw 0}catch(e){$('#body').innerHTML='<div class="panel"><div class="empty">Live NIFTY or VIX quote is unavailable right now. Nothing is estimated. Try again in a minute.</div></div>';return}
 const bc=BAND[d.band]||'#5eead4';
 $('#ticker').innerHTML=`<div class="tick"><span class="live-dot"></span>RADAR <b>${d.band}</b></div><div class="tick">VIX <b>${d.vix.toFixed(2)}</b></div><div class="tick"><b>${new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})}</b> IST</div>`;
 const B=d.baseline,A=d.adjusted;
 const lo=Math.min(A.long_put,B.long_put,d.spot)-400,hi=Math.max(A.long_call,B.long_call)+400;
 const x=p=>((p-lo)/(hi-lo)*100).toFixed(2)+'%';
 $('#body').innerHTML=`${d.quotes_live===false?`<div class="panel" style="margin-bottom:14px;border-color:rgba(255,77,94,.45)"><p style="margin:0;color:var(--avoid);font-size:13px">Yahoo is rate-limiting this server right now, so live quotes cannot refresh. These are the last real quotes it returned, fetched ${ago(d.quotes_as_of)}. Nothing is estimated.</p></div>`:''}
 <div class="sg-hero">
  <div class="sg-tile"><div class="eyebrow">NIFTY 50 spot</div><div class="v">${fmt(d.spot)}</div><div class="d">${d.spot_age_min>45?'Market closed, last print':'Live'} &middot; ${ago(d.spot_time)}</div></div>
  <div class="sg-tile"><div class="eyebrow">India VIX</div><div class="v">${d.vix.toFixed(2)}</div><div class="d">Implies &plusmn;${d.sigma_pct}% (${Math.round(d.sigma_pts)} pts) over ${dte} days</div></div>
  <div class="sg-tile"><div class="eyebrow">Radar risk now</div><div class="v" style="color:${bc};text-shadow:0 0 26px ${bc}66">${d.score}</div><div class="d">${d.band} &middot; highest zone: ${d.region_name||'-'}</div></div>
 </div>
 <div class="ladder">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px"><div class="eyebrow">Short strikes: normal vs risk-adjusted</div>
  <div class="seg">${[2,7,14,30].map(n=>`<button data-d="${n}" class="${n===dte?'on':''}">${n} days</button>`).join('')}</div></div>
  ${d.stand_aside?`<p style="color:var(--avoid);margin-top:12px;font-size:13px">Risk band is AVOID. The radar suggests standing aside from new short-premium positions. The strikes below are the widest the model would consider.</p>`:''}
  <div class="ltrack" style="--bandc:${bc}">
   <div class="zone z2" style="left:${x(A.short_put)};width:calc(${x(A.short_call)} - ${x(A.short_put)})"></div>
   <div class="zone z1" style="left:${x(A.short_call)};width:calc(${x(A.long_call)} - ${x(A.short_call)})"></div>
   <div class="zone z1" style="left:${x(A.long_put)};width:calc(${x(A.short_put)} - ${x(A.long_put)})"></div>
   <div class="lbar a" style="left:${x(B.short_put)};right:auto;width:calc(${x(B.short_call)} - ${x(B.short_put)})"><span>NORMAL ${d.multiples?d.multiples.NORMAL:''}&sigma;</span></div>
   <div class="lbar b" style="left:${x(A.short_put)};right:auto;width:calc(${x(A.short_call)} - ${x(A.short_put)})"><span>RISK-ADJUSTED ${d.adjusted.k}&sigma; &middot; ${d.band}</span><span style="margin-left:auto">${fmt(A.short_put)} &harr; ${fmt(A.short_call)}</span></div>
   <div class="spotline" style="left:${x(d.spot)}"></div>
   <div class="spotlab" style="left:${x(d.spot)}">SPOT ${fmt(d.spot)}</div>
   <div class="spotlab2" style="left:${x(d.spot)}">${d.sigma_pct}% = 1&sigma; in ${dte}d</div>
  </div>
 </div>
 <div class="legs">
  <div class="leg" style="--lc:var(--normal)"><small>Buy put (wing)</small><div class="p">${fmt(A.long_put)}</div><i>caps loss below</i></div>
  <div class="leg" style="--lc:${bc}"><small>Sell put</small><div class="p">${fmt(A.short_put)}</div><i>${A.put_dist_pct}% from spot</i></div>
  <div class="leg" style="--lc:${bc}"><small>Sell call</small><div class="p">${fmt(A.short_call)}</div><i>+${A.call_dist_pct}% from spot</i></div>
  <div class="leg" style="--lc:var(--normal)"><small>Buy call (wing)</small><div class="p">${fmt(A.long_call)}</div><i>caps loss above</i></div>
 </div>
 <div class="ladder"><div class="eyebrow">Overnight gap test</div><p style="color:var(--mute);font-size:12.5px;margin:8px 0 12px">Drag to see where a gap would land against your strikes.</p><input type="range" id="gs" class="rng" min="-6" max="6" step="0.1" value="0" style="width:100%"><div id="gr" style="margin-top:12px;font-size:13.5px"></div></div>
 <div class="note"><div class="eyebrow" style="margin-bottom:8px">How it is computed</div><ul>
  <li>Expected move = spot &times; VIX/100 &times; &radic;(days/365). Both inputs are live quotes from Yahoo Finance.</li>
  <li>Short strikes sit 1&sigma; out for the NORMAL band; the radar's band widens them (caution 1.3&sigma;, high 1.7&sigma;, avoid 2.2&sigma;), rounded to 50, wings 100 pts wide.</li>
  <li>The band comes from this radar's highest zone score. Multiples are a transparent rule, not a fitted model.</li>
  <li>Planning aid, not advice. It sizes volatility risk only - no direction call, no backtest of this rule.</li></ul></div>`;
 document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{dte=+b.dataset.d;draw()});
 const gup=g=>{const p=d.spot*(1+g/100);const gc=p>A.short_call,gp=p<A.short_put,gb=p>B.short_call||p<B.short_put;
  $('#gr').innerHTML='NIFTY at <b>'+Math.round(p).toLocaleString('en-IN')+'</b> ('+(g>0?'+':'')+g+'%): risk-adjusted strikes '+(gc||gp?'<b style="color:var(--avoid)">breached ('+(gc?'call':'put')+' side)</b>':'<b style="color:var(--normal)">hold</b>')+'; normal strikes '+(gb?'<b style="color:var(--avoid)">breached</b>':'<b style="color:var(--normal)">hold</b>')+'.'};
 const gsl=$('#gs');gsl.oninput=e=>gup(+e.target.value);gup(0);
}
draw();

};
routes.backtest=async v=>{
v.innerHTML=`
<h1 class="pro-title">Strike calibration backtest</h1>
<p class="pro-sub">How often would the strike rules used by Strike Guard have been breached in the real market? Five years of actual NIFTY and India VIX history, tested week by week.</p>
<div id="btb"><div class="empty">Loading five years of market history...</div></div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 let d;try{d=await api('/api/backtest')}catch(e){$('#btb').innerHTML='<div class="panel"><div class="empty">Historical market data is unavailable right now. Nothing is estimated. Try again in a minute.</div></div>';return}
 const mx=Math.max(...d.all.map(x=>x.touch_pct)),band=['NORMAL','CAUTION','HIGH','AVOID'];
 const o=d.all,hv=d.high_vix.stats;
 $('#btb').innerHTML='<div class="tiles3"><div class="ptile"><div class="eyebrow">Weeks tested</div><div class="v">'+d.windows+'</div><div class="d">'+d.from+' to '+d.to+'</div></div>'
 +'<div class="ptile"><div class="eyebrow">Normal-band strikes: touched in a week</div><div class="v" style="color:var(--avoid)">'+o[0].touch_pct+'%</div><div class="d">closed beyond them: '+o[0].close_pct+'%</div></div>'
 +'<div class="ptile"><div class="eyebrow">Avoid-band strikes: touched</div><div class="v" style="color:var(--normal)">'+o[3].touch_pct+'%</div><div class="d">closed beyond them: '+o[3].close_pct+'%</div></div></div>'
 +'<div class="panel" style="margin-bottom:20px"><div class="eyebrow">Share of weeks a short strike was breached, by distance</div>'
 +'<div class="bt" style="margin-top:36px">'+o.map((x,i)=>'<div class="g"><div class="b" style="height:'+(x.touch_pct/mx*100)+'%;background:var(--accent)"><em>'+x.touch_pct+'%</em></div><div class="b" style="height:'+(x.close_pct/mx*100)+'%;background:#3d4a6e"><em>'+x.close_pct+'%</em></div></div>').join('')+'</div>'
 +'<div class="btl">'+o.map((x,i)=>'<div>'+x.k+'&sigma;<br>'+band[i].toLowerCase()+' band rule</div>').join('')+'</div>'
 +'<div class="legend"><span><i style="background:var(--accent)"></i>Touched at any point in the week (high or low)</span><span><i style="background:#3d4a6e"></i>Closed beyond the strike at expiry</span></div></div>'
 +'<div class="g2"><div class="panel"><div class="eyebrow">Counts</div><table class="tbl" style="margin-top:8px"><tr><th>Strike distance</th><th>Touched</th><th>Closed beyond</th></tr>'+o.map(x=>'<tr><td>'+x.k+'&sigma;</td><td>'+x.touch_breach+' of '+x.n+' ('+x.touch_pct+'%)</td><td>'+x.close_breach+' of '+x.n+' ('+x.close_pct+'%)</td></tr>').join('')+'</table>'
 +'<div class="eyebrow" style="margin-top:24px">Only when VIX was high ('+d.high_vix.threshold+'+, top third, '+d.high_vix.n+' weeks)</div><table class="tbl" style="margin-top:8px"><tr><th>Strike distance</th><th>Touched</th><th>Closed beyond</th></tr>'+hv.map(x=>'<tr><td>'+x.k+'&sigma;</td><td>'+x.touch_pct+'%</td><td>'+x.close_pct+'%</td></tr>').join('')+'</table></div>'
 +'<div class="panel"><div class="eyebrow">Largest weekly moves against the VIX-implied range</div><table class="tbl" style="margin-top:8px"><tr><th>Week</th><th>VIX</th><th>NIFTY move</th><th>Size vs range</th></tr>'+d.worst.map(x=>'<tr><td>'+x.start+' to '+x.end+'</td><td>'+x.vix+'</td><td>'+(x.move_pct>0?'+':'')+x.move_pct+'%</td><td>'+x.multiple+'&sigma;</td></tr>').join('')+'</table></div></div>'
 +'<div class="panel"><div class="eyebrow">Reading this honestly</div><ul style="margin:10px 0 0 18px;color:var(--mute);line-height:1.8;font-size:13.5px"><li>Each test week starts from that day\'s real NIFTY close and India VIX close, sets a 1&sigma; range = spot &times; VIX/100 &times; &radic;(7/365), and checks the next '+d.hold_days+' trading days of real highs, lows and closes. Windows do not overlap.</li><li>Widening to 1.3&sigma;, 1.7&sigma; and 2.2&sigma; lowers the breach rate every time, which is what the Strike Guard rule relies on. The cost is less premium collected, which this page does not model.</li><li>This tests the strike distances and the VIX range only. The geopolitical risk score has no multi-year history yet, so it is not backtested here and no claim is made that the radar predicted any of these weeks.</li><li>Past breach rates are not a forecast. Source: '+esc(d.source)+'.</li></ul></div>';
}
main();


};
routes.gaps=async v=>{
v.innerHTML=`
<h1 class="pro-title">Overnight gap risk</h1>
<p class="pro-sub">Iron condors cannot be adjusted while the market is shut. This page measures how far NIFTY really opened away from the previous close, over five years of actual daily data.</p>
<div id="gpb"><div class="empty">Loading five years of market history...</div></div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 let d;try{d=await api('/api/gaps')}catch(e){$('#gpb').innerHTML='<div class="panel"><div class="empty">Historical market data is unavailable right now. Nothing is estimated. Try again in a minute.</div></div>';return}
 const mx=Math.max(...d.hist.map(x=>x.n)),lab=h=>(h.lo<=-9?'below '+h.hi:h.hi>=9?'above '+h.lo:h.lo+' to '+h.hi)+'%',vs=d.vix_split,p=d.abs_percentiles;
 $('#gpb').innerHTML='<div class="tiles3"><div class="ptile"><div class="eyebrow">Trading days measured</div><div class="v">'+d.days+'</div><div class="d">'+d.from+' to '+d.to+'</div></div>'
 +'<div class="ptile"><div class="eyebrow">Typical gap (median)</div><div class="v">'+p.p50+'%</div><div class="d">9 in 10 days are under '+p.p90+'%</div></div>'
 +'<div class="ptile"><div class="eyebrow">Gap bigger than 1%</div><div class="v" style="color:var(--avoid)">'+d.exceed[1].share+'%</div><div class="d">'+d.exceed[1].n+' of '+d.days+' opens. 1 in 100 days exceeds '+p.p99+'%</div></div></div>'
 +'<div class="panel" style="margin-bottom:20px"><div class="eyebrow">Distribution of overnight gaps (open vs previous close)</div>'
 +'<div class="bt" style="margin-top:36px">'+d.hist.map(x=>'<div class="g"><div class="b" style="height:'+Math.max(2,x.n/mx*100)+'%;background:'+(x.lo>=-0.5&&x.hi<=0.5?'#3d4a6e':'var(--accent)')+'"><em>'+x.n+'</em></div></div>').join('')+'</div>'
 +'<div class="btl">'+d.hist.map(x=>'<div>'+lab(x)+'</div>').join('')+'</div></div>'
 +'<div class="g2"><div class="panel"><div class="eyebrow">How often gaps exceed a size</div><table class="tbl" style="margin-top:8px"><tr><th>Gap size</th><th>Days</th><th>Share of days</th></tr>'+d.exceed.map(x=>'<tr><td>over '+x.pct+'%</td><td>'+x.n+'</td><td>'+x.share+'%</td></tr>').join('')+'</table>'
 +'<div class="eyebrow" style="margin-top:24px">Gaps after a high-VIX vs low-VIX day (split at '+vs.threshold+')</div><table class="tbl" style="margin-top:8px"><tr><th>Previous-day VIX</th><th>Days</th><th>Avg gap</th><th>Gap over 1%</th></tr><tr><td>'+vs.threshold+'+ (high)</td><td>'+vs.high.n+'</td><td>'+vs.high.avg_pct+'%</td><td>'+vs.high.over1_pct+'%</td></tr><tr><td>below '+vs.threshold+'</td><td>'+vs.low.n+'</td><td>'+vs.low.avg_pct+'%</td><td>'+vs.low.over1_pct+'%</td></tr></table>'
 +'<div class="eyebrow" style="margin-top:24px">By weekday (Monday includes the weekend)</div><table class="tbl" style="margin-top:8px"><tr><th>Day</th><th>Avg gap</th><th>Gaps over 1%</th></tr>'+d.by_weekday.map(x=>'<tr><td>'+x.day+'</td><td>'+x.avg_pct+'%</td><td>'+x.over1+'</td></tr>').join('')+'</table></div>'
 +'<div class="panel"><div class="eyebrow">Eight largest overnight gaps</div><table class="tbl" style="margin-top:8px"><tr><th>Date</th><th>Gap</th><th>VIX previous day</th></tr>'+d.worst.map(x=>'<tr><td>'+x.date+'</td><td>'+(x.gap_pct>0?'+':'')+x.gap_pct+'%</td><td>'+(x.vix_prev==null?'-':x.vix_prev)+'</td></tr>').join('')+'</table></div></div>'
 +'<div class="panel"><div class="eyebrow">Reading this honestly</div><ul style="margin:10px 0 0 18px;color:var(--mute);line-height:1.8;font-size:13.5px"><li>Gap = that day\'s real NIFTY open divided by the previous trading day\'s close, minus 1. Holidays and weekends are included in the gap, so Monday is a longer interval.</li><li>This is history, not a forecast. The geopolitical risk score is not shown here because it has no multi-year history.</li><li>Source: '+esc(d.source)+'.</li></ul></div>';
}
main();


};
routes.signals=async v=>{
v.innerHTML=`
<h1 class="pro-title">Signals explorer</h1>
<p class="pro-sub">Every signal the extractors produced, newest first.</p>
<div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap"><select id="fr" class="pinp"><option value="">All regions</option></select><select id="ft" class="pinp"><option value="">All types</option></select><select id="fh" class="pinp"><option value="24">24 h</option><option value="48" selected>48 h</option><option value="168">7 days</option></select></div>
<div class="panel" id="tbl"></div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 $('#fr').innerHTML='<option value="">All regions</option>'+Object.keys(RN).slice(0,3).map(k=>'<option value="'+k+'">'+RN[k]+'</option>').join('');
 $('#ft').innerHTML='<option value="">All types</option>'+Object.entries(SIG).map(([k,x])=>'<option value="'+k+'">'+x+'</option>').join('');
 const load=async()=>{const q=new URLSearchParams({hours:$('#fh').value});if($('#fr').value)q.set('region',$('#fr').value);if($('#ft').value)q.set('type',$('#ft').value);const d=await api('/api/signals?'+q);
  $('#tbl').innerHTML=d.length?'<table class="tbl"><tr><th>When</th><th>Region</th><th>Signal</th><th>Score</th><th>Evidence</th></tr>'+d.map(g=>'<tr><td>'+when(g.t)+'</td><td>'+esc(RN[g.region]||g.region)+'</td><td>'+(SIG[g.type]||g.type)+'</td><td class="n">'+g.score+'</td><td style="color:var(--mute)">'+esc((g.evidence&&g.evidence.reason)||'')+'</td></tr>').join('')+'</table>':'<div class="empty">No signals in this window. Signals only appear when a rule threshold is met.</div>'};
 ['fr','ft','fh'].forEach(i=>$('#'+i).onchange=load);load();
}
main();


};
routes.alerts=async v=>{
v.innerHTML=`
<h1 class="pro-title">Alerts</h1>
<p class="pro-sub">Every alert the agent sent, with the evidence behind it.</p>
<div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;align-items:center"><select id="fl" class="pinp"><option value="">All bands</option><option>CAUTION</option><option>HIGH</option><option>AVOID</option></select><a class="pbtn ghost" href="/alerts.csv">Export CSV</a></div>
<div class="panel" id="tbl"></div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 const load=async()=>{const d=await api('/api/alerts'+($('#fl').value?'?label='+$('#fl').value:''));
  $('#tbl').innerHTML=d.length?'<table class="tbl"><tr><th>When</th><th>Region</th><th>Band</th><th>Score</th><th>Status</th><th>Type</th></tr>'+d.map(a=>'<tr style="cursor:pointer" onclick="openAlert(\''+a.id+'\')"><td>'+when(a.t)+'</td><td>'+esc(RN[a.region]||a.region)+'</td><td>'+badge(a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label)+'</td><td class="n">'+(a.kind==='system_warning'?'-':a.score)+'</td><td>'+a.status+'</td><td>'+(a.kind==='system_warning'?'system warning · feed stale':a.kind)+(a.escalation?' · escalation':'')+'</td></tr>').join('')+'</table>':'<div class="empty">No alerts yet. An alert needs two independent signal types in one region; quiet is the normal state.</div>'};
 $('#fl').onchange=load;load();
}
main();


};
routes.replay=async v=>{
v.innerHTML=`
<h1 class="pro-title">Risk replay</h1>
<p class="pro-sub">Scrub through stored risk snapshots to see what the radar showed at any past moment.</p>
<div class="panel" style="margin-bottom:20px"><input type="range" id="rs" class="rng" min="0" value="0" style="width:100%"><div class="eyebrow" id="rt" style="margin:12px 0"></div><div class="tiles3" id="rg" style="margin:0"></div></div>
<div class="panel"><div class="eyebrow">Hormuz score over the stored window</div><div id="rc" style="margin-top:10px"></div></div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 const ds=await Promise.all(Object.keys(RN).slice(0,3).map(r=>api('/api/region/'+r+'?hours=336')));
 const pts=ds[0].history;
 if(pts.length<2){$('.pro-main .pro-wrap').insertAdjacentHTML('beforeend','');document.querySelector('#rs').closest('.panel').innerHTML='<div class="empty">Replay needs stored history. It starts filling as soon as the agent has run for a few cycles.</div>';return}
 const rs=$('#rs');rs.max=pts.length-1;rs.value=pts.length-1;
 const at=i=>{const t=+new Date(pts[i].t);$('#rt').textContent=new Date(pts[i].t).toLocaleString();
  $('#rg').innerHTML=ds.map(d=>{let best=d.history[0];for(const p of d.history)if(Math.abs(new Date(p.t)-t)<Math.abs(new Date(best.t)-t))best=p;
   return '<div class="ptile"><div class="eyebrow">'+esc(d.name)+'</div><div class="v" style="-webkit-text-fill-color:'+colr(best.label)+'">'+best.score+'</div><div class="d">'+best.label+'</div></div>'}).join('');
  $('#rc').innerHTML=chartSVG(pts,pts[i].t)};
 rs.oninput=e=>at(+e.target.value);at(pts.length-1);
}
main();


};
routes.news=async v=>{
v.innerHTML=`
<h1 class="pro-title">Conflict news</h1>
<p class="pro-sub">GDELT articles and geocoded events mapped to the three zones.</p>
<div style="display:flex;gap:10px;margin-bottom:18px"><select id="fr" class="pinp"><option value="">All regions</option></select></div>
<div class="panel news" id="nl"></div>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 $('#fr').innerHTML='<option value="">All regions</option>'+Object.keys(RN).slice(0,3).map(k=>'<option value="'+k+'">'+RN[k]+'</option>').join('');
 const load=async()=>{const d=await api('/api/news'+($('#fr').value?'?region='+$('#fr').value:''));
  $('#nl').innerHTML=d.length?d.map(h=>'<a href="'+esc(h.url)+'" target="_blank" rel="noopener">'+esc(h.title)+'<span>'+esc(h.domain)+' · '+esc(RN[h.region]||h.region)+' · '+ago(h.t)+' · '+esc(h.feed||'')+'</span></a>').join(''):'<div class="empty">Nothing in the last 12 hours</div>'};
 $('#fr').onchange=load;load();
}
main();


};
routes.briefing=async v=>{
v.innerHTML=`
<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap">
 <div><h1 class="pro-title">Daily briefing</h1><p class="pro-sub" id="dateline" style="margin-bottom:20px"></p></div>
 <button class="pbtn ghost" onclick="window.print()">Save as PDF</button>
</div>
<div class="panel" style="margin-bottom:20px"><div class="eyebrow">Overall stance</div><div class="big2" id="stance" style="margin:10px 0 6px"></div><p class="lead" id="stancea"></p><div id="stanced"></div></div>
<div class="tiles3" id="regions"></div>
<div class="g2"><div class="panel"><div class="eyebrow">Market</div><div class="g2" id="market" style="margin:12px 0 0"></div></div>
<div class="panel"><div class="eyebrow">Alerts in the last stored window</div><div id="alerts"></div></div></div>
<p class="lead" style="font-size:12px;max-width:none;margin-top:6px">Volatility and gap-risk indicator for NIFTY option sellers. It does not predict direction. GPS degradation is a proxy for interference, not confirmed jamming; counts reflect what public feeds show.</p>
`;


const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=t=>{if(!t)return'never';const s=Math.round((Date.now()-new Date(t))/1000);return s<45?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>new Date(t).toLocaleString([], {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const BANDC={NORMAL:'#3ddc97',CAUTION:'#f5b544',HIGH:'#ff7a45',AVOID:'#ff4d5e',MORNING:'#5eead4',SYSTEM:'#a78bfa'};
const colr=l=>BANDC[l]||'#8592b6';
const SIG={gps_jamming_cluster:'GPS degradation cluster',military_spike:'Military aircraft spike',tanker_dark_gap:'Tanker AIS anomaly',conflict_news_spike:'Conflict news velocity',crude_confirmation:'Crude confirmation',vix_confirmation:'India VIX confirmation'};
const RN={hormuz:'Strait of Hormuz',red_sea:'Red Sea / Gulf of Aden',india_pak:'India-Pakistan border',all:'All regions',global:'Global',system:'System'};
const PLAY={NORMAL:{t:'Normal',a:'Trade your usual iron condor rules.',d:['Standard lot size','Usual wing width and strike distance','No extra hedge needed from this indicator']},
CAUTION:{t:'Caution',a:'Reduce aggression and avoid very tight strikes.',d:['Prefer normal size only if premiums pay for the risk','Avoid short strikes close to spot','Check the signal list before holding overnight']},
HIGH:{t:'High',a:'Reduce lot size, widen the wings, avoid overnight short-option risk.',d:['Cut lot size','Widen wings / move short strikes further out','Prefer closing short options before the market closes']},
AVOID:{t:'Avoid fresh narrow IC',a:'Avoid new narrow condors and review hedge or exit rules.',d:['No fresh narrow iron condors','Review existing positions against your hedge / exit rules','Gap risk is the concern, not direction']}};
async function api(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(u+' '+r.status);return r.json()}
function badge(l){return '<span class="pro-badge" style="--c:'+colr(l)+'">'+esc(l)+'</span>'}
function ringSVG(score,label,size,w){w=w||9;const r=size/2-w-1,c=2*Math.PI*r;
 return '<svg width="'+size+'" height="'+size+'" style="transform:rotate(-90deg)"><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="rgba(120,150,255,.14)" stroke-width="'+w+'"/><circle cx="'+size/2+'" cy="'+size/2+'" r="'+r+'" fill="none" stroke="'+colr(label)+'" stroke-width="'+w+'" stroke-linecap="round" stroke-dasharray="'+c+'" stroke-dashoffset="'+(c*(1-score/100))+'" style="filter:drop-shadow(0 0 6px '+colr(label)+')"/></svg>'}
function chartSVG(points,marker){
 if(!points||points.length<2)return '<div class="empty">Not enough history yet. The chart fills in as the agent keeps running.</div>';
 const W=900,H=210,P=28,t0=+new Date(points[0].t),t1=+new Date(points[points.length-1].t)||t0+1,X=t=>P+(new Date(t)-t0)/(t1-t0||1)*(W-P-8),Y=v=>H-22-(v/100)*(H-34);
 const bands=[[0,30,'#3ddc97'],[31,55,'#f5b544'],[56,75,'#ff7a45'],[76,100,'#ff4d5e']].map(b=>'<rect x="'+P+'" y="'+Y(b[1])+'" width="'+(W-P-8)+'" height="'+(Y(b[0])-Y(b[1]))+'" fill="'+b[2]+'" opacity=".07"/>').join('');
 const d='M'+points.map(p=>X(p.t).toFixed(1)+','+Y(p.score).toFixed(1)).join('L');
 const grid=[0,30,55,75,100].map(v=>'<text x="2" y="'+(Y(v)+3)+'" fill="#8592b6" font-size="9" font-family="monospace">'+v+'</text>').join('');
 const mk=marker!=null?'<line x1="'+X(marker)+'" x2="'+X(marker)+'" y1="8" y2="'+(H-22)+'" stroke="#5eead4" stroke-dasharray="3 3"/>':'';
 const area=d+'L'+(W-8)+','+(H-22)+'L'+P+','+(H-22)+'Z';
 const grad='<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5eead4" stop-opacity=".3"/><stop offset="1" stop-color="#5eead4" stop-opacity="0"/></linearGradient></defs>';
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%">'+grad+bands+grid+'<path d="'+area+'" fill="url(#cg)" stroke="none"/><path d="'+d+'" fill="none" stroke="#5eead4" stroke-width="2" style="filter:drop-shadow(0 0 7px rgba(94,234,212,.6))"/>'+mk+'<text x="'+P+'" y="'+(H-5)+'" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[0].t)+'</text><text x="'+(W-8)+'" y="'+(H-5)+'" text-anchor="end" fill="#8592b6" font-size="10" font-family="monospace">'+when(points[points.length-1].t)+'</text></svg>'}
function alertRow(a){const l=a.kind==='morning'?'MORNING':a.kind==='system_warning'?'SYSTEM':a.label;
 return '<div class="al" style="--c:'+colr(l)+'"><div class="b"></div><div><h4>'+(a.kind==='morning'?'Morning summary':a.kind==='test'?'Test alert':a.kind==='system_warning'?'System warning - feed stale':a.label+' - '+esc(RN[a.region]||a.region))+'</h4><p>'+ago(a.sent_at||a.t)+' · score '+a.score+' · '+a.status+'</p></div></div>'}
async function ticker(){
 try{const o=await api('/api/overview');const v=o.market&&o.market.india_vix;document.body.style.setProperty('--bandc',colr(o.overall));
 $('#ticker').innerHTML='<div class="tick"><span class="live-dot"></span>RADAR <b>'+o.overall+'</b></div>'+(v?'<div class="tick">VIX <b>'+Number(v.last).toFixed(2)+'</b></div>':'')+'<div class="tick"><b>'+new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+'</b> IST</div>';}catch(e){}}




async function main(){
 ticker();
 const [o,...rs]=await Promise.all([api('/api/overview'),...Object.keys(RN).slice(0,3).map(r=>api('/api/region/'+r+'?hours=24'))]);
 const lab=o.overall;
 $('#dateline').textContent=new Date().toLocaleDateString([], {weekday:'long',day:'numeric',month:'long',year:'numeric'})+' · generated from live data at '+new Date().toLocaleTimeString();
 $('#stance').innerHTML=PLAY[lab].t+' · '+o.max_score+'/100';$('#stance').style.color=colr(lab);
 $('#stancea').textContent=PLAY[lab].a;
 $('#stanced').innerHTML=PLAY[lab].d.map(x=>'<div class="step"><i>-</i><div>'+x+'</div></div>').join('');
 $('#regions').innerHTML=rs.map(r=>{const l=r.current?r.current.label:'NORMAL';
  return '<div class="ptile"><div class="eyebrow">'+esc(r.name)+'</div><div class="v" style="-webkit-text-fill-color:'+colr(l)+'">'+(r.current?r.current.score:0)+'</div>'+badge(l)
  +'<p style="margin-top:12px;font-size:13px;color:var(--mute)">'+(r.current&&r.current.active_signals.length?r.current.active_signals.map(a=>esc(a.evidence)).join('<br>'):'No active signals.')+'</p></div>'}).join('');
 const mt=(n,m)=>{if(!m)return '<div class="ptile"><div class="eyebrow">'+n+'</div><div class="v">-</div><div class="d">waiting for first reading</div></div>';const up=m.pct>=0;
  return '<div class="ptile"><div class="eyebrow">'+n+'</div><div class="v">'+Number(m.last).toFixed(2)+'</div><div class="d" style="color:'+(up?'var(--high)':'var(--normal)')+'">'+(up?'+':'')+Number(m.pct).toFixed(2)+'% vs prev close</div><div class="d" style="margin-top:4px">'+(m.stale?'Market closed, last session value':'Live')+' · '+esc(m.symbol)+' · '+ago(m.bar_time)+'</div></div>'};
 $('#market').innerHTML=mt('Brent crude',o.market.brent)+mt('India VIX',o.market.india_vix);
 $('#alerts').innerHTML=o.alerts.length?o.alerts.slice(0,5).map(alertRow).join(''):'<div class="empty">None. No region had two independent signal types.</div>';
}
main();


};
routes.feeds=async v=>{
v.innerHTML=`
<h1 class="pro-title">Feed health</h1>
<p class="pro-sub">Every collector run is recorded. A feed showing nothing is different from a feed that is down.</p>
<div class="fgrid" id="feeds"></div>
<div class="panel" id="srcs" style="margin-top:20px"></div>`;

const $=s=>document.querySelector(s);
const ago=t=>{if(!t)return'never';const s=(Date.now()-new Date(t))/1e3;if(s<60)return'just now';if(s<3600)return Math.floor(s/60)+' min ago';if(s<86400)return Math.floor(s/3600)+' h ago';return Math.floor(s/86400)+' d ago'};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function main(){
 const o=await(await fetch('/api/overview')).json();
 const feeds=o.feeds||[];
 const ok=feeds.filter(f=>f.ok).length;
 $('#ticker').innerHTML=`<div class="tick"><span class="live-dot ${ok===feeds.length?'':'bad'}"></span><b>${ok}/${feeds.length}</b> feeds healthy</div><div class="tick"><b>${new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})}</b> IST</div>`;
 $('#feeds').innerHTML=feeds.map(f=>{const c=f.ok?'#3ddc97':'#ff4d5e';
  const rows=[['Last run',ago(f.last_run)],['Last success',ago(f.last_ok)]];
  if(f.events_last_run!==undefined)rows.push(['Events last run',f.events_last_run]);
  if(f.duration_s!=null)rows.push(['Duration',f.duration_s+' s']);
  if(f.messages!==undefined)rows.push(['Messages',f.messages]);
  if(f.last_message)rows.push(['Last message',ago(f.last_message)]);
  return `<div class="fcard" style="--fc:${c}"><div class="h"><i></i><b>${esc(f.feed)}</b><span class="st">${f.ok?'HEALTHY':'DOWN'}</span></div>
   ${rows.map(r=>`<div class="frow"><span>${r[0]}</span><b>${r[1]}</b></div>`).join('')}
   ${f.success_rate_24h!=null?`<div class="fbar"><i style="width:${f.success_rate_24h}%"></i></div><div class="frow" style="border-top:0"><span>${f.success_rate_24h}% ok in 24 h</span></div>`:''}
   ${f.error?`<div class="ferr">${esc(f.error.slice(0,220))}</div>`:''}</div>`}).join('');
 $('#srcs').innerHTML='<div class="eyebrow">Sources</div><div class="kv" style="margin-top:12px"><b>Aircraft, GPS accuracy, military flag</b><span>adsb.lol, fallback adsb.fi (public ADS-B)</span><b>Conflict news</b><span>GDELT DOC API, fallback GDELT 15-minute event files</span><b>Brent, India VIX</b><span>Yahoo Finance chart API, fallback NSE</span><b>Vessels</b><span>aisstream.io '+(o.ais_enabled?'(connected)':'(needs AISSTREAM_API_KEY)')+'</span></div>';
}
main();

};
routes.map=async v=>{
v.innerHTML=`
<h1 class="pro-title">Live map</h1>
<p class="pro-sub" id="liveinfo" style="margin-bottom:16px">warming up...</p>
<div id="bigmap" class="mapfull"></div>
<div class="legend"><span><i style="background:#ff4d5e"></i>Degraded GPS accuracy (proxy for interference)</span><span><i style="background:#4ea1ff"></i>Military-flagged aircraft</span><span><i style="background:#f5b544"></i>Tanker</span><span><i style="background:#6fd3c7"></i>Vessel</span></div>
<p class="lead" style="font-size:12px;margin-top:12px;max-width:none">Positions come from a server cache of public ADS-B feeds, refreshed every 15-60 s per zone, and glide between refreshes using each aircraft's reported speed and heading. A zone showing none means the feed shows none, not that none exist.</p>
`;
 ticker();
 const map=L.map('bigmap',{zoomControl:false,attributionControl:false}).setView([24,55],4);
 L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:9}).addTo(map);
 L.control.zoom({position:'bottomright'}).addTo(map);
 const layer=L.layerGroup().addTo(map);
 const plot=async()=>{layer.clearLayers();
  const m=await api('/api/map');
  for(const b of Object.values(m.regions||{}))L.rectangle([[b[0],b[2]],[b[1],b[3]]],{color:'#5eead4',weight:1,fill:false,dashArray:'4 6',opacity:.55}).addTo(layer);
  (m.points||[]).forEach(p=>{const c=p.type==='gps_jamming'?'#ff4d5e':p.type==='military_aircraft'?'#4ea1ff':p.type==='ais_dark_gap'?'#f5b544':'#8592b6';
   L.circleMarker([p.lat,p.lon],{radius:p.type==='gps_jamming'?7:5,color:c,fillColor:c,fillOpacity:.75,weight:1.5}).bindTooltip(esc(p.label||p.type)+' · '+esc(p.type.replace(/_/g,' '))).addTo(layer)});
  let live={aircraft:[],vessels:[]};try{live=await api('/api/live')}catch(e){}
  (live.aircraft||[]).forEach(a=>{const c=a.deg?'#ff4d5e':a.mil?'#4ea1ff':'#9aa0b4';
   L.circleMarker([a.lat,a.lon],{radius:a.deg||a.mil?6:4,color:c,fillColor:c,fillOpacity:.9,weight:1}).bindTooltip((a.deg?'Degraded GPS · ':a.mil?'Military flag · ':'')+esc(a.call||a.hex)).addTo(layer)});
  (live.vessels||[]).forEach(x=>{const c=x.tanker?'#f5b544':'#6fd3c7';
   L.circleMarker([x.lat,x.lon],{radius:x.tanker?5:3,color:c,fillColor:c,fillOpacity:.85,weight:1}).bindTooltip(esc(x.name||x.mmsi)+(x.tanker?' · tanker':'')).addTo(layer)});
  const nd=(live.aircraft||[]).filter(a=>a.deg).length,nm=(live.aircraft||[]).filter(a=>a.mil).length;
  const el=$('#liveinfo');if(el)el.textContent=(m.points||[]).length+' cached signal points plotted · '+nd+' aircraft with degraded GPS · '+nm+' military-flagged · '+(live.vessels||[]).length+' vessels tracked live';};
 await plot();
 setTimeout(()=>{map.invalidateSize();map.fitBounds([[10,32],[38,78]])},100);
 const iv=setInterval(()=>{if(!document.body.contains(map.getContainer())){clearInterval(iv);return}plot()},15000);
 CLEAN=()=>{clearInterval(iv);try{map.remove()}catch(e){}};
};
routes.method=async v=>{
 ticker();
 const s=await api('/api/settings');const W=s.weights,R=s.regions,sig=Object.keys(W);
 v.innerHTML=`<h1 class="pro-title">Methodology</h1><p class="pro-sub">How a score is built, with a simulator you can play with. The simulator only does arithmetic on the real weights; it does not read or change live data.</p>
 <div class="g2"><div class="panel"><div class="eyebrow">Score formula</div><p class="lead" style="margin:10px 0">Each active signal adds its weight. The sum is multiplied by the region factor and capped at 100. Crude and India VIX only count when at least one OSINT signal is active in the region, so one data family alone never raises a high alert. An alert needs two independent signal types.</p>
 <table class="tbl"><tr><th>Signal</th><th>Weight</th></tr>${sig.map(k=>`<tr><td>${SIG[k]}</td><td class="n">${W[k]}</td></tr>`).join('')}</table>
 <table class="tbl" style="margin-top:16px"><tr><th>Region</th><th>Multiplier</th></tr>${Object.values(R).map(r=>`<tr><td>${esc(r.name)}</td><td class="n">x${r.multiplier}</td></tr>`).join('')}</table></div>
 <div class="panel"><div class="eyebrow">What-if simulator</div><div style="margin:12px 0"><select id="sr" class="pinp">${Object.entries(R).map(([k,r])=>`<option value="${k}">${esc(r.name)}</option>`).join('')}</select></div>
 ${sig.map(k=>`<label class="tg"><span>${SIG[k]}</span><span><small>+${W[k]}</small> <input type="checkbox" class="sg" value="${k}"></span></label>`).join('')}
 <div class="stance" style="margin-top:18px"><div class="gauge" id="sg" style="width:130px;height:130px"></div><div><div class="big2" id="sl"></div><p class="lead" id="sa" style="font-size:13px"></p></div></div></div></div>
 <div class="panel"><div class="eyebrow">Honest limits</div><ul style="margin:10px 0 0 18px;color:var(--mute);line-height:1.8;font-size:13.5px"><li>GPS degradation (NACp) is a proxy for interference, not confirmed jamming.</li><li>The military count is what the public ADS-B feed shows. A low count means few visible aircraft, not that none are present.</li><li>AIS comes from terrestrial receivers; a vessel going quiet can be a coverage edge.</li><li>GDELT counts are conflict-coded articles, which can include commentary and repeats.</li><li>Volatility and gap-risk indicator only. No direction call, no trade execution, no backtest.</li></ul></div>`;
 const calc=()=>{const on=[...document.querySelectorAll('.sg:checked')].map(x=>x.value),osint=on.filter(k=>!k.endsWith('_confirmation')),use=osint.length?on:[];
  const sc=Math.min(100,Math.round(use.reduce((a,k)=>a+W[k],0)*R[$('#sr').value].multiplier));
  const b=s.bands,l=sc>=b.avoid[0]?'AVOID':sc>=b.high[0]?'HIGH':sc>=b.caution[0]?'CAUTION':'NORMAL';
  document.body.style.setProperty('--bandc',colr(l));
  $('#sg').innerHTML=ringSVG(sc,l,130)+`<div class="n"><div>${sc}</div></div>`;
  $('#sl').textContent=PLAY[l].t;$('#sl').style.color=colr(l);
  $('#sa').textContent=on.length&&!osint.length?'Market confirmation alone scores 0: it needs at least one OSINT signal.':PLAY[l].a};
 document.querySelectorAll('.sg,#sr').forEach(x=>x.onchange=calc);calc();
};
routes.settings=async v=>{
 ticker();
 const [s,E]=await Promise.all([api('/api/settings'),api('/api/settings/editable')]);
 const grp=f=>E.fields.filter(x=>f(x.key));
 const inp=x=>{if(x.type==='bool')return `<label style="font-size:12.5px;color:var(--mute)"><input type="checkbox" data-k="${x.key}" ${x.value?'checked':''} ${E.editing_enabled?'':'disabled'}> ${x.value?'On':'Off'}</label>`;
  if(x.type==='list3')return [0,1,2].map(i=>`<input class="snum" data-k="${x.key}" data-i="${i}" value="${x.value[i]}" inputmode="decimal" ${E.editing_enabled?'':'disabled'}>`).join('');
  return `<input class="snum" data-k="${x.key}" value="${x.value}" inputmode="decimal" ${E.editing_enabled?'':'disabled'}>`};
 const rows=fs=>fs.map(x=>`<div class="setrow"><div><b>${esc(x.label)}</b><small>default ${Array.isArray(x.default)?x.default.join(' / '):x.default}${x.min!=null&&x.type!=='list3'?` · allowed ${x.min} to ${x.max}`:''}</small></div><div class="fin">${inp(x)}</div></div>`).join('');
 const fmt=x=>Array.isArray(x)?x.join(' / '):String(x);
 v.innerHTML=`<h1 class="pro-title">Settings</h1><p class="pro-sub">Thresholds and weights that drive the score. Changes apply on the next scoring cycle and are written to the change log.</p>
 <div class="g2"><div class="panel"><div class="eyebrow">Delivery</div><div class="kv" style="margin-top:12px"><b>Telegram</b><span>${s.telegram.ready?'ready':'not connected'} (token ${s.telegram.token_set?'set':'missing'}, chat id ${s.telegram.chat_set?'set':'missing'})</span><b>LLM analyst note</b><span>${esc(s.llm_provider)}</span><b>AIS</b><span>${s.ais_enabled?'on':'off (no key)'}</span><b>Live layer</b><span>${s.live_layer?'on':'off'}, zone sweeps every ${Object.entries(s.live_tiers_s).map(([k,x])=>k+' '+x+'s').join(', ')}</span><b>Morning summary</b><span>${s.alerts.morning_summary_time_ist} IST, Mon-Fri</span><b>Retention</b><span>${s.retention_days} days</span></div><div style="margin-top:16px"><button class="pbtn ghost" id="tt">Send test alert</button> <span id="tr" style="color:var(--mute);font-size:13px;margin-left:8px"></span></div></div>
 <div class="panel"><div class="eyebrow">Admin</div><p class="lead" style="margin:12px 0">${E.editing_enabled?'Signed in as admin. Every change is logged with time, old value and new value.':'Editing is disabled because ADMIN_PASSWORD is not set on this server.'}</p><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><button class="pbtn" id="sv" ${E.editing_enabled?'':'disabled'}>Save changes</button><button class="pbtn ghost" id="rs" ${E.editing_enabled?'':'disabled'}>Reset to defaults</button><span id="sm" style="font-size:13px;color:var(--mute)"></span></div></div></div>
 <div class="g2"><div class="panel"><div class="eyebrow">Signal weights (points)</div>${rows(grp(k=>k.startsWith('weights.')))}<div class="eyebrow" style="margin-top:22px">Risk bands (score where the band starts)</div>${rows(grp(k=>k.startsWith('bands.')))}<div class="eyebrow" style="margin-top:22px">Region multipliers</div>${rows(grp(k=>k.includes('.multiplier')))}</div>
 <div class="panel"><div class="eyebrow">Detection rules</div>${rows(grp(k=>k.startsWith('rules.')))}<div class="eyebrow" style="margin-top:22px">Alerts</div>${rows(grp(k=>k.startsWith('alerts.')))}</div></div>
 <div class="panel"><div class="eyebrow">Change log</div>${E.log.length?`<table class="tbl"><tr><th>When</th><th>Who</th><th>Setting</th><th>Old</th><th>New</th></tr>${E.log.map(c=>`<tr><td>${new Date(c.t).toLocaleString()}</td><td>${esc(c.actor)}</td><td>${esc(c.label)}${c.note?' ('+esc(c.note)+')':''}</td><td>${esc(fmt(c.old))}</td><td>${esc(fmt(c.new))}</td></tr>`).join('')}</table>`:'<div class="empty">No changes yet. Everything runs on the shipped defaults.</div>'}</div>`;
 const collect=()=>{const o={};$$('[data-k]').forEach(el=>{const k=el.dataset.k;if(el.type==='checkbox'){o[k]=el.checked}else if(el.dataset.i!==undefined){(o[k]=o[k]||[])[+el.dataset.i]=el.value}else o[k]=el.value});return o};
 $('#sv').onclick=async()=>{const all=collect(),ch={};for(const x of E.fields){const n=all[x.key];const cur=x.type==='bool'?n:x.type==='list3'?n.map(Number):Number(n);if(JSON.stringify(cur)!==JSON.stringify(x.value))ch[x.key]=cur}
  if(!Object.keys(ch).length){$('#sm').textContent='Nothing changed';return}
  const r=await fetch('/api/settings',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({changes:ch})});const j=await r.json();
  if(!r.ok){$('#sm').style.color='var(--avoid)';$('#sm').textContent=j.detail||'Could not save';return}toast(j.applied.length+' setting(s) saved');routes.settings(v)};
 $('#rs').onclick=async()=>{if(!confirm('Reset every setting to the shipped defaults?'))return;const r=await fetch('/api/settings/reset',{method:'POST'});if(r.ok){toast('Reset to defaults');routes.settings(v)}};
 $('#tt').onclick=async()=>{$('#tr').textContent='sending...';const r=await fetch('/alerts/test',{method:'POST',headers:{'content-type':'application/json'},body:'{}'});$('#tr').textContent=r.ok?'sent (status: '+(await r.json()).status+')':r.status===429?'wait 30 seconds between tests':'failed'};
};