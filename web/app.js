"use strict";

const state={reference:null,candidate:null,results:[],map:"all",grid:[12,8],lastSearch:null};
const $=(selector)=>document.querySelector(selector);
const $$=(selector)=>[...document.querySelectorAll(selector)];
const format=new Intl.NumberFormat("en-GB",{maximumFractionDigits:1});
const percent=(value)=>value==null?"—":`${format.format(value*100)}%`;
const number=(value,digits=1)=>value==null?"—":Number(value).toFixed(digits);

document.addEventListener("DOMContentLoaded",init);

async function init(){
  bindControls();
  const session=await fetchJson("/api/auth/session").catch(()=>({authenticated:false}));
  if(session.authenticated) await unlock(); else showLogin();
}

function bindControls(){
  bindNavigation();
  $("#login-form").addEventListener("submit",login);
  $("#logout-button").addEventListener("click",logout);
  $("#reference-search").addEventListener("input",debounce(searchReferences,350));
  $("#reference").addEventListener("change",setReference);
  $("#candidate-competitions").addEventListener("change",refreshCandidateSeasons);
  $("#find-button").addEventListener("click",runSearch);
  $$(".weights input").forEach(input=>input.addEventListener("input",()=>document.querySelector(`output[for=${input.id}]`).value=input.value));
  $$(".map-tab").forEach(button=>button.addEventListener("click",()=>{
    $$(".map-tab").forEach(tab=>tab.classList.toggle("active",tab===button));state.map=button.dataset.map;renderComparisonMaps();
  }));
  window.addEventListener("resize",debounce(()=>{if(state.reference)renderReference();if(state.candidate)renderComparisonMaps();},140));
}

function bindNavigation(){
  $$(".nav-item").forEach(button=>button.addEventListener("click",()=>{
    $$(".nav-item").forEach(item=>item.classList.toggle("active",item===button));
    $$(".view").forEach(view=>view.classList.toggle("active",view.id===button.dataset.view));
    window.scrollTo({top:0,behavior:"smooth"});
  }));
}

async function login(event){
  event.preventDefault();
  const button=event.currentTarget.querySelector("button");button.disabled=true;
  $("#login-error").textContent="";
  try{
    await fetchJson("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("#login-password").value})});
    $("#login-password").value="";await unlock();
  }catch(error){$("#login-error").textContent=error.message;}
  finally{button.disabled=false;}
}

async function logout(){
  await fetchJson("/api/auth/logout",{method:"POST"}).catch(()=>null);showLogin();
}

function showLogin(){
  document.body.classList.add("locked");$("#app-shell").hidden=true;$("#login-view").hidden=false;$("#login-password").focus();
}

async function unlock(){
  document.body.classList.remove("locked");$("#login-view").hidden=true;$("#app-shell").hidden=false;
  try{await Promise.all([loadCatalogue(),searchReferences()]);}
  catch(error){toast(error.message);if(error.status===401)showLogin();}
}

async function proxy(endpoint,{method="GET",body=null,query={}}={}){
  const params=new URLSearchParams({endpoint,...query});
  return fetchJson(`/api/scoutprint?${params}`,{method,headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
}

async function fetchJson(url,options={}){
  const response=await fetch(url,options);const payload=await response.json().catch(()=>({}));
  if(!response.ok){const error=new Error(payload.error||payload.detail||`Request failed (${response.status})`);error.status=response.status;throw error;}
  return payload;
}

async function loadCatalogue(){
  const [competitionPayload,seasonPayload]=await Promise.all([proxy("competitions"),proxy("seasons")]);
  const competitions=competitionPayload.competitions;
  $("#competition-count").textContent=competitions.length;
  $("#profile-count").textContent=format.format(competitions.reduce((sum,item)=>sum+item.player_seasons,0));
  $("#season-count").textContent=new Set(seasonPayload.seasons.map(item=>item.season)).size;
  $("#candidate-competitions").innerHTML=competitions.map(item=>`<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)} · ${format.format(item.player_seasons)}</option>`).join("");
  state.seasons=seasonPayload.seasons;refreshCandidateSeasons();
}

function refreshCandidateSeasons(){
  const chosen=selectedValues($("#candidate-competitions"));
  const rows=(state.seasons||[]).filter(row=>!chosen.length||chosen.includes(row.competition));
  const seasons=[...new Set(rows.map(row=>row.season))].sort().reverse();
  $("#candidate-seasons").innerHTML=seasons.map(season=>`<option value="${escapeHtml(season)}">${escapeHtml(season)}</option>`).join("");
}

async function searchReferences(){
  const name=$("#reference-search").value.trim();if(name.length<2)return;
  const payload=await proxy("players",{query:{name,limit:"100"}});
  const current=$("#reference").value;
  $("#reference").innerHTML=payload.players.map(player=>`<option value="${escapeHtml(player.player_season_id)}">${escapeHtml(player.player_name)} · ${escapeHtml(player.club||player.team_name)} · ${escapeHtml(player.competition_name)} ${escapeHtml(player.season_name)}</option>`).join("");
  if(!payload.players.length){state.reference=null;$("#reference-name").textContent="No matching player-season";return;}
  if(payload.players.some(player=>player.player_season_id===current))$("#reference").value=current;
  else{
    const salah=payload.players.find(player=>player.player_name==="Mohamed Salah"&&player.competition_name==="Premier League"&&player.season_name==="2017/18");
    $("#reference").value=(salah||payload.players[0]).player_season_id;
  }
  await setReference();
}

async function setReference(){
  const id=$("#reference").value;if(!id)return;
  const payload=await proxy(`player/${encodeURIComponent(id)}/profile`);
  state.reference=payload.profile;state.grid=payload.profile.grid;state.candidate=null;state.results=[];
  $("#results-section").classList.add("hidden");$("#comparison-section").classList.add("hidden");renderReference();
}

function renderReference(){
  const player=state.reference;if(!player)return;
  $("#reference-name").textContent=player.player_name;
  $("#reference-context").textContent=`${player.team_name||"Club unavailable"} · ${player.competition_name} ${player.season_name} · ${player.positions||"Position unavailable"}`;
  $("#reference-monogram").textContent=initials(player.player_name);
  $("#reference-facts").innerHTML=fact("Minutes",format.format(player.minutes||0))+fact("xG",number(player.statistics.xg,2))+fact("Age",number(player.age));
  drawPitch($("#reference-pitch"),player.maps.all);
  const stats=player.statistics,zones=[["Attacking third",stats.pct_attacking_third],["Penalty area",stats.pct_penalty_area],["Half-spaces",stats.pct_half_space],["Central",stats.pct_central],["Wide",stats.pct_wide],["Box presence",stats.box_presence_rate]];
  $("#zone-grid").innerHTML=zones.map(([label,value])=>`<div class="zone-card"><strong>${percent(value)}</strong><span>${label}</span></div>`).join("");
}

function searchRequest(){
  const optionalNumber=(selector)=>$(selector).value===""?null:Number($(selector).value);
  return {
    reference_player_season_id:state.reference.player_season_id,
    reference_competition:state.reference.competition_name,
    reference_season:state.reference.season_name,
    candidate_competitions:selectedValues($("#candidate-competitions")),candidate_seasons:selectedValues($("#candidate-seasons")),
    minimum_minutes:Number($("#min-minutes").value)||0,minimum_age:optionalNumber("#age-min"),maximum_age:optionalNumber("#age-max"),
    mirror_mode:$("#mirror-mode").checked,minimum_comparison_coverage:Number($("#min-coverage").value)||0,result_limit:25,
    weights:{"Spatial role":+$("#w-spatial").value,"Goal threat":+$("#w-goal").value,"Shooting":+$("#w-shoot").value,"Chance creation":+$("#w-create").value,"Carrying":+$("#w-carry").value,"Passing":+$("#w-pass").value,"Defending":+$("#w-defend").value},
  };
}

async function runSearch(){
  if(!state.reference)return;
  const button=$("#find-button");button.disabled=true;button.querySelector("span").textContent="Exact reranking…";
  try{
    state.lastSearch=searchRequest();const payload=await proxy("search/similar",{method:"POST",body:state.lastSearch});state.results=payload.results;
    $("#result-summary").textContent=`${payload.engine} · ${format.format(payload.candidate_count)} comparable profiles · ${format.format(payload.runtime_ms)} ms`;
    $("#results-body").innerHTML=state.results.map(result=>`<tr tabindex="0" data-id="${escapeHtml(result.player_season_id)}"><td>${result.rank}</td><td class="player-cell"><strong>${escapeHtml(result.player_name)}</strong><span>${escapeHtml(result.competition)} · ${escapeHtml(result.season)} · ${escapeHtml(result.position||"")}</span></td><td>${escapeHtml(result.club||"—")}</td><td>${number(result.age)}</td><td>${format.format(result.minutes||0)}</td><td><span class="score-pill">${number(result.profile_match)}</span></td><td class="score">${number(result.spatial_match)}</td><td>${number(result.same_side_match)}</td><td>${number(result.mirrored_match)}</td></tr>`).join("");
    $$("#results-body tr").forEach(row=>{row.addEventListener("click",()=>openComparison(row.dataset.id));row.addEventListener("keydown",event=>{if(event.key==="Enter")openComparison(row.dataset.id);});});
    $("#results-section").classList.remove("hidden");$("#comparison-section").classList.add("hidden");$("#results-section").scrollIntoView({behavior:"smooth"});
  }catch(error){toast(error.message);if(error.status===401)showLogin();}
  finally{button.disabled=false;button.querySelector("span").textContent="Find similar players";}
}

async function openComparison(id){
  try{
    const payload=await proxy("comparison",{method:"POST",body:{...state.lastSearch,candidate_player_season_id:id}});state.candidate=payload;
    $("#comparison-title").textContent=`${payload.reference.player_name} / ${payload.candidate.player_name}`;
    $("#score-cluster").innerHTML=scoreBox("Profile match",payload.score.profile_match)+scoreBox("Spatial",payload.score.spatial_match)+scoreBox("Coverage",payload.score.comparison_coverage);
    $("#explanation").textContent=`${payload.explanation.text} Unavailable: ${payload.score.unavailable_categories.join(", ")||"none"}.`;
    $("#map-a-name").textContent=payload.reference.player_name;$("#map-b-name").textContent=payload.candidate.player_name;
    renderComparisonMaps();renderMetricComparison();$("#comparison-section").classList.remove("hidden");$("#comparison-section").scrollIntoView({behavior:"smooth"});
  }catch(error){toast(error.message);}
}

function renderComparisonMaps(){
  if(!state.candidate)return;const a=state.candidate.reference.maps[state.map],b=state.candidate.candidate.maps[state.map];
  if(!a||!b){toast(`${state.map} map unavailable for this comparison`);return;}
  drawPitch($("#map-a"),a);drawPitch($("#map-b"),b);drawPitch($("#map-diff"),state.candidate.difference_maps[state.map],true);
}

function renderMetricComparison(){
  const a=state.candidate.reference.statistics,b=state.candidate.candidate.statistics;
  const metrics=[["xG / 90","xg_p90",false],["xA / 90","xa_p90",false],["Shots / 90","shots_p90",false],["Chances / 90","chance_creation_p90",false],["Passes / 90","passes_p90",false],["Defensive / 90","defensive_actions_p90",false],["Penalty area","pct_penalty_area",true],["Half-spaces","pct_half_space",true]];
  $("#metric-comparison").innerHTML=metrics.map(([label,key,isPercent])=>`<div class="metric-row"><span>${label}</span><div><i>${isPercent?percent(a[key]):number(a[key],2)}</i><b>${isPercent?percent(b[key]):number(b[key],2)}</b></div></div>`).join("");
}

function selectedValues(select){return [...select.selectedOptions].map(option=>option.value);}
function drawPitch(canvas,vector,difference=false){
  if(!vector)return;const dpr=Math.min(window.devicePixelRatio||1,2),rect=canvas.getBoundingClientRect(),w=Math.max(280,rect.width),h=w/1.52;canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.height=`${h}px`;
  const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);const pad=12,pw=w-pad*2,ph=h-pad*2,[gx,gy]=state.grid,max=Math.max(...vector.map(Math.abs),1e-9);ctx.fillStyle="#07150e";ctx.fillRect(0,0,w,h);
  for(let x=0;x<gx;x++)for(let y=0;y<gy;y++){const value=vector[x*gy+y],strength=Math.min(1,Math.abs(value)/max);if(!strength)continue;ctx.fillStyle=difference?(value>=0?`rgba(64,229,141,${.08+.75*strength})`:`rgba(102,163,255,${.08+.72*strength})`):heatColor(strength);ctx.fillRect(pad+x*pw/gx,pad+y*ph/gy,pw/gx+.4,ph/gy+.4);}
  ctx.strokeStyle="rgba(220,242,230,.68)";ctx.lineWidth=1;ctx.strokeRect(pad,pad,pw,ph);ctx.beginPath();ctx.moveTo(pad+pw/2,pad);ctx.lineTo(pad+pw/2,pad+ph);ctx.stroke();ctx.beginPath();ctx.arc(pad+pw/2,pad+ph/2,ph*.09,0,Math.PI*2);ctx.stroke();const boxW=pw*.145,boxH=ph*.57,smallW=pw*.052,smallH=ph*.27;ctx.strokeRect(pad,pad+(ph-boxH)/2,boxW,boxH);ctx.strokeRect(pad+pw-boxW,pad+(ph-boxH)/2,boxW,boxH);ctx.strokeRect(pad,pad+(ph-smallH)/2,smallW,smallH);ctx.strokeRect(pad+pw-smallW,pad+(ph-smallH)/2,smallW,smallH);
}

function heatColor(value){if(value<.35)return`rgba(22,100,58,${.25+value})`;if(value<.7)return`rgba(64,229,141,${.3+value*.7})`;return`rgba(238,255,119,${.45+value*.55})`;}
function fact(label,value){return`<div><strong>${value}</strong><span>${label}</span></div>`;}
function scoreBox(label,value){return`<div><strong>${number(value)}</strong><span>${label}</span></div>`;}
function initials(name){return name.split(/\s+/).slice(0,2).map(part=>part[0]).join("").toUpperCase();}
function escapeHtml(value){return String(value??"").replace(/[&<>'"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);}
function debounce(fn,delay){let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay);};}
function toast(message){const element=$("#toast");element.textContent=message;element.classList.add("show");setTimeout(()=>element.classList.remove("show"),3500);}
