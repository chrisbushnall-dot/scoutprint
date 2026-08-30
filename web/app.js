"use strict";

const state={reference:null,referencePlayer:null,referenceMatches:[],results:[],lastSearch:null,catalogue:null,sort:{key:"recommendation_score",direction:"desc"},view:"list",comparison:null,map:"all",grid:[12,8],scrollY:0};
const $=selector=>document.querySelector(selector);
const $$=selector=>[...document.querySelectorAll(selector)];
const integer=new Intl.NumberFormat("en-GB",{maximumFractionDigits:0});
const decimal=new Intl.NumberFormat("en-GB",{minimumFractionDigits:1,maximumFractionDigits:1});

document.addEventListener("DOMContentLoaded",init);

async function init(){
  bindControls();
  const session=await fetchJson("/api/auth/session").catch(()=>({authenticated:false}));
  if(session.authenticated)await unlock();else showLogin();
}

function bindControls(){
  $("#login-form").addEventListener("submit",login);
  $("#logout-button").addEventListener("click",logout);
  $("#reference-search").addEventListener("input",debounce(()=>findReferences($("#reference-search").value),250));
  $("#reference-search").addEventListener("focus",()=>{if(state.referenceMatches.length)showReferenceOptions(state.referenceMatches);});
  $("#reference-season").addEventListener("change",syncReferenceCompetition);
  $("#reference-competition").addEventListener("change",syncReferenceProfile);
  $("#search-form").addEventListener("submit",event=>{event.preventDefault();runSearch();});
  $("#filter-toggle").addEventListener("click",toggleFilters);
  $("#apply-filters").addEventListener("click",()=>{runSearch();if(innerWidth<760)toggleFilters(false);});
  $("#result-limit").addEventListener("change",()=>{if(state.lastSearch)runSearch();});
  $$(".view-toggle button").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.mode)));
  $$("th button[data-sort]").forEach(button=>button.addEventListener("click",()=>setSort(button.dataset.sort)));
  $("#back-results").addEventListener("click",()=>{if(location.hash.startsWith("#player="))history.back();else showResults(false);});
  window.addEventListener("popstate",()=>showResults(false));
  window.addEventListener("resize",debounce(()=>{if(state.comparison)renderMaps();},120));
  document.addEventListener("click",event=>{if(!event.target.closest(".autocomplete"))hideReferenceOptions();});
}

async function login(event){
  event.preventDefault();const button=event.currentTarget.querySelector("button");button.disabled=true;$("#login-error").textContent="";
  try{await fetchJson("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("#login-password").value})});$("#login-password").value="";await unlock();}
  catch(error){$("#login-error").textContent=error.message;}finally{button.disabled=false;}
}

async function logout(){await fetchJson("/api/auth/logout",{method:"POST"}).catch(()=>null);showLogin();}
function showLogin(){document.body.classList.add("locked");$("#app-shell").hidden=true;$("#login-view").hidden=false;$("#login-password").focus();}

async function unlock(){
  document.body.classList.remove("locked");$("#login-view").hidden=true;$("#app-shell").hidden=false;
  try{await Promise.all([loadCatalogue(),findReferences("Mohamed Salah",true)]);}catch(error){handleError(error);}
}

async function loadCatalogue(){
  const payload=await proxy("recent/catalogue");state.catalogue=payload;
  $("#player-count").textContent=integer.format(payload.recent_players);$("#profile-count").textContent=integer.format(payload.recent_player_seasons);$("#window-count").textContent=payload.windows.length;
  $("#candidate-windows").innerHTML=payload.windows.map(item=>`<label><input type="checkbox" name="candidate-window" value="${escapeHtml(item.window)}" checked><span><b>${escapeHtml(item.window)}</b><small>${integer.format(item.player_seasons)} profiles</small></span></label>`).join("");
  $("#candidate-competition").innerHTML=`<option value="">All competitions</option>${payload.competitions.map(item=>`<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)} · ${integer.format(item.player_seasons)}</option>`).join("")}`;
  $("#candidate-position").innerHTML=`<option value="">All positions</option>${payload.positions.map(position=>`<option value="${escapeHtml(position)}">${escapeHtml(position)}</option>`).join("")}`;
}

async function findReferences(term,initial=false){
  const query=term.trim();if(query.length<2){hideReferenceOptions();return;}
  try{
    const payload=await proxy("players",{query:{name:query,limit:"30"}});state.referenceMatches=payload.players;
    if(initial){const salah=payload.players.find(player=>player.player_name.includes("Mohamed Salah"))||payload.players[0];if(salah){const profile=salah.profiles.find(item=>item.competition_name==="Premier League"&&item.season_name==="2017/18")||salah.profiles[0];await chooseReference(salah,profile);}}
    else showReferenceOptions(payload.players);
  }catch(error){handleError(error);}
}

function showReferenceOptions(players){
  const menu=$("#reference-options");$("#reference-search").setAttribute("aria-expanded","true");menu.hidden=false;
  if(!players.length){menu.innerHTML=`<p>No matching players</p>`;return;}
  menu.innerHTML=players.slice(0,30).map((player,index)=>`<button type="button" role="option" data-index="${index}"><strong>${escapeHtml(player.player_name)}</strong><span>${escapeHtml(player.clubs.slice(0,3).join(" / ")||"Club unavailable")} · ${integer.format(player.season_count)} available season${player.season_count===1?"":"s"}</span></button>`).join("");
  menu.querySelectorAll("button").forEach(button=>button.addEventListener("click",()=>chooseReference(players[Number(button.dataset.index)])));
}
function hideReferenceOptions(){$("#reference-options").hidden=true;$("#reference-search").setAttribute("aria-expanded","false");}

async function chooseReference(player,preferredProfile=null){
  hideReferenceOptions();state.referencePlayer=player;state.referenceMatches=player.profiles||[];$("#reference-search").value=player.player_name;
  const seasons=[...new Set(state.referenceMatches.map(item=>item.season_name))].sort().reverse();
  $("#reference-season").innerHTML=seasons.map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  $("#reference-season").value=preferredProfile?.season_name||seasons[0]||"";
  await syncReferenceCompetition(preferredProfile?.competition_name);
}

async function syncReferenceCompetition(preferred){
  const season=$("#reference-season").value;const matches=state.referenceMatches.filter(item=>item.season_name===season);
  const competitions=[...new Set(matches.map(item=>item.competition_name))].sort();$("#reference-competition").innerHTML=competitions.map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  $("#reference-competition").value=competitions.includes(preferred)?preferred:competitions[0]||"";await syncReferenceProfile();
}

async function syncReferenceProfile(){const match=state.referenceMatches.find(item=>item.competition_name===$("#reference-competition").value&&item.season_name===$("#reference-season").value);if(match&&match.player_season_id!==state.reference?.player_season_id)await loadReference(match.player_season_id);}
async function loadReference(id){const payload=await proxy(`player/${encodeURIComponent(id)}/profile`);state.reference=payload.profile;state.grid=payload.profile.grid;}

function searchRequest(){
  const optional=selector=>$(selector).value===""?null:Number($(selector).value);const competition=$("#candidate-competition").value;const position=$("#candidate-position").value;
  return {reference_player_season_id:state.reference.player_season_id,reference_competition:state.reference.competition_name,reference_season:state.reference.season_name,candidate_windows:$$('input[name="candidate-window"]:checked').map(input=>input.value),candidate_competitions:competition?[competition]:[],candidate_positions:position?[position]:[],data_tiers:$$('input[name="tier"]:checked').map(input=>input.value),recent_candidates_only:true,unique_players:true,minimum_minutes:Number($("#min-minutes").value)||0,minimum_age:optional("#age-min"),maximum_age:optional("#age-max"),mirror_mode:$("#mirror-mode").checked,minimum_profile_match:Number($("#min-profile").value)||0,minimum_comparison_coverage:Number($("#min-coverage").value)||0,result_limit:Number($("#result-limit").value)||50};
}

async function runSearch(){
  if(!state.reference){toast("Select a reference player-season first");return;}const windows=$$('input[name="candidate-window"]:checked');if(!windows.length){toast("Select at least one candidate season");return;}
  const button=$("#search-button");button.disabled=true;button.querySelector("span").textContent="Searching";showLoading(true);updateFilterCount();
  try{state.lastSearch=searchRequest();const payload=await proxy("search/similar",{method:"POST",body:state.lastSearch});state.results=payload.results;state.sort={key:"recommendation_score",direction:"desc"};renderResults();$("#results-meta").innerHTML=`<strong>${integer.format(payload.candidate_count)} unique matching players</strong><span>${escapeHtml(payload.engine)} · ${decimal.format(payload.runtime_ms)} ms</span>`;$("#results-section").scrollIntoView({behavior:"smooth",block:"start"});}
  catch(error){handleError(error);}finally{button.disabled=false;button.querySelector("span").textContent="Search";showLoading(false);}
}

function showLoading(active){$("#loading-state").hidden=!active;if(active){$("#empty-state").hidden=true;$("#list-results").hidden=true;$("#card-results").hidden=true;}}

function renderResults(){
  const results=sortedResults();$("#empty-state").hidden=results.length>0;if(!results.length){$("#empty-state").querySelector("h2").textContent="No candidates match these filters.";$("#empty-state").querySelector("p").textContent="Reduce the minutes, profile or coverage threshold and search again.";}
  $("#results-body").innerHTML=results.map(result=>`<tr tabindex="0" data-id="${escapeHtml(result.player_season_id)}"><td><span class="grade grade-${grade(result.recommendation_score).replace("+","plus").replace("-","minus")}">${grade(result.recommendation_score)}</span><small class="rec-score">${value(result.recommendation_score,0)}</small></td><td class="player-cell"><strong>${escapeHtml(result.player_name)}</strong><span>${escapeHtml(shortPosition(result.position))} · ${escapeHtml(result.club||"Club unavailable")} · ${escapeHtml(result.competition||"—")} · ${escapeHtml(result.candidate_window||result.season||"—")}</span><small class="why-label">${escapeHtml(matchLabels(result))}</small></td><td class="col-position">${escapeHtml(shortPosition(result.position))}</td><td class="col-club">${escapeHtml(result.club||"—")}</td><td class="col-league">${escapeHtml(result.competition||"—")}</td><td class="col-season">${escapeHtml(result.candidate_window||result.season||"—")}</td><td class="numeric">${value(result.age,1)}</td><td class="numeric col-minutes">${result.minutes==null?"—":integer.format(result.minutes)}</td><td class="numeric"><span class="profile-score">${value(result.profile_match,1)}</span></td><td class="numeric col-spatial">${value(result.spatial_match,1)}</td><td class="numeric col-xg">${value(result.xg_p90,2)}</td><td class="numeric col-xa">${value(result.xa_p90,2)}</td><td class="numeric"><span class="coverage-value">${percentage(result.comparison_coverage)}</span><small class="confidence confidence-${String(result.confidence||"low").toLowerCase()}">${escapeHtml(result.confidence||"LOW")}</small></td><td><span class="tier tier-${escapeHtml(result.data_tier)}">${escapeHtml(result.data_tier)}</span></td></tr>`).join("");
  $("#card-results").innerHTML=results.map(result=>`<button class="result-card surface" type="button" data-id="${escapeHtml(result.player_season_id)}"><span class="grade">${grade(result.recommendation_score)}</span><div><strong>${escapeHtml(result.player_name)}</strong><p>${escapeHtml(shortPosition(result.position))} · ${escapeHtml(result.club||"Club unavailable")}</p><small>${escapeHtml(result.competition||"—")} · ${escapeHtml(result.candidate_window||result.season||"—")}</small><em>${escapeHtml(matchLabels(result))}</em></div><dl><div><dt>REC</dt><dd>${value(result.recommendation_score,1)}</dd></div><div><dt>Profile</dt><dd>${value(result.profile_match,1)}</dd></div><div><dt>Coverage</dt><dd>${value(result.comparison_coverage,0)}%</dd></div><div><dt>Tier</dt><dd>${escapeHtml(result.data_tier)}</dd></div></dl></button>`).join("");
  $$('[data-id]').filter(element=>element.closest("#results-section")).forEach(element=>{element.addEventListener("click",()=>openComparison(element.dataset.id));element.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openComparison(element.dataset.id);}});});
  updateSortHeaders();setView(state.view);
}

function sortedResults(){return [...state.results].sort((a,b)=>{const av=a[state.sort.key],bv=b[state.sort.key];if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return-1;const order=typeof av==="string"?String(av).localeCompare(String(bv)):av-bv;return state.sort.direction==="asc"?order:-order;});}
function setSort(key){if(state.sort.key===key)state.sort.direction=state.sort.direction==="desc"?"asc":"desc";else state.sort={key,direction:"desc"};renderResults();}
function updateSortHeaders(){$$("th").forEach(th=>th.removeAttribute("aria-sort"));const button=$(`th button[data-sort="${state.sort.key}"]`);if(button)button.closest("th").setAttribute("aria-sort",state.sort.direction==="desc"?"descending":"ascending");}
function setView(mode){state.view=mode;$$(".view-toggle button").forEach(button=>button.classList.toggle("active",button.dataset.mode===mode));$("#list-results").hidden=mode!=="list"||!state.results.length;$("#card-results").hidden=mode!=="cards"||!state.results.length;}

async function openComparison(id){
  state.scrollY=scrollY;$("#search-view").hidden=true;$("#detail-view").hidden=false;$("#detail-content").hidden=true;$("#detail-loading").hidden=false;scrollTo({top:0});history.pushState({detail:id},"",`#player=${encodeURIComponent(id)}`);
  try{const payload=await proxy("comparison",{method:"POST",body:{...state.lastSearch,candidate_player_season_id:id}});state.comparison=payload;renderComparison();}
  catch(error){handleError(error);showResults(true);}
}

function showResults(updateHistory){$("#detail-view").hidden=true;$("#search-view").hidden=false;if(updateHistory)history.pushState({},"",location.pathname);requestAnimationFrame(()=>scrollTo({top:state.scrollY,behavior:"instant"}));}

function renderComparison(){
  const payload=state.comparison,score=payload.score,a=payload.reference,b=payload.candidate;state.grid=a.grid;$("#detail-loading").hidden=true;$("#detail-content").hidden=false;
  $("#detail-title").textContent=`${a.player_name} vs ${b.player_name}`;$("#detail-context").textContent=`${b.team_name||"Club unavailable"} · ${b.competition_name} · ${score.candidate_window||b.season_name}`;
  $("#detail-scores").innerHTML=scoreTile("REC",`${grade(score.recommendation_score)} · ${value(score.recommendation_score,1)}`)+scoreTile("Raw profile",value(score.profile_match,1))+scoreTile("Coverage",`${value(score.comparison_coverage,0)}% · ${score.confidence||"LOW"}`)+scoreTile("Role fit",`${value(score.role_compatibility,0)}%`)+scoreTile("Tier",score.data_tier);
  $("#reference-card").innerHTML=profileCard("Reference",a);$("#candidate-card").innerHTML=profileCard("Candidate",b);
  const spatial=Boolean(a.maps.all&&b.maps.all);$("#tier-notice").hidden=spatial;$("#maps-section").hidden=!spatial;
  if(spatial){const maps=Object.keys(a.maps).filter(key=>a.maps[key]&&b.maps[key]);$("#map-tabs").innerHTML=maps.map((key,index)=>`<button class="${index===0?"active":""}" type="button" data-map="${escapeHtml(key)}">${mapLabel(key)}</button>`).join("");state.map=maps[0]||"all";$("#map-tabs").querySelectorAll("button").forEach(button=>button.addEventListener("click",()=>{$$("#map-tabs button").forEach(item=>item.classList.toggle("active",item===button));state.map=button.dataset.map;renderMaps();}));$("#map-a-name").textContent=a.player_name;$("#map-b-name").textContent=b.player_name;renderMaps();}
  renderExplanation(score);renderMetricComparison();
}

function renderExplanation(score){const matching=score.top_matching_dimensions||[],differences=score.biggest_differences||[];$("#why-match").innerHTML=matching.map(item=>explanationBar(item,"match")).join("")||"<p>No comparable dimensions available.</p>";$("#where-differ").innerHTML=differences.map(item=>explanationBar(item,"difference")).join("")||"<p>No comparable differences available.</p>";$("#role-summary").textContent=`${score.role_family||"Unclassified"} · ${value(score.role_compatibility,0)}% role compatibility`;}
function explanationBar(item,kind){return`<div class="explanation-row ${kind}"><span>${escapeHtml(displayDimension(item.dimension))}</span><i><b style="width:${Math.max(0,Math.min(100,Number(item.score)||0))}%"></b></i><strong>${value(item.score,0)}</strong></div>`;}

function profileCard(label,profile){return`<p class="kicker">${label}</p><div class="profile-title"><span>${initials(profile.player_name)}</span><div><h2>${escapeHtml(profile.player_name)}</h2><p>${escapeHtml(profile.team_name||"Club unavailable")} · ${escapeHtml(profile.competition_name)} · ${escapeHtml(profile.season_name)}</p></div></div><dl><div><dt>Position</dt><dd>${escapeHtml(profile.positions||"—")}</dd></div><div><dt>Age</dt><dd>${value(profile.age,1)}</dd></div><div><dt>Minutes</dt><dd>${profile.minutes==null?"—":integer.format(profile.minutes)}</dd></div><div><dt>Data tier</dt><dd>${escapeHtml(profile.data_tier||"—")}</dd></div></dl>`;}

function renderMetricComparison(){const a=state.comparison.reference.statistics,b=state.comparison.candidate.statistics;const metrics=[["Goals / 90","goals_p90"],["Assists / 90","assists_p90"],["xG / 90","xg_p90"],["xA / 90","xa_p90"],["Shots / 90","shots_p90"],["Chances / 90","chance_creation_p90"],["Passes / 90","passes_p90"],["Defensive / 90","defensive_actions_p90"]];$("#metric-comparison").innerHTML=metrics.map(([label,key])=>`<div><span>${label}</span><strong>${value(a[key],2)}</strong><i></i><b>${value(b[key],2)}</b></div>`).join("");}
function renderMaps(){if(!state.comparison)return;const {reference,candidate,difference_maps:difference}=state.comparison;drawPitch($("#map-a"),reference.maps[state.map]);drawPitch($("#map-b"),candidate.maps[state.map]);drawPitch($("#map-diff"),difference[state.map],true);}

function drawPitch(canvas,vector,difference=false){if(!vector)return;const dpr=Math.min(devicePixelRatio||1,2),rect=canvas.getBoundingClientRect(),w=Math.max(260,rect.width),h=w/1.55;canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.height=`${h}px`;const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);const pad=10,pw=w-pad*2,ph=h-pad*2,[gx,gy]=state.grid,max=Math.max(...vector.map(Math.abs),1e-9);ctx.fillStyle="#07100c";ctx.fillRect(0,0,w,h);for(let x=0;x<gx;x++)for(let y=0;y<gy;y++){const item=vector[x*gy+y],strength=Math.min(1,Math.abs(item)/max);if(!strength)continue;ctx.fillStyle=difference?(item>=0?`rgba(68,229,143,${.08+.76*strength})`:`rgba(99,164,255,${.08+.72*strength})`):heatColor(strength);ctx.fillRect(pad+x*pw/gx,pad+y*ph/gy,pw/gx+.5,ph/gy+.5);}ctx.strokeStyle="rgba(221,240,230,.58)";ctx.lineWidth=1;ctx.strokeRect(pad,pad,pw,ph);ctx.beginPath();ctx.moveTo(pad+pw/2,pad);ctx.lineTo(pad+pw/2,pad+ph);ctx.stroke();ctx.beginPath();ctx.arc(pad+pw/2,pad+ph/2,ph*.09,0,Math.PI*2);ctx.stroke();const boxW=pw*.145,boxH=ph*.57;ctx.strokeRect(pad,pad+(ph-boxH)/2,boxW,boxH);ctx.strokeRect(pad+pw-boxW,pad+(ph-boxH)/2,boxW,boxH);}

function toggleFilters(force){const panel=$("#filters-panel"),open=force??panel.hidden;panel.hidden=!open;$("#filter-toggle").setAttribute("aria-expanded",String(open));}
function updateFilterCount(){let count=0;if($("#candidate-competition").value)count++;if($("#candidate-position").value)count++;for(const id of ["#age-min","#age-max","#min-profile","#min-coverage"])if(Number($(id).value)>0)count++;count+=3-$$('input[name="tier"]:checked').length;$("#filter-count").textContent=count;}
function matchLabels(result){return(result.top_matching_dimensions||[]).map(item=>displayDimension(item.dimension)).slice(0,3).join(" · ")||"Limited comparable evidence";}
function displayDimension(value){return({"Chance creation":"Creation","Spatial role":"Spatial role","Goal threat":"Goal threat"})[value]||value;}
function grade(score){if(score==null)return"—";if(score>=90)return"A+";if(score>=85)return"A";if(score>=80)return"A-";if(score>=75)return"B+";if(score>=70)return"B";if(score>=65)return"B-";return"C";}
function shortPosition(position){return String(position||"—").replaceAll("_"," ").split(" | ")[0];}
function scoreTile(label,valueText){return`<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(valueText)}</strong></div>`;}
function mapLabel(key){return({all:"All actions",shots:"Shots",goals:"Goals",chances:"Chances",passes:"Passes",defence:"Defence",receipts:"Receipts",carries:"Carries",progressions:"Progressions",dribbles:"Dribbles"})[key]||key;}
function heatColor(value){if(value<.35)return`rgba(18,99,57,${.28+value})`;if(value<.7)return`rgba(68,229,143,${.34+value*.68})`;return`rgba(235,255,121,${.5+value*.5})`;}
function initials(name){return String(name).split(/\s+/).slice(0,2).map(part=>part[0]).join("").toUpperCase();}
function value(item,digits=1){return item==null||!Number.isFinite(Number(item))?"—":Number(item).toFixed(digits);}
function percentage(item){return item==null||!Number.isFinite(Number(item))?"—":`${Number(item).toFixed(0)}%`;}
function debounce(fn,delay){let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay);};}
function escapeHtml(value){return String(value??"").replace(/[&<>'"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);}
function toast(message){const element=$("#toast");element.textContent=message;element.classList.add("show");setTimeout(()=>element.classList.remove("show"),4000);}
function handleError(error){toast(error.message);if(error.status===401)showLogin();}

async function proxy(endpoint,{method="GET",body=null,query={}}={}){const params=new URLSearchParams({endpoint,...query});return fetchJson(`/api/scoutprint?${params}`,{method,headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});}
async function fetchJson(url,options={}){const response=await fetch(url,options);const payload=await response.json().catch(()=>({}));if(!response.ok){const error=new Error(payload.detail||payload.error||`Request failed (${response.status})`);error.status=response.status;throw error;}return payload;}
