"use strict";

const state={data:null,reference:null,candidate:null,results:[],map:"all"};
const $=(selector)=>document.querySelector(selector);
const $$=(selector)=>[...document.querySelectorAll(selector)];
const format=new Intl.NumberFormat("en-GB",{maximumFractionDigits:1});
const percent=(value)=>value==null?"—":`${format.format(value*100)}%`;
const number=(value,digits=1)=>value==null?"—":Number(value).toFixed(digits);

document.addEventListener("DOMContentLoaded",init);

async function init(){
  bindNavigation(); bindControls();
  try{
    const response=await fetch("data/profiles.json");
    if(!response.ok)throw new Error(`Data request failed (${response.status})`);
    state.data=await response.json();
    populateControls();
    const salah=state.data.players.find(p=>p.player_name.includes("Salah"));
    $("#reference").value=salah?.player_season_id||state.data.players[0].player_season_id;
    setReference();
  }catch(error){
    $("#reference-name").textContent="Profiles unavailable";
    $("#reference-context").textContent=`${error.message}. Refresh to try again.`;
    toast("Could not load profile data");
  }
}

function bindNavigation(){
  $$(".nav-item").forEach(button=>button.addEventListener("click",()=>{
    $$(".nav-item").forEach(item=>item.classList.toggle("active",item===button));
    $$(".view").forEach(view=>view.classList.toggle("active",view.id===button.dataset.view));
    $("#main").focus({preventScroll:true}); window.scrollTo({top:0,behavior:"smooth"});
  }));
}

function bindControls(){
  $("#reference").addEventListener("change",setReference);
  $("#find-button").addEventListener("click",runSearch);
  $$(".weights input").forEach(input=>input.addEventListener("input",()=>document.querySelector(`output[for=${input.id}]`).value=input.value));
  $$(".map-tab").forEach(button=>button.addEventListener("click",()=>{
    $$(".map-tab").forEach(tab=>tab.classList.toggle("active",tab===button)); state.map=button.dataset.map; renderComparisonMaps();
  }));
  window.addEventListener("resize",debounce(()=>{if(state.reference)renderReference();if(state.candidate)renderComparisonMaps();},140));
}

function populateControls(){
  const reference=$("#reference");
  reference.innerHTML=state.data.players.map(p=>`<option value="${p.player_season_id}">${escapeHtml(p.player_name)} · ${escapeHtml(p.team_name)}</option>`).join("");
  const positions=[...new Set(state.data.players.map(p=>p.positions).filter(Boolean))].sort();
  $("#position").innerHTML+=[...positions].map(position=>`<option value="${escapeHtml(position)}">${escapeHtml(position)}</option>`).join("");
}

function setReference(){
  state.reference=state.data.players.find(player=>player.player_season_id===$("#reference").value);
  state.candidate=null; state.results=[];
  $("#results-section").classList.add("hidden"); $("#comparison-section").classList.add("hidden");
  renderReference();
}

function renderReference(){
  const player=state.reference;if(!player)return;
  $("#reference-name").textContent=player.player_name;
  $("#reference-context").textContent=`${player.team_name} · Premier League 2017/18 · ${player.positions||"Position unavailable"}`;
  $("#reference-monogram").textContent=initials(player.player_name);
  $("#reference-facts").innerHTML=fact("Minutes",format.format(player.minutes))+fact("Goals",player.goals)+fact("Age",number(player.age));
  drawPitch($("#reference-pitch"),player.fp.all);
  const zones=[
    ["Attacking third",player.pct_attacking_third],["Penalty area",player.pct_penalty_area],
    ["Half-spaces",player.pct_half_space],["Central",player.pct_central],["Wide",player.pct_wide],
    ["Box presence",player.box_presence_rate]
  ];
  $("#zone-grid").innerHTML=zones.map(([label,value])=>`<div class="zone-card"><strong>${percent(value)}</strong><span>${label}</span></div>`).join("");
}

function runSearch(){
  const button=$("#find-button");button.disabled=true;button.querySelector("span").textContent="Comparing profiles…";
  requestAnimationFrame(()=>setTimeout(()=>{
    const reference=state.reference;
    const minimum=Number($("#min-minutes").value)||0,ageMin=Number($("#age-min").value)||0,ageMax=Number($("#age-max").value)||99;
    const position=$("#position").value,mirrorMode=$("#mirror-mode").checked;
    const weights={spatial:+$("#w-spatial").value,goal:+$("#w-goal").value,shoot:+$("#w-shoot").value,create:+$("#w-create").value,pass:+$("#w-pass").value,defend:+$("#w-defend").value};
    const weightTotal=Object.values(weights).reduce((sum,value)=>sum+value,0)||1;
    state.results=state.data.players.filter(player=>player.player_season_id!==reference.player_season_id&&player.minutes>=minimum&&(player.age==null||(player.age>=ageMin&&player.age<=ageMax))&&(!position||player.positions===position)).map(player=>{
      const same=spatialScore(reference.fp.all,player.fp.all,false),mirrored=spatialScore(reference.fp.all,player.fp.all,true);
      const scores={same,mirrored,spatial:mirrorMode?Math.max(same,mirrored):same};
      scores.goal=categoryScore(reference,player,["goals_p90","pct_penalty_area","box_presence_rate"]);
      scores.shoot=categoryScore(reference,player,["shots_p90","goals_p90"]);
      scores.create=categoryScore(reference,player,["chance_creation_p90","assists_p90"]);
      scores.pass=categoryScore(reference,player,["passes_p90"]);
      scores.defend=categoryScore(reference,player,["defensive_actions_p90"]);
      scores.overall=Object.entries(weights).reduce((sum,[key,weight])=>sum+scores[key]*weight,0)/weightTotal;
      return {player,scores};
    }).sort((a,b)=>b.scores.overall-a.scores.overall);
    renderResults(); button.disabled=false;button.querySelector("span").textContent="Find similar players";
  },20));
}

function renderResults(){
  const section=$("#results-section");section.classList.remove("hidden");
  $("#result-summary").textContent=`${state.results.length} eligible profiles · click a row to compare`;
  $("#results-body").innerHTML=state.results.slice(0,30).map((result,index)=>`<tr tabindex="0" data-id="${result.player.player_season_id}"><td>${String(index+1).padStart(2,"0")}</td><td class="player-cell"><strong>${escapeHtml(result.player.player_name)}</strong><span>${escapeHtml(result.player.positions||"Unknown role")}</span></td><td>${escapeHtml(result.player.team_name)}</td><td>${number(result.player.age)}</td><td>${format.format(result.player.minutes)}</td><td><span class="score-pill">${number(result.scores.overall)}</span></td><td class="score">${number(result.scores.spatial)}</td><td>${number(result.scores.same)}</td><td>${number(result.scores.mirrored)}</td></tr>`).join("")||`<tr><td colspan="9">No players match these constraints. Broaden the age, position or minute filters.</td></tr>`;
  $$("#results-body tr[data-id]").forEach(row=>{
    const open=()=>openComparison(row.dataset.id);row.addEventListener("click",open);row.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();open();}});
  });
  section.scrollIntoView({behavior:"smooth",block:"start"});
}

function openComparison(id){
  const result=state.results.find(item=>item.player.player_season_id===id);if(!result)return;
  state.candidate=result;
  const reference=state.reference,candidate=result.player,scores=result.scores;
  $("#comparison-title").textContent=`${reference.player_name} vs ${candidate.player_name}`;
  $("#score-cluster").innerHTML=scoreBox("Overall",scores.overall)+scoreBox("Spatial",scores.spatial)+scoreBox("Same side",scores.same)+scoreBox("Mirrored",scores.mirrored);
  $("#explanation").textContent=explain(reference,candidate,scores);
  $("#map-a-name").textContent=reference.player_name;$("#map-b-name").textContent=candidate.player_name;
  renderComparisonMaps();renderMetricComparison();
  $("#comparison-section").classList.remove("hidden");$("#comparison-section").scrollIntoView({behavior:"smooth",block:"start"});
}

function renderComparisonMaps(){
  if(!state.candidate)return;
  const a=state.reference.fp[state.map],b=state.candidate.player.fp[state.map];
  drawPitch($("#map-a"),a);drawPitch($("#map-b"),b);drawPitch($("#map-diff"),b.map((value,index)=>value-a[index]),true);
}

function renderMetricComparison(){
  const a=state.reference,b=state.candidate.player;
  const metrics=[["Goals / 90","goals_p90",false],["Shots / 90","shots_p90",false],["Assists / 90","assists_p90",false],["Chances / 90","chance_creation_p90",false],["Passes / 90","passes_p90",false],["Defensive / 90","defensive_actions_p90",false],["Penalty area","pct_penalty_area",true],["Half-spaces","pct_half_space",true]];
  $("#metric-comparison").innerHTML=metrics.map(([label,key,isPercent])=>`<div class="metric-row"><span>${label}</span><div><i>${isPercent?percent(a[key]):number(a[key],2)}</i><b>${isPercent?percent(b[key]):number(b[key],2)}</b></div></div>`).join("");
}

function categoryScore(a,b,metrics){
  const values=metrics.map(metric=>{
    if(a[metric]==null||b[metric]==null)return null;
    const scale=state.data.meta.scales[metric],range=Math.max(scale.high-scale.low,.01);
    return (b[metric]-a[metric])/range;
  }).filter(value=>value!==null);
  if(!values.length)return 50;
  const distance=Math.sqrt(values.reduce((sum,value)=>sum+value*value,0)/values.length);
  return 100*Math.exp(-distance);
}

function spatialScore(aRaw,bRaw,mirror){
  const q=state.data.meta.quantization,a=aRaw.map(v=>v/q),grid=mirror?mirrorGrid(bRaw).map(v=>v/q):bRaw.map(v=>v/q);
  let dot=0,aa=0,bb=0,js=0;
  for(let i=0;i<a.length;i++){dot+=a[i]*grid[i];aa+=a[i]*a[i];bb+=grid[i]*grid[i];const m=(a[i]+grid[i])/2;if(a[i]>0)js+=.5*a[i]*Math.log2(a[i]/m);if(grid[i]>0)js+=.5*grid[i]*Math.log2(grid[i]/m);}
  const cosine=aa&&bb?dot/Math.sqrt(aa*bb):0,jsSimilarity=1-Math.sqrt(Math.max(0,js));
  const distance=projectedWasserstein(a,grid),transport=Math.exp(-distance/18);
  return Math.max(0,Math.min(100,100*(.5*transport+.3*cosine+.2*jsSimilarity)));
}

function projectedWasserstein(a,b){
  const [gx,gy]=state.data.meta.grid;let xDistance=0,yDistance=0,cumA=0,cumB=0;
  for(let x=0;x<gx;x++){let massA=0,massB=0;for(let y=0;y<gy;y++){massA+=a[x*gy+y];massB+=b[x*gy+y];}cumA+=massA;cumB+=massB;xDistance+=Math.abs(cumA-cumB)*(100/gx);}
  cumA=0;cumB=0;
  for(let y=0;y<gy;y++){let massA=0,massB=0;for(let x=0;x<gx;x++){massA+=a[x*gy+y];massB+=b[x*gy+y];}cumA+=massA;cumB+=massB;yDistance+=Math.abs(cumA-cumB)*(100/gy);}
  return Math.hypot(xDistance,yDistance);
}

function mirrorGrid(vector){const [gx,gy]=state.data.meta.grid,result=new Array(vector.length);for(let x=0;x<gx;x++)for(let y=0;y<gy;y++)result[x*gy+y]=vector[x*gy+(gy-1-y)];return result;}

function drawPitch(canvas,vector,difference=false){
  const dpr=Math.min(window.devicePixelRatio||1,2),rect=canvas.getBoundingClientRect(),w=Math.max(280,rect.width),h=w/1.52;canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.height=`${h}px`;
  const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);const pad=12,pw=w-pad*2,ph=h-pad*2,[gx,gy]=state.data.meta.grid,max=Math.max(...vector.map(Math.abs),1);
  ctx.fillStyle="#07150e";ctx.fillRect(0,0,w,h);
  for(let x=0;x<gx;x++)for(let y=0;y<gy;y++){const value=vector[x*gy+y],strength=Math.min(1,Math.abs(value)/max);if(!strength)continue;ctx.fillStyle=difference?(value>=0?`rgba(64,229,141,${.08+.75*strength})`:`rgba(102,163,255,${.08+.72*strength})`):heatColor(strength);ctx.fillRect(pad+x*pw/gx,pad+y*ph/gy,pw/gx+.4,ph/gy+.4);}
  ctx.strokeStyle="rgba(220,242,230,.68)";ctx.lineWidth=1;ctx.strokeRect(pad,pad,pw,ph);ctx.beginPath();ctx.moveTo(pad+pw/2,pad);ctx.lineTo(pad+pw/2,pad+ph);ctx.stroke();ctx.beginPath();ctx.arc(pad+pw/2,pad+ph/2,ph*.09,0,Math.PI*2);ctx.stroke();
  const boxW=pw*.145,boxH=ph*.57,smallW=pw*.052,smallH=ph*.27;ctx.strokeRect(pad,pad+(ph-boxH)/2,boxW,boxH);ctx.strokeRect(pad+pw-boxW,pad+(ph-boxH)/2,boxW,boxH);ctx.strokeRect(pad,pad+(ph-smallH)/2,smallW,smallH);ctx.strokeRect(pad+pw-smallW,pad+(ph-smallH)/2,smallW,smallH);
}

function heatColor(value){if(value<.35)return`rgba(22,100,58,${.25+value})`;if(value<.7)return`rgba(64,229,141,${.3+value*.7})`;return`rgba(238,255,119,${.45+value*.55})`;}
function explain(a,b,scores){const clauses=[];[["pct_half_space","half-space involvement"],["pct_penalty_area","penalty-area presence"],["pct_wide","wide activity"],["shots_p90","shot volume"],["chance_creation_p90","chance creation"]].forEach(([key,label])=>{if(a[key]==null||b[key]==null)return;const delta=b[key]-a[key],threshold=Math.max(Math.abs(a[key])*.12,key.includes("pct_")?.015:.08);clauses.push(Math.abs(delta)<threshold?`similar ${label}`:`${delta>0?"more":"less"} ${label}`);});const orientation=scores.mirrored>scores.same+5?"after mirroring the flank":"on the same-side orientation";return`${b.player_name} is closest spatially ${orientation}, with ${clauses.slice(0,4).join(", ")}. The comparison is generated from the displayed distributions and per-90 features.`;}
function fact(label,value){return`<div><strong>${value}</strong><span>${label}</span></div>`}function scoreBox(label,value){return`<div><strong>${number(value)}</strong><span>${label}</span></div>`}function initials(name){return name.split(/\s+/).slice(0,2).map(part=>part[0]).join("").toUpperCase()}function escapeHtml(value){return String(value??"").replace(/[&<>'"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char])}function debounce(fn,delay){let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay)}}function toast(message){const element=$("#toast");element.textContent=message;element.classList.add("show");setTimeout(()=>element.classList.remove("show"),3500)}
