"use strict";

const state={reference:null,referencePlayer:null,referenceMatches:[],results:[],lastSearch:null,catalogue:null,sort:{key:"recommendation_score",direction:"desc"},view:"list",productView:"radar",comparison:null,map:"all",grid:[12,8],scrollY:0,radar:{catalogue:null,results:[],mode:"breakouts",sort:null,order:"desc"},league:{loaded:false},teams:{loaded:false},matches:{loaded:false,detail:null},players:{loaded:false,results:[],sort:"radar_score",order:"desc",offset:0,limit:50,total:0,dossier:null,scrollY:0},recruitment:{loaded:false,tool:"roles",results:[],sort:"current_level",order:"desc",offset:0,limit:50,total:0}};
const $=selector=>document.querySelector(selector);
const $$=selector=>[...document.querySelectorAll(selector)];
const integer=new Intl.NumberFormat("en-GB",{maximumFractionDigits:0});
const decimal=new Intl.NumberFormat("en-GB",{minimumFractionDigits:1,maximumFractionDigits:1});

function revealActiveControl(selector){
  const control=$(selector);if(!control||innerWidth>760)return;
  requestAnimationFrame(()=>control.scrollIntoView({block:"nearest",inline:"center"}));
}

document.addEventListener("DOMContentLoaded",init);

async function init(){
  bindControls();
  const session=await fetchJson("/api/auth/session").catch(()=>({authenticated:false}));
  if(session.authenticated)await unlock();else showLogin();
}

function bindControls(){
  $("#login-form").addEventListener("submit",login);
  $("#logout-button").addEventListener("click",logout);
  $$("#primary-nav [data-product-view]").forEach(button=>button.addEventListener("click",()=>showProductView(button.dataset.productView)));
  $$("[data-radar-mode]").forEach(button=>button.addEventListener("click",()=>setRadarMode(button.dataset.radarMode)));
  $$("[data-radar-sort]").forEach(button=>button.addEventListener("click",()=>setRadarSort(button.dataset.radarSort)));
  $("#radar-filters").addEventListener("submit",event=>{event.preventDefault();loadRadar();});
  $("#open-league-explorer").addEventListener("click",openLeagueExplorer);
  $("#back-radar").addEventListener("click",()=>showProductView("radar"));
  $("#league-league").addEventListener("change",syncLeagueSeasons);
  $("#league-filters").addEventListener("submit",event=>{event.preventDefault();loadLeague();});
  $("#team-league").addEventListener("change",syncTeamSeasons);
  $("#team-season").addEventListener("change",syncTeams);
  $("#team-filters").addEventListener("submit",event=>{event.preventDefault();loadTeam();});
  $("#match-filters").addEventListener("submit",event=>{event.preventDefault();loadMatches();});
  $("#back-matches").addEventListener("click",closeMatchDetail);
  $("#player-filters").addEventListener("submit",event=>{event.preventDefault();loadPlayers(true);});
  $$("[data-player-sort]").forEach(button=>button.addEventListener("click",()=>setPlayerSort(button.dataset.playerSort)));
  $("#player-previous").addEventListener("click",()=>changePlayerPage(-1));
  $("#player-next").addEventListener("click",()=>changePlayerPage(1));
  $("#back-players").addEventListener("click",()=>history.back());
  $$('[data-dossier-tab]').forEach(button=>button.addEventListener("click",()=>setDossierTab(button.dataset.dossierTab)));
  $("#player-filters").addEventListener("change",updatePlayerFilterCount);
  $$('[data-recruitment-tool]').forEach(button=>button.addEventListener("click",()=>setRecruitmentTool(button.dataset.recruitmentTool)));
  $("#recruitment-filters").addEventListener("submit",event=>{event.preventDefault();loadRecruitment(true);});
  $$('[data-recruitment-sort]').forEach(button=>button.addEventListener("click",()=>setRecruitmentSort(button.dataset.recruitmentSort)));
  $("#recruitment-previous").addEventListener("click",()=>changeRecruitmentPage(-1));
  $("#recruitment-next").addEventListener("click",()=>changeRecruitmentPage(1));
  $("#player-advanced-filters").open=innerWidth>760;
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
  window.addEventListener("popstate",()=>{if(!$("#player-dossier-view").hidden)closePlayerDossier(false);else showResults(false);});
  window.addEventListener("resize",debounce(()=>{if(state.comparison)renderMaps();},120));
  document.addEventListener("click",event=>{if(!event.target.closest(".autocomplete"))hideReferenceOptions();});
}

function showProductView(name){
  state.productView=name;
  $$("#primary-nav [data-product-view]").forEach(button=>button.classList.toggle("active",button.dataset.productView===name));
  revealActiveControl('#primary-nav [data-product-view].active');
  $$(".product-view").forEach(view=>{const viewName=view.dataset.productViewName||view.id.replace("-view","");view.hidden=viewName!==name;});
  $("#player-dossier-view").hidden=true;
  $("#detail-view").hidden=true;
  history.replaceState({},"",`#${name}`);
  if(name==="players"&&!state.players.loaded)loadPlayers(true);
  if(name==="recruitment"&&state.recruitment.tool==="roles"&&!state.recruitment.loaded)loadRecruitment(true);
  if(name==="teams"&&!state.teams.loaded)loadTeam();
  if(name==="matches"&&!state.matches.loaded)loadMatches();
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
  try{await Promise.all([loadCatalogue(),findReferences("Mohamed Salah",true),loadRadarCatalogue()]);const requested=location.hash.slice(1);showProductView(["radar","league","players","recruitment","teams","matches"].includes(requested)?requested:"radar");if(requested==="league")loadLeague();}catch(error){handleError(error);}
}

const radarModeCopy={
  "breakouts":["BREAKOUT SCORE","Breakouts","Emerging players ranked by current evidence, age context and supported development."],
  "biggest-risers":["DEVELOPMENT","Biggest Risers","Positive comparable season-on-season Current Level movement."],
  "u21":["AGE CONTEXT","U21","Players aged 21 or younger ranked by transparent Radar evidence."],
  "underlying-output":["PRODUCTION GAP","Underlying > Output","Supported xG and xA evidence running ahead of recorded goals and assists."],
  "role-changes":["ROLE EVOLUTION","Role Changes","Material behaviour-led role changes between comparable seasons."]
};
const leagueModes=["u21","breakouts","risers","attackers","creators","progressors","defenders","underlying-output","role-changes"];

async function loadRadarCatalogue(){
  const payload=await proxy("intelligence/catalogue");state.radar.catalogue=payload;
  $("#radar-player-count").textContent=integer.format(payload.players);$("#radar-profile-count").textContent=integer.format(payload.player_seasons);
  $("#explorer-player-count").textContent=integer.format(payload.players);$("#explorer-profile-count").textContent=integer.format(payload.player_seasons);
  $("#radar-season").innerHTML=`<option value="">All seasons</option>${payload.seasons.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#radar-league").innerHTML=`<option value="">All leagues</option>${payload.leagues.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#radar-role").innerHTML=`<option value="">All roles</option>${Object.keys(payload.roles).map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)} · ${integer.format(payload.roles[item])}</option>`).join("")}`;
  $("#radar-confidence").innerHTML=`<option value="">All confidence</option>${payload.confidences.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#player-season").innerHTML=`<option value="">Latest eligible</option>${payload.seasons.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#player-league").innerHTML=`<option value="">All leagues</option>${payload.leagues.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#player-role").innerHTML=`<option value="">All roles</option>${Object.keys(payload.roles).map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)} · ${integer.format(payload.roles[item])}</option>`).join("")}`;
  $("#player-position").innerHTML=`<option value="">All positions</option>${payload.positions.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#player-confidence").innerHTML=`<option value="">All confidence</option>${payload.confidences.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  const recruitmentRoles=Object.keys(payload.roles).filter(item=>item!=="Unclassified");
  $("#recruitment-role").innerHTML=recruitmentRoles.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)} · ${integer.format(payload.roles[item])}</option>`).join("");
  if(recruitmentRoles.includes("Box 9"))$("#recruitment-role").value="Box 9";
  $("#recruitment-league").innerHTML=`<option value="">All leagues</option>${payload.leagues.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#recruitment-season").innerHTML=`<option value="">Latest eligible</option>${payload.seasons.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  $("#recruitment-player-count").textContent=integer.format(payload.players);$("#recruitment-profile-count").textContent=integer.format(payload.player_seasons);
  $("#league-league").innerHTML=payload.leagues.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
  syncLeagueSeasons();
  const teamLeagues=[...new Set((payload.team_seasons||[]).map(item=>item.league))].sort();
  $("#team-league").innerHTML=teamLeagues.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
  syncTeamSeasons();
  await loadRadar();
}

function syncLeagueSeasons(){
  const catalogue=state.radar.catalogue||{},league=$("#league-league").value,seasons=catalogue.league_seasons?.[league]||[];
  $("#league-season").innerHTML=seasons.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
}

function openLeagueExplorer(){showProductView("league");if(!state.league.loaded)loadLeague();}

function leagueQuery(){return{league:$("#league-league").value,season:$("#league-season").value,minimum_minutes:String(Number($("#league-minutes").value)||0),limit_per_mode:"5"};}

async function loadLeague(){
  if(!$("#league-league").value||!$("#league-season").value)return;
  const button=$("#league-load");button.disabled=true;$("#league-loading").hidden=false;$("#league-content").hidden=true;$("#league-empty").hidden=true;
  try{const payload=await proxy("league",{query:leagueQuery()});state.league.loaded=true;renderLeague(payload);}
  catch(error){handleError(error);}finally{button.disabled=false;$("#league-loading").hidden=true;}
}

function renderLeague(payload){
  $("#league-empty").hidden=payload.player_seasons>0;$("#league-content").hidden=payload.player_seasons===0;
  $("#league-summary").innerHTML=`<div><strong>${integer.format(payload.players)}</strong><span>players</span></div><div><strong>${integer.format(payload.clubs)}</strong><span>clubs</span></div><div><strong>${integer.format(payload.classified_roles)}</strong><span>classified</span></div>`;
  const roles=payload.role_distribution||[],maximum=Math.max(1,...roles.map(item=>item.players));
  $("#league-role-distribution").innerHTML=roles.length?roles.map(item=>`<div><span>${escapeHtml(item.role)}</span><i><b style="width:${Math.max(2,100*item.players/maximum)}%"></b></i><strong>${integer.format(item.players)} · ${value(item.share,1)}%</strong></div>`).join(""):'<p class="safe-empty">Role evidence is unavailable for this population.</p>';
  const boards=payload.leaderboards||[];
  $("#league-leaderboards").innerHTML=leagueModes.map(id=>boards.find(board=>board.id===id)).filter(Boolean).map(board=>`<article class="league-board surface"><header><div><p class="kicker">${escapeHtml(board.sort.field.replaceAll("_"," "))}</p><h2>${escapeHtml(board.label)}</h2></div><span>${integer.format(board.available)} available</span></header>${board.players.length?`<ol>${board.players.map(row=>`<li><span>${escapeHtml(row.player_name)}<small>${escapeHtml(row.club||"Club unavailable")} · ${escapeHtml(row.primary_role||"Unclassified")}</small></span><strong>${leagueBoardValue(row,board.sort.field)}</strong></li>`).join("")}</ol>`:'<p class="league-board-empty">No supported players at this threshold.</p>'}</article>`).join("");
}

function leagueBoardValue(row,field){const digits=["xa_p90","output_gap"].includes(field)?2:1;return value(row[field],digits);}

function teamSelections(){return state.radar.catalogue?.team_seasons||[];}
function syncTeamSeasons(){const league=$("#team-league").value,seasons=[...new Set(teamSelections().filter(item=>item.league===league).map(item=>item.season))].sort().reverse();$("#team-season").innerHTML=seasons.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");syncTeams();}
function syncTeams(){const league=$("#team-league").value,season=$("#team-season").value,teams=[...new Set(teamSelections().filter(item=>item.league===league&&item.season===season).map(item=>item.team))].sort();$("#team-team").innerHTML=teams.map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");}
function teamQuery(){return{team:$("#team-team").value,league:$("#team-league").value,season:$("#team-season").value,minimum_minutes:String(Number($("#team-minutes").value)||0),limit:"8"};}
async function loadTeam(){if(!$("#team-team").value||!$("#team-league").value||!$("#team-season").value)return;const button=$("#team-load");button.disabled=true;$("#team-loading").hidden=false;$("#team-content").hidden=true;$("#team-empty").hidden=true;try{const payload=await proxy("team",{query:teamQuery()});state.teams.loaded=true;renderTeam(payload);}catch(error){handleError(error);}finally{button.disabled=false;$("#team-loading").hidden=true;}}
function renderTeam(payload){$("#team-empty").hidden=payload.player_seasons>0;$("#team-content").hidden=payload.player_seasons===0;$("#team-summary").innerHTML=`<div><strong>${integer.format(payload.players)}</strong><span>players</span></div><div><strong>${integer.format(payload.classified_roles)}</strong><span>classified</span></div><div><strong>${payload.u21_minutes_share==null?"—":value(payload.u21_minutes_share,1)+"%"}</strong><span>U21 minutes</span></div>`;$("#team-key-players").innerHTML=teamPlayerRows(payload.key_players,"current_level","Current");$("#team-breakouts").innerHTML=teamPlayerRows(payload.breakouts,"breakout_score","Breakout");$("#team-role-depth").innerHTML=(payload.role_depth||[]).map(item=>`<article><header><span class="role-chip">${escapeHtml(item.role)}</span><strong>${integer.format(item.players)} · ${integer.format(item.minutes)} min</strong></header><ol>${item.options.map(row=>`<li><span>${escapeHtml(row.player_name)}<small>${teamMinutes(row.minutes)} · ${escapeHtml(row.confidence||"LOW")}</small></span><b>${value(row.current_level,1)}</b></li>`).join("")}</ol></article>`).join("")||'<p class="safe-empty">Behavioural role evidence is unavailable for this team-season.</p>';$("#team-unavailable").innerHTML=(payload.unavailable||[]).map(item=>`<li>${escapeHtml(item)}</li>`).join("");}
function teamPlayerRows(rows,field,label){return rows.length?`<ol>${rows.map(row=>`<li><span>${escapeHtml(row.player_name)}<small>${escapeHtml(row.primary_role||"Unclassified")} · ${teamMinutes(row.minutes)} · ${escapeHtml(row.confidence||"LOW")}</small></span><strong>${value(row[field],1)}<small>${label}</small></strong></li>`).join("")}</ol>`:'<p class="safe-empty">No supported evidence is available at this threshold.</p>';}
function teamMinutes(minutes){return minutes==null?"Minutes unavailable":`${integer.format(minutes)} min`;}

function matchQuery(){const query={limit:"30"};[["league","#match-league"],["team","#match-team"],["date_from","#match-date-from"],["date_to","#match-date-to"]].forEach(([key,selector])=>{const item=$(selector).value.trim();if(item)query[key]=item;});return query;}
async function loadMatches(){const button=$("#match-load");button.disabled=true;$("#match-loading").hidden=false;$("#match-list").hidden=true;$("#match-detail").hidden=true;$("#match-empty").hidden=true;try{const payload=await proxy("matches",{query:matchQuery()});state.matches.loaded=true;renderMatches(payload);}catch(error){handleError(error);}finally{button.disabled=false;$("#match-loading").hidden=true;}}
function renderMatches(payload){const catalogue=payload.catalogue||{};if(!$("#match-league").options.length||$("#match-league").options.length===1){$("#match-league").innerHTML=`<option value="">All supported leagues</option>${(catalogue.leagues||[]).map(item=>`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;$("#match-date-from").min=catalogue.date_min||"";$("#match-date-from").max=catalogue.date_max||"";$("#match-date-to").min=catalogue.date_min||"";$("#match-date-to").max=catalogue.date_max||"";}$("#match-summary").innerHTML=`<div><strong>${integer.format(catalogue.supported_matches||0)}</strong><span>supported</span></div><div><strong>${integer.format(payload.total||0)}</strong><span>matching</span></div>`;const rows=payload.matches||[];$("#match-empty").hidden=rows.length>0;$("#match-list").hidden=rows.length===0;$("#match-list").innerHTML=rows.map(row=>`<button class="match-card surface" type="button" data-match-id="${escapeHtml(row.id)}"><span class="match-date">${escapeHtml(row.date||"Date unavailable")}<small>${escapeHtml(row.league?.name||"League unavailable")} · ${escapeHtml(row.round||"")}</small></span><span class="match-teams"><b>${escapeHtml(row.home_team?.name||"Home")}</b><b>${escapeHtml(row.away_team?.name||"Away")}</b></span><strong class="match-card-score">${row.score_home??"—"}<br>${row.score_away??"—"}</strong><span class="match-evidence-tags">${Object.entries(row.availability||{}).filter(([,available])=>available).map(([key])=>`<i>${escapeHtml(key.replaceAll("_"," "))}</i>`).join("")}</span></button>`).join("");$$('[data-match-id]').forEach(button=>button.addEventListener("click",()=>openMatch(button.dataset.matchId)));}
async function openMatch(id){$("#match-list").hidden=true;$("#match-filters").hidden=true;$("#match-detail").hidden=false;$("#match-evidence-grid").hidden=true;$("#match-loading").hidden=false;try{const payload=await proxy(`matches/${encodeURIComponent(id)}`);state.matches.detail=payload;renderMatch(payload);}catch(error){handleError(error);closeMatchDetail();}finally{$("#match-loading").hidden=true;}}
function closeMatchDetail(){$("#match-detail").hidden=true;$("#match-filters").hidden=false;$("#match-list").hidden=false;state.matches.detail=null;}
function renderMatch(payload){const match=payload.match;$("#match-detail-context").textContent=`${match.date||"Date unavailable"} · ${match.league?.name||"League unavailable"} · ${match.round||"Round unavailable"}`;$("#match-detail-title").textContent=`${match.home_team?.name||"Home"} vs ${match.away_team?.name||"Away"}`;$("#match-detail-ground").textContent=[match.stadium,match.referee?`Referee: ${match.referee}`:null].filter(Boolean).join(" · ");$("#match-detail-score").textContent=`${match.score_home??"—"}–${match.score_away??"—"}`;$("#match-evidence-grid").hidden=false;$("#match-shot-summary").innerHTML=(payload.shot_summary||[]).map(item=>`<div><strong>${escapeHtml(item.team?.name||"Team")}</strong><span>${item.shots} shots · ${item.on_target} on target · ${value(item.xg,2)} xG · ${item.big_chances} big chances</span></div>`).join("");$("#match-shot-sequence").innerHTML=(payload.shots||[]).map(shot=>`<div><b>${shot.minute??"—"}'</b><span>${escapeHtml(shot.player?.name||"Unknown")} · ${escapeHtml(shot.team||"")}<small>${escapeHtml(shot.outcome||"Shot")} · ${value(shot.xg,2)} xG</small></span></div>`).join("")||'<p class="safe-empty">Shot evidence is unavailable.</p>';$("#match-performers").innerHTML=(payload.top_performers||[]).map(row=>`<div><span>${escapeHtml(row.name||"Unknown")}<small>${escapeHtml(row.team||"")} · ${row.stats.minutes??"—"} min</small></span><strong>${value(row.stats.rating,2)}</strong></div>`).join("")||'<p class="safe-empty">Player ratings are unavailable.</p>';renderMatchLineups(payload);renderMatchPlayers(payload.player_stats||[]);renderMatchNetworks(payload.pass_networks||[]);$("#match-limitations").innerHTML=(payload.limitations||[]).map(item=>`<li>${escapeHtml(item)}</li>`).join("");requestAnimationFrame(()=>drawMatchShots($("#match-shot-map"),payload.shots||[],match));}
function renderMatchLineups(payload){const match=payload.match,lineups=payload.lineups||{};$("#match-lineup-grid").innerHTML=[[match.home_team,lineups.home],[match.away_team,lineups.away]].map(([team,side])=>`<section><header><strong>${escapeHtml(team?.name||"Team")}</strong><span>${escapeHtml(side?.formation||"Formation unavailable")}</span></header>${side?`<ol>${side.starters.map(player=>`<li><b>${escapeHtml(player.shirt_number||"—")}</b><span>${escapeHtml(player.name||"Unknown")}${player.captain?" (c)":""}</span></li>`).join("")}</ol><small>Coach: ${escapeHtml(side.coach||"Unavailable")} · ${side.substitutes.length} substitutes</small>`:'<p class="safe-empty">Lineup unavailable.</p>'}</section>`).join("");}
function renderMatchPlayers(rows){$("#match-player-stats").innerHTML=rows.length?`<table><thead><tr><th>Player</th><th>Team</th><th class="numeric">Rating</th><th class="numeric">Min</th><th class="numeric">G</th><th class="numeric">A</th><th class="numeric">xG+xA</th><th class="numeric">Chances</th><th class="numeric">Touches</th><th class="numeric">Def actions</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${escapeHtml(row.name||"Unknown")}</td><td>${escapeHtml(row.team||"—")}</td><td class="numeric">${value(row.stats.rating,2)}</td><td class="numeric">${row.stats.minutes??"—"}</td><td class="numeric">${row.stats.goals??"—"}</td><td class="numeric">${row.stats.assists??"—"}</td><td class="numeric">${value(row.stats.xg_xa,2)}</td><td class="numeric">${row.stats.chances_created??"—"}</td><td class="numeric">${row.stats.touches??"—"}</td><td class="numeric">${row.stats.defensive_actions??"—"}</td></tr>`).join("")}</tbody></table>`:'<p class="safe-empty">Player statistics are unavailable.</p>';}
function renderMatchNetworks(networks){$("#match-networks").innerHTML=networks.map(network=>`<section><header><strong>${escapeHtml(network.team?.name||"Team")}</strong><span>Centralisation ${value(network.centralization,2)}</span></header><ol>${network.nodes.sort((a,b)=>(b.passes||0)-(a.passes||0)).map(node=>`<li><span>${escapeHtml(node.player?.name||"Unknown")}<small>avg ${value(node.x,1)}, ${value(node.y,1)}</small></span><b>${node.passes??"—"} passes · ${node.received??"—"} received</b></li>`).join("")}</ol></section>`).join("")||'<p class="safe-empty">Pass-network positions are unavailable.</p>';}
function drawMatchShots(canvas,shots,match){const rect=canvas.getBoundingClientRect(),w=Math.max(280,rect.width),h=w/1.55,dpr=Math.min(devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.height=`${h}px`;const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);ctx.fillStyle="#07100c";ctx.fillRect(0,0,w,h);ctx.strokeStyle="rgba(221,240,230,.58)";ctx.strokeRect(10,10,w-20,h-20);ctx.beginPath();ctx.moveTo(w/2,10);ctx.lineTo(w/2,h-10);ctx.stroke();const homeId=match.home_team?.id;shots.forEach(shot=>{const x=10+(Number(shot.x)||0)*(w-20)/100,y=10+(Number(shot.y)||0)*(h-20)/100,r=3+Math.sqrt(Math.max(0,Number(shot.xg)||0))*12;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=shot.team_id===homeId?"rgba(68,229,143,.72)":"rgba(99,164,255,.72)";ctx.fill();if(String(shot.outcome).toLowerCase()==="goal"){ctx.strokeStyle="#ebff79";ctx.lineWidth=2;ctx.stroke();}});}

function setRecruitmentTool(tool){
  state.recruitment.tool=tool;$$('[data-recruitment-tool]').forEach(button=>button.classList.toggle("active",button.dataset.recruitmentTool===tool));
  revealActiveControl('.recruitment-tabs [data-recruitment-tool].active');
  $("#role-search-panel").hidden=tool!=="roles";$("#replacement-search-panel").hidden=tool!=="replacement";
  if(tool==="roles"&&!state.recruitment.loaded)loadRecruitment(true);
}

function recruitmentQuery(){
  const query={role:$("#recruitment-role").value,minimum_minutes:String(Number($("#recruitment-minutes").value)||0),sort_by:state.recruitment.sort,sort_order:state.recruitment.order,offset:String(state.recruitment.offset),limit:String(state.recruitment.limit)};
  const fields=[["league","#recruitment-league"],["season","#recruitment-season"],["minimum_age","#recruitment-age-min"],["maximum_age","#recruitment-age-max"]];fields.forEach(([key,selector])=>{const item=$(selector).value;if(item!=="")query[key]=item;});return query;
}

async function loadRecruitment(reset=false){
  if(reset)state.recruitment.offset=0;const results=$(".recruitment-results"),button=$("#recruitment-search-button");results.setAttribute("aria-busy","true");button.disabled=true;$("#recruitment-loading").hidden=false;$("#recruitment-table").hidden=true;$("#recruitment-cards").hidden=true;$("#recruitment-empty").hidden=true;$("#recruitment-pagination").hidden=true;
  try{const payload=await proxy("recruitment/roles",{query:recruitmentQuery()});state.recruitment.loaded=true;state.recruitment.results=payload.candidates;state.recruitment.total=payload.total;state.recruitment.sort=payload.sort.field;state.recruitment.order=payload.sort.order;renderRecruitment(payload);}
  catch(error){handleError(error);$("#recruitment-meta").textContent="Role Search could not be loaded.";}
  finally{$("#recruitment-loading").hidden=true;button.disabled=false;results.setAttribute("aria-busy","false");}
}

function renderRecruitment(payload){
  const rows=payload.candidates,start=payload.total?payload.offset+1:0,end=Math.min(payload.offset+rows.length,payload.total);$("#recruitment-meta").innerHTML=`<strong>${integer.format(payload.total)} candidates</strong><span>Showing ${integer.format(start)}–${integer.format(end)} · ${escapeHtml(payload.filters.role)} · ${escapeHtml(payload.sort.field.replaceAll("_"," "))}</span>`;
  $("#recruitment-empty").hidden=rows.length>0;$("#recruitment-table").hidden=!rows.length;$("#recruitment-cards").hidden=!rows.length;
  $("#recruitment-body").innerHTML=rows.map(row=>`<tr><td class="player-cell"><strong>${escapeHtml(row.player_name)}</strong><span>${escapeHtml(row.position||"Position unavailable")}</span></td><td>${escapeHtml(row.club||"—")}</td><td>${escapeHtml(row.competition||"—")}</td><td>${escapeHtml(row.season||row.candidate_window||"—")}</td><td class="numeric">${value(row.age,0)}</td><td class="numeric">${row.minutes==null?"—":integer.format(row.minutes)}</td><td class="numeric">${value(row.current_level,1)}</td><td class="numeric ${Number(row.development)>0?"positive":""}">${signedValue(row.development,1)}</td><td class="numeric"><strong class="radar-score">${value(row.role_fit,1)}</strong></td><td><span class="change-summary">${escapeHtml(roleFitReason(row))}</span></td><td><span class="confidence confidence-${String(row.confidence||"low").toLowerCase()}">${escapeHtml(row.confidence||"LOW")}</span></td></tr>`).join("");
  $("#recruitment-cards").innerHTML=rows.map(row=>`<article class="radar-card recruitment-card surface"><header><div><strong>${escapeHtml(row.player_name)}</strong><span>${escapeHtml(row.club||"Club unavailable")} · ${escapeHtml(row.competition||"—")} · ${escapeHtml(row.season||row.candidate_window||"—")}</span></div><b>${value(row.role_fit,1)}</b></header><p><span class="role-chip">${escapeHtml(row.primary_role)}</span><span class="confidence confidence-${String(row.confidence||"low").toLowerCase()}">${escapeHtml(row.confidence||"LOW")}</span></p><dl><div><dt>Current</dt><dd>${value(row.current_level,1)}</dd></div><div><dt>Dev</dt><dd>${signedValue(row.development,1)}</dd></div><div><dt>Minutes</dt><dd>${row.minutes==null?"—":integer.format(row.minutes)}</dd></div><div><dt>Age</dt><dd>${value(row.age,0)}</dd></div></dl><small>${escapeHtml(roleFitReason(row))}</small></article>`).join("");
  $$('[data-recruitment-sort]').forEach(button=>{const th=button.closest("th");th.removeAttribute("aria-sort");if(button.dataset.recruitmentSort===payload.sort.field)th.setAttribute("aria-sort",payload.sort.order==="desc"?"descending":"ascending");});
  const pages=Math.ceil(payload.total/payload.limit),page=Math.floor(payload.offset/payload.limit)+1;$("#recruitment-pagination").hidden=pages<=1;$("#recruitment-page-meta").textContent=`Page ${page} of ${pages}`;$("#recruitment-previous").disabled=payload.offset===0;$("#recruitment-next").disabled=payload.offset+payload.limit>=payload.total;
}

function roleFitReason(row){const evidence=row.role_fit_evidence||{},dimensions=Array.isArray(evidence.dimensions)?evidence.dimensions:[],top=dimensions.slice(0,2).map(item=>`${item.dimension} ${value(item.percentile,0)}p`);if(evidence.metric_coverage!=null)top.push(`${value(Number(evidence.metric_coverage)*100,0)}% behaviour coverage`);return top.join(" · ")||"Role evidence unavailable";}
function setRecruitmentSort(field){if(state.recruitment.sort===field)state.recruitment.order=state.recruitment.order==="desc"?"asc":"desc";else{state.recruitment.sort=field;state.recruitment.order="desc";}loadRecruitment(true);}
function changeRecruitmentPage(direction){state.recruitment.offset=Math.max(0,state.recruitment.offset+direction*state.recruitment.limit);loadRecruitment();$("#role-search-panel").scrollIntoView({behavior:"smooth",block:"start"});}

function playerQuery(){
  const query={minimum_minutes:String(Number($("#player-minutes").value)||0),unique_players:String(!$("#player-expand-seasons").checked),sort_by:state.players.sort,sort_order:state.players.order,offset:String(state.players.offset),limit:String(state.players.limit)};
  const fields=[["player","#player-name"],["club","#player-club"],["league","#player-league"],["season","#player-season"],["role","#player-role"],["position","#player-position"],["minimum_age","#player-age-min"],["maximum_age","#player-age-max"],["data_tier","#player-tier"],["confidence","#player-confidence"]];
  fields.forEach(([key,selector])=>{const item=$(selector).value.trim();if(item!=="")query[key]=item;});
  return query;
}

async function loadPlayers(reset=false){
  if(reset)state.players.offset=0;
  updatePlayerFilterCount();const results=$(".player-results"),button=$("#player-search-button");results.setAttribute("aria-busy","true");button.disabled=true;$("#player-loading").hidden=false;$("#player-table").hidden=true;$("#player-cards").hidden=true;$("#player-empty").hidden=true;$("#player-pagination").hidden=true;
  try{const payload=await proxy("players",{query:playerQuery()});state.players.loaded=true;state.players.results=payload.players;state.players.total=payload.total;state.players.sort=payload.sort.field;state.players.order=payload.sort.order;renderPlayers(payload);}
  catch(error){handleError(error);$("#player-meta").textContent="Player Explorer could not be loaded.";}
  finally{$("#player-loading").hidden=true;button.disabled=false;results.setAttribute("aria-busy","false");}
}

function renderPlayers(payload){
  const rows=payload.players,start=payload.total?payload.offset+1:0,end=Math.min(payload.offset+rows.length,payload.total),expanded=!payload.unique_players;
  $("#player-meta").innerHTML=`<strong>${integer.format(payload.total)} ${expanded?"player-seasons":"players"}</strong><span>Showing ${integer.format(start)}–${integer.format(end)} · ${expanded?"every season":"latest eligible season"}</span>`;
  $("#player-empty").hidden=rows.length>0;$("#player-table").hidden=!rows.length;$("#player-cards").hidden=!rows.length;
  $("#player-body").innerHTML=rows.map(row=>`<tr tabindex="0" data-dossier-id="${escapeHtml(row.player_season_id)}"><td class="player-cell"><strong>${escapeHtml(row.player_name)}</strong><span>${escapeHtml(row.position||"Position unavailable")}</span></td><td><span class="role-chip">${escapeHtml(row.primary_role||"Unclassified")}</span></td><td>${escapeHtml(row.club||"—")}</td><td>${escapeHtml(row.competition||"—")}</td><td>${escapeHtml(row.season||row.candidate_window||"—")}</td><td class="numeric">${value(row.age,0)}</td><td class="numeric">${row.minutes==null?"—":integer.format(row.minutes)}</td><td class="numeric">${value(row.current_level,1)}</td><td class="numeric ${Number(row.development)>0?"positive":""}">${signedValue(row.development,1)}</td><td class="numeric"><strong class="radar-score">${value(row.radar_score,1)}</strong></td><td class="numeric">${value(row.xg_p90,2)}</td><td class="numeric">${value(row.xa_p90,2)}</td><td><span class="tier tier-${escapeHtml(row.data_tier)}">${escapeHtml(row.data_tier||"—")}</span></td><td><span class="confidence confidence-${String(row.confidence||"low").toLowerCase()}">${escapeHtml(row.confidence||"LOW")}</span></td></tr>`).join("");
  $("#player-cards").innerHTML=rows.map(row=>`<button class="player-card surface" type="button" data-dossier-id="${escapeHtml(row.player_season_id)}"><header><div><strong>${escapeHtml(row.player_name)}</strong><span>${escapeHtml(row.club||"Club unavailable")} · ${escapeHtml(row.competition||"—")}</span></div><b>${value(row.radar_score,1)}<small>Radar</small></b></header><p><span class="role-chip">${escapeHtml(row.primary_role||"Unclassified")}</span><span class="confidence confidence-${String(row.confidence||"low").toLowerCase()}">${escapeHtml(row.confidence||"LOW")}</span><span class="tier tier-${escapeHtml(row.data_tier)}">${escapeHtml(row.data_tier||"—")}</span></p><dl><div><dt>Current</dt><dd>${value(row.current_level,1)}</dd></div><div><dt>Development</dt><dd>${signedValue(row.development,1)}</dd></div><div><dt>Minutes</dt><dd>${row.minutes==null?"—":integer.format(row.minutes)}</dd></div><div><dt>Age</dt><dd>${value(row.age,0)}</dd></div></dl><footer><span>${escapeHtml(row.season||row.candidate_window||"Season unavailable")}</span><span>xG ${value(row.xg_p90,2)} · xA ${value(row.xa_p90,2)}</span></footer></button>`).join("");
  $$('[data-dossier-id]').forEach(element=>{element.addEventListener("click",()=>openPlayerDossier(element.dataset.dossierId));element.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openPlayerDossier(element.dataset.dossierId);}});});
  $$("[data-player-sort]").forEach(button=>{const th=button.closest("th");th.removeAttribute("aria-sort");if(button.dataset.playerSort===payload.sort.field)th.setAttribute("aria-sort",payload.sort.order==="desc"?"descending":"ascending");});
  const pages=Math.ceil(payload.total/payload.limit),page=Math.floor(payload.offset/payload.limit)+1;$("#player-pagination").hidden=pages<=1;$("#player-page-meta").textContent=`Page ${page} of ${pages}`;$("#player-previous").disabled=payload.offset===0;$("#player-next").disabled=payload.offset+payload.limit>=payload.total;
}

function setPlayerSort(field){if(state.players.sort===field)state.players.order=state.players.order==="desc"?"asc":"desc";else{state.players.sort=field;state.players.order=["player_name","role","data_tier","confidence"].includes(field)?"asc":"desc";}loadPlayers(true);}
function changePlayerPage(direction){state.players.offset=Math.max(0,state.players.offset+direction*state.players.limit);loadPlayers();$("#players-view").scrollIntoView({behavior:"smooth",block:"start"});}
function updatePlayerFilterCount(){const selectors=["#player-league","#player-season","#player-role","#player-position","#player-age-min","#player-age-max","#player-tier","#player-confidence"];let count=selectors.filter(selector=>$(selector).value!=="").length;if(Number($("#player-minutes").value)>0)count++;if($("#player-expand-seasons").checked)count++;$("#player-filter-count").textContent=count;}

async function openPlayerDossier(id){
  state.players.scrollY=scrollY;setDossierTab("overview");$("#players-view").hidden=true;$("#player-dossier-view").hidden=false;$("#dossier-content").hidden=true;$("#dossier-loading").hidden=false;scrollTo({top:0});history.pushState({dossier:id},"",`#dossier=${encodeURIComponent(id)}`);
  try{const payload=await proxy(`player/${encodeURIComponent(id)}/intelligence`);state.players.dossier=payload.intelligence;renderPlayerDossier(payload.intelligence);}
  catch(error){handleError(error);history.replaceState({},"","#players");closePlayerDossier(false);}
}

function closePlayerDossier(){$("#player-dossier-view").hidden=true;$("#players-view").hidden=false;requestAnimationFrame(()=>scrollTo({top:state.players.scrollY,behavior:"instant"}));}

function renderPlayerDossier(player){
  $("#dossier-loading").hidden=true;$("#dossier-content").hidden=false;$("#dossier-name").textContent=player.player_name||"Unnamed player";$("#dossier-context").textContent=`${player.club||"Club unavailable"} · ${player.competition||"League unavailable"} · ${player.season||player.candidate_window||"Season unavailable"}`;
  $("#dossier-scores").innerHTML=scoreTile("Current level",value(player.current_level,1))+scoreTile("Radar",value(player.radar_score,1))+scoreTile("Development",signedValue(player.development,1))+scoreTile("Confidence",player.confidence||"LOW");
  const facts=[["Position",player.position||"Unavailable"],["Age",value(player.age,0)],["Minutes",player.minutes==null?"Unavailable":integer.format(player.minutes)],["Data tier",player.data_tier||"Unavailable"],["Career seasons",value(player.career_seasons,0)],["Metric coverage",player.metric_coverage==null?"Unavailable":percentage(Number(player.metric_coverage)*100)]];
  $("#dossier-facts").innerHTML=facts.map(([label,item])=>`<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(item)}</dd></div>`).join("");
  $("#dossier-confidence-note").textContent=`${player.confidence||"LOW"} evidence confidence · ${value(player.confidence_score,0)} / 100. Confidence reflects minutes, metric coverage, seasons, data tier and spatial availability.`;
  $("#dossier-role").textContent=player.primary_role||"Unclassified";const secondary=player.secondary_role?` Secondary role: ${player.secondary_role}.`:"";const support=player.role_evidence?.position_support||player.position||"unavailable";$("#dossier-role-context").textContent=`Classified from available behaviour; provider position (${support}) is supporting evidence only.${secondary}`;
  renderRoleEvidence(player);renderCurrentLevel(player);renderDevelopment(player);renderDossierEvidence(player);
}

function setDossierTab(tab){
  $$('[data-dossier-tab]').forEach(button=>button.classList.toggle("active",button.dataset.dossierTab===tab));
  revealActiveControl('.dossier-tabs [data-dossier-tab].active');
  $$('[data-dossier-panel]').forEach(panel=>{panel.hidden=panel.dataset.dossierPanel!==tab;});
}

function renderRoleEvidence(player){
  const evidence=player.role_evidence||{},dimensions=Array.isArray(evidence.dimensions)?evidence.dimensions:[];
  $("#dossier-role-evidence").innerHTML=dimensions.length?dimensions.map(item=>evidenceBar(item.dimension,item.percentile,`${value(item.percentile,0)} percentile · weight ${value(item.weight,2)}`)).join(""):`<p class="safe-empty">${escapeHtml(evidence.limitation||"Behavioural role dimensions are unavailable for this player-season.")}</p>`;
}

function renderCurrentLevel(player){
  $("#dossier-current-level").textContent=value(player.current_level,1);const components=Object.entries(player.current_level_components||{}).filter(([,item])=>item!=null);
  $("#dossier-current-components").innerHTML=components.length?components.map(([metric,item])=>evidenceBar(metricLabel(metric),item,`${value(item,0)} percentile`)).join(""):'<p class="safe-empty">Role-relative component percentiles are unavailable for this player-season.</p>';
  const population=player.league_population==null?"unavailable":integer.format(player.league_population),raw=value(player.current_level_raw,1),league=ratioPercentage(player.league_population_factor),sample=ratioPercentage(player.sample_factor);
  $("#dossier-current-adjustments").innerHTML=`<div><span>Raw component mean</span><strong>${raw}</strong></div><div><span>League population</span><strong>${population}</strong></div><div><span>Population reliability</span><strong>${league}</strong></div><div><span>Sample reliability</span><strong>${sample}</strong></div>`;
}

function renderDevelopment(player){
  const history=Array.isArray(player.history)?player.history:[],comparable=history.filter(item=>item.development!=null);
  $("#dossier-development-score").textContent=player.development==null?"—":signedValue(player.development,1);
  if(player.development==null){
    $("#dossier-development-summary").innerHTML='<p class="safe-empty">Comparable consecutive-season Development is unavailable for this player-season.</p>';
  }else{
    const context=player.development_context||{},changes=Array.isArray(context.biggest_metric_changes)?context.biggest_metric_changes:[];
    const transition=[context.team_change&&player.previous_club?`${player.previous_club} → ${player.club||"current club"}`:"",context.league_change&&player.previous_league?`${player.previous_league} → ${player.competition||"current league"}`:""].filter(Boolean);
    $("#dossier-development-summary").innerHTML=`<div class="development-summary"><div><span>Previous Current Level</span><strong>${value(player.previous_current_level,1)}</strong></div><div><span>Current Level movement</span><strong class="${Number(player.development)>0?"positive":""}">${signedValue(player.development,1)}</strong></div><div><span>Comparable transitions</span><strong>${integer.format(comparable.length)}</strong></div></div>${changes.length?`<div class="metric-change-list">${changes.map(item=>`<span>${escapeHtml(item.metric)} <strong class="${Number(item.change)>0?"positive":""}">${signedValue(item.change,item.metric==="Minutes"?0:2)}</strong></span>`).join("")}</div>`:""}${transition.length?`<p class="development-transition">${escapeHtml(transition.join(" · "))}</p>`:""}`;
  }
  $("#dossier-development-history").innerHTML=history.length?history.map(item=>`<article class="development-season${item.player_season_id===player.player_season_id?" current":""}"><header><div><strong>${escapeHtml(item.season||item.candidate_window||"Season unavailable")}</strong><span>${escapeHtml(item.club||"Club unavailable")} · ${escapeHtml(item.competition||"League unavailable")}</span></div><span class="role-chip">${escapeHtml(item.primary_role||"Unclassified")}</span></header><dl><div><dt>Current Level</dt><dd>${value(item.current_level,1)}</dd></div><div><dt>Development</dt><dd class="${Number(item.development)>0?"positive":""}">${item.development==null?"Unavailable":signedValue(item.development,1)}</dd></div><div><dt>Minutes</dt><dd>${item.minutes==null?"Unavailable":integer.format(item.minutes)}</dd></div><div><dt>Confidence</dt><dd>${escapeHtml(item.confidence||"LOW")}</dd></div></dl></article>`).join(""):'<p class="safe-empty">No season history is available for this player.</p>';
  const transitions=history.filter(item=>item.role_changed&&item.previous_role);
  $("#dossier-role-evolution").innerHTML=transitions.length?transitions.map(item=>`<div class="role-transition"><span>${escapeHtml(item.season||item.candidate_window||"Season")}</span><strong>${escapeHtml(item.previous_role)} <i>→</i> ${escapeHtml(item.primary_role||"Unclassified")}</strong><small>${escapeHtml(item.previous_club||"Previous club")} → ${escapeHtml(item.club||"Current club")}</small></div>`).join(""):`<p class="safe-empty">${history.length<2?"Role evolution is unavailable without multi-season history.":"No supported behavioural role change appears across available consecutive seasons."}</p>`;
}

function evidenceBar(label,percentile,detail){const width=Math.max(0,Math.min(100,Number(percentile)||0));return`<div class="evidence-row"><div><span>${escapeHtml(label)}</span><strong>${escapeHtml(detail)}</strong></div><i><b style="width:${width}%"></b></i></div>`;}
function metricLabel(metric){return String(metric).replace(/_p90$/," / 90").replaceAll("_"," ").replace(/\b\w/g,letter=>letter.toUpperCase()).replace("Xg","xG").replace("Xa","xA");}
function ratioPercentage(item){return item==null?"—":`${value(Number(item)*100,0)}%`;}

function renderDossierEvidence(player){
  const evidence=player.dossier_evidence||{},grid=Array.isArray(evidence.grid)?evidence.grid:[12,8];
  const spatial=evidence.spatial||{},shooting=evidence.shooting||{},creation=evidence.creation||{};
  const spatialMap=Boolean(spatial.map_available&&spatial.map);$("#dossier-spatial-map-wrap").hidden=!spatialMap;$("#dossier-spatial-empty").hidden=spatialMap;
  $("#dossier-spatial-note").textContent=spatialMap?(spatial.event_count==null?"Recorded action":integer.format(spatial.event_count)+" recorded actions")+" · normalized "+grid[0]+"×"+grid[1]+" fingerprint.":"No supported action-location fingerprint is available.";
  $("#dossier-spatial-metrics").innerHTML=metricTiles(spatial.metrics,true,"Spatial distribution dimensions are unavailable for this player-season.");
  if(spatialMap)requestAnimationFrame(()=>drawEvidencePitch($("#dossier-spatial-map"),spatial.map,grid));

  const shotMap=Boolean(shooting.map_available&&shooting.maps?.shots);$("#dossier-shooting-maps").hidden=!shotMap;$("#dossier-goal-map-card").hidden=!shooting.maps?.goals;$("#dossier-shooting-map-empty").hidden=shotMap;
  $("#dossier-shooting-note").textContent=shotMap?(shooting.event_count==null?"Recorded shots":integer.format(shooting.event_count)+" recorded shots")+" · location frequency, not shot probability.":"No supported shot-location fingerprint is available.";
  $("#dossier-shooting-label").textContent=(player.underlying_output_label||"Underlying-versus-output label unavailable")+". "+(shooting.definition||"xG definition unavailable; no unsupported interpretation is added.");
  $("#dossier-shooting-metrics").innerHTML=metricTiles(shooting.metrics,false,"Shooting metrics are unavailable for this player-season.");
  if(shotMap)requestAnimationFrame(()=>{drawEvidencePitch($("#dossier-shot-map"),shooting.maps.shots,grid);if(shooting.maps.goals)drawEvidencePitch($("#dossier-goal-map"),shooting.maps.goals,grid);});

  const creationMap=Boolean(creation.map_available&&creation.map);$("#dossier-creation-map-wrap").hidden=!creationMap;$("#dossier-creation-map-empty").hidden=creationMap;
  const creationDefinition=creation.definitions?.chance_creation||creation.definitions?.xa;$("#dossier-creation-note").textContent=creationMap?(creation.event_count==null?"Recorded creations":integer.format(creation.event_count)+" recorded creations")+" · "+(creationDefinition||"source-defined chance creation")+".":"No supported creation-location fingerprint is available.";
  $("#dossier-creation-metrics").innerHTML=metricTiles(creation.metrics,false,"Creation metrics are unavailable for this player-season.");
  if(creationMap)requestAnimationFrame(()=>drawEvidencePitch($("#dossier-creation-map"),creation.map,grid));
}

function drawEvidencePitch(canvas,vector,grid){const previous=state.grid;state.grid=grid;drawPitch(canvas,vector);state.grid=previous;}
function metricTiles(metrics={},asShare=false,empty){const items=Object.entries(metrics).filter(([,item])=>item!=null);return items.length?items.map(([metric,item])=>'<div><span>'+escapeHtml(metricLabel(metric))+'</span><strong>'+(asShare?percentage(Number(item)*100):value(item,metric.endsWith("_p90")?2:1))+'</strong></div>').join(""):'<p class="safe-empty">'+escapeHtml(empty)+'</p>';}

function radarQuery(){
  const query={mode:state.radar.mode,minimum_minutes:String(Number($("#radar-minutes").value)||0),limit:"50"};
  const fields=[["season","#radar-season"],["league","#radar-league"],["role","#radar-role"],["confidence","#radar-confidence"],["minimum_age","#radar-age-min"],["maximum_age","#radar-age-max"]];
  fields.forEach(([key,selector])=>{const item=$(selector).value;if(item!=="")query[key]=item;});
  if(state.radar.sort){query.sort_by=state.radar.sort;query.sort_order=state.radar.order;}
  return query;
}

async function loadRadar(){
  const results=$(".radar-results");results.setAttribute("aria-busy","true");$("#radar-loading").hidden=false;$("#radar-table").hidden=true;$("#radar-cards").hidden=true;$("#radar-empty").hidden=true;
  try{
    const payload=await proxy("radar",{query:radarQuery()});state.radar.results=payload.results;state.radar.sort=payload.sort.field;state.radar.order=payload.sort.order;renderRadar(payload);
  }catch(error){handleError(error);$("#radar-meta").textContent="Radar could not be loaded.";}finally{$("#radar-loading").hidden=true;results.setAttribute("aria-busy","false");}
}

function setRadarMode(mode){
  state.radar.mode=mode;state.radar.sort=null;state.radar.order="desc";$$("[data-radar-mode]").forEach(button=>button.classList.toggle("active",button.dataset.radarMode===mode));
  revealActiveControl('#radar-modes [data-radar-mode].active');
  const copy=radarModeCopy[mode];$("#radar-mode-kicker").textContent=copy[0];$("#radar-mode-title").textContent=copy[1];$("#radar-mode-description").textContent=copy[2];loadRadar();
}

function setRadarSort(field){
  if(state.radar.sort===field)state.radar.order=state.radar.order==="desc"?"asc":"desc";else{state.radar.sort=field;state.radar.order="desc";}loadRadar();
}

function renderRadar(payload){
  const rows=payload.results;$("#radar-meta").innerHTML=`<strong>${integer.format(payload.total)} players</strong><span>Showing ${integer.format(rows.length)} · ${escapeHtml(payload.sort.field.replaceAll("_"," "))}</span>`;
  $("#radar-empty").hidden=rows.length>0;$("#radar-table").hidden=!rows.length;$("#radar-cards").hidden=!rows.length;
  $("#radar-body").innerHTML=rows.map(row=>`<tr><td class="numeric"><strong class="radar-score">${value(row.radar_score,1)}</strong></td><td class="numeric">${value(row.breakout_score,1)}</td><td class="player-cell"><strong>${escapeHtml(row.player_name)}</strong><span>${escapeHtml(row.position||"Position unavailable")} · ${escapeHtml(row.season||row.candidate_window||"—")}</span></td><td><span class="role-chip">${escapeHtml(row.primary_role||"Unclassified")}</span></td><td>${escapeHtml(row.club||"—")}</td><td>${escapeHtml(row.competition||"—")}</td><td class="numeric">${value(row.age,0)}</td><td class="numeric">${value(row.current_level,1)}</td><td class="numeric ${Number(row.development)>0?"positive":""}">${signedValue(row.development,1)}</td><td class="numeric">${row.minutes==null?"—":integer.format(row.minutes)}</td><td class="numeric">${value(row.xg_p90,2)}</td><td class="numeric">${value(row.xa_p90,2)}</td><td><span class="change-summary">${radarChange(row)}</span></td><td><span class="confidence confidence-${String(row.confidence||"low").toLowerCase()}">${escapeHtml(row.confidence||"LOW")}</span></td></tr>`).join("");
  $("#radar-cards").innerHTML=rows.map(row=>`<article class="radar-card surface"><header><div><strong>${escapeHtml(row.player_name)}</strong><span>${escapeHtml(row.club||"Club unavailable")} · ${escapeHtml(row.competition||"—")}</span></div><b>${value(radarPrimaryScore(row),1)}</b></header><p><span class="role-chip">${escapeHtml(row.primary_role||"Unclassified")}</span><span class="confidence confidence-${String(row.confidence||"low").toLowerCase()}">${escapeHtml(row.confidence||"LOW")}</span></p><dl><div><dt>Age</dt><dd>${value(row.age,0)}</dd></div><div><dt>Current</dt><dd>${value(row.current_level,1)}</dd></div><div><dt>Dev</dt><dd>${signedValue(row.development,1)}</dd></div><div><dt>Minutes</dt><dd>${row.minutes==null?"—":integer.format(row.minutes)}</dd></div></dl><small>${radarChange(row)}</small></article>`).join("");
  $$("[data-radar-sort]").forEach(button=>{const th=button.closest("th");th.removeAttribute("aria-sort");if(button.dataset.radarSort===payload.sort.field)th.setAttribute("aria-sort",payload.sort.order==="desc"?"descending":"ascending");});
}

function radarPrimaryScore(row){return state.radar.mode==="breakouts"?row.breakout_score:state.radar.mode==="biggest-risers"?row.development:state.radar.mode==="underlying-output"?row.output_gap:row.radar_score;}
function radarChange(row){
  if(state.radar.mode==="role-changes")return `${row.previous_role||"Unclassified"} → ${row.primary_role||"Unclassified"}${row.spatial_change==null?"":` · spatial ${signedValue(row.spatial_change,1)}`}`;
  if(state.radar.mode==="underlying-output")return `${row.underlying_output_label||"Underlying lead"} · gap ${signedValue(row.output_gap,2)}`;
  const changes=[];if(row.xg_change!=null)changes.push(`xG ${signedValue(row.xg_change,2)}`);if(row.xa_change!=null)changes.push(`xA ${signedValue(row.xa_change,2)}`);if(row.minutes_change!=null)changes.push(`min ${signedValue(row.minutes_change,0)}`);return changes.join(" · ")||"Comparable change unavailable";
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
    if(initial){const salah=payload.players.find(player=>player.player_name.includes("Mohamed Salah"))||payload.players[0];if(salah)await chooseReference(salah,salah.profiles[0]);}
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
  return {reference_player_season_id:state.reference.player_season_id,reference_competition:state.reference.competition_name,reference_season:state.reference.season_name,candidate_windows:$$('input[name="candidate-window"]:checked').map(input=>input.value),candidate_competitions:competition?[competition]:[],candidate_positions:position?[position]:[],data_tiers:$$('input[name="tier"]:checked').map(input=>input.value),recent_candidates_only:true,unique_players:true,minimum_minutes:Number($("#min-minutes").value)||0,minimum_age:optional("#age-min"),maximum_age:optional("#age-max"),mirror_mode:$("#mirror-mode").checked,minimum_profile_match:Number($("#min-profile").value)||0,minimum_comparison_coverage:Number($("#min-coverage").value)||0,include_low_confidence:$("#include-low-confidence").checked,result_limit:Number($("#result-limit").value)||50};
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

function renderExplanation(score){const matching=score.top_matching_dimensions||[],differences=score.biggest_differences||[];$("#why-match").innerHTML=matching.map(item=>explanationBar(item,"match")).join("")||"<p>No comparable dimensions available.</p>";$("#where-differ").innerHTML=differences.map(item=>explanationBar(item,"difference")).join("")||"<p>No comparable differences available.</p>";$("#role-summary").textContent=`${score.role_family||"Unclassified"} · ${value(score.role_compatibility,0)}% role compatibility · ${value(score.comparison_coverage,0)}% comparable evidence. Fit is descriptive, not a transfer recommendation.`;}
function explanationBar(item,kind){return`<div class="explanation-row ${kind}"><span>${escapeHtml(displayDimension(item.dimension))}</span><i><b style="width:${Math.max(0,Math.min(100,Number(item.score)||0))}%"></b></i><strong>${value(item.score,0)}</strong></div>`;}

function profileCard(label,profile){return`<p class="kicker">${label}</p><div class="profile-title"><span>${initials(profile.player_name)}</span><div><h2>${escapeHtml(profile.player_name)}</h2><p>${escapeHtml(profile.team_name||"Club unavailable")} · ${escapeHtml(profile.competition_name)} · ${escapeHtml(profile.season_name)}</p></div></div><dl><div><dt>Position</dt><dd>${escapeHtml(profile.positions||"—")}</dd></div><div><dt>Age</dt><dd>${value(profile.age,1)}</dd></div><div><dt>Minutes</dt><dd>${profile.minutes==null?"—":integer.format(profile.minutes)}</dd></div><div><dt>Data tier</dt><dd>${escapeHtml(profile.data_tier||"—")}</dd></div></dl>`;}

function renderMetricComparison(){const a=state.comparison.reference.statistics,b=state.comparison.candidate.statistics;const metrics=[["Goals / 90","goals_p90"],["Assists / 90","assists_p90"],["xG / 90","xg_p90"],["xA / 90","xa_p90"],["Shots / 90","shots_p90"],["Chances / 90","chance_creation_p90"],["Passes / 90","passes_p90"],["Defensive / 90","defensive_actions_p90"]];$("#metric-comparison").innerHTML=metrics.map(([label,key])=>`<div><span>${label}</span><strong>${value(a[key],2)}</strong><i></i><b>${value(b[key],2)}</b></div>`).join("");}
function renderMaps(){if(!state.comparison)return;const {reference,candidate,difference_maps:difference}=state.comparison;drawPitch($("#map-a"),reference.maps[state.map]);drawPitch($("#map-b"),candidate.maps[state.map]);drawPitch($("#map-diff"),difference[state.map],true);}

function drawPitch(canvas,vector,difference=false){if(!vector)return;const dpr=Math.min(devicePixelRatio||1,2),rect=canvas.getBoundingClientRect(),w=Math.max(260,rect.width),h=w/1.55;canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.height=`${h}px`;const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);const pad=10,pw=w-pad*2,ph=h-pad*2,[gx,gy]=state.grid,max=Math.max(...vector.map(Math.abs),1e-9);ctx.fillStyle="#07100c";ctx.fillRect(0,0,w,h);for(let x=0;x<gx;x++)for(let y=0;y<gy;y++){const item=vector[x*gy+y],strength=Math.min(1,Math.abs(item)/max);if(!strength)continue;ctx.fillStyle=difference?(item>=0?`rgba(68,229,143,${.08+.76*strength})`:`rgba(99,164,255,${.08+.72*strength})`):heatColor(strength);ctx.fillRect(pad+x*pw/gx,pad+y*ph/gy,pw/gx+.5,ph/gy+.5);}ctx.strokeStyle="rgba(221,240,230,.58)";ctx.lineWidth=1;ctx.strokeRect(pad,pad,pw,ph);ctx.beginPath();ctx.moveTo(pad+pw/2,pad);ctx.lineTo(pad+pw/2,pad+ph);ctx.stroke();ctx.beginPath();ctx.arc(pad+pw/2,pad+ph/2,ph*.09,0,Math.PI*2);ctx.stroke();const boxW=pw*.145,boxH=ph*.57;ctx.strokeRect(pad,pad+(ph-boxH)/2,boxW,boxH);ctx.strokeRect(pad+pw-boxW,pad+(ph-boxH)/2,boxW,boxH);}

function toggleFilters(force){const panel=$("#filters-panel"),open=force??panel.hidden;panel.hidden=!open;$("#filter-toggle").setAttribute("aria-expanded",String(open));}
function updateFilterCount(){let count=0;if($("#candidate-competition").value)count++;if($("#candidate-position").value)count++;for(const id of ["#age-min","#age-max","#min-profile","#min-coverage"])if(Number($(id).value)>0)count++;count+=3-$$('input[name="tier"]:checked').length;if($("#include-low-confidence").checked)count++;$("#filter-count").textContent=count;}
function matchLabels(result){return(result.top_matching_dimensions||[]).map(item=>displayDimension(item.dimension)).slice(0,3).join(" · ")||"Limited comparable evidence";}
function displayDimension(value){return({"Chance creation":"Creation","Spatial role":"Spatial role","Goal threat":"Goal threat"})[value]||value;}
function grade(score){if(score==null)return"—";if(score>=90)return"A+";if(score>=85)return"A";if(score>=80)return"A-";if(score>=75)return"B+";if(score>=70)return"B";if(score>=65)return"B-";return"C";}
function shortPosition(position){return String(position||"—").replaceAll("_"," ").split(" | ")[0];}
function scoreTile(label,valueText){return`<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(valueText)}</strong></div>`;}
function mapLabel(key){return({all:"All actions",shots:"Shots",goals:"Goals",chances:"Chances",passes:"Passes",defence:"Defence",receipts:"Receipts",carries:"Carries",progressions:"Progressions",dribbles:"Dribbles"})[key]||key;}
function heatColor(value){if(value<.35)return`rgba(18,99,57,${.28+value})`;if(value<.7)return`rgba(68,229,143,${.34+value*.68})`;return`rgba(235,255,121,${.5+value*.5})`;}
function initials(name){return String(name).split(/\s+/).slice(0,2).map(part=>part[0]).join("").toUpperCase();}
function value(item,digits=1){return item==null||!Number.isFinite(Number(item))?"—":Number(item).toFixed(digits);}
function signedValue(item,digits=1){if(item==null||!Number.isFinite(Number(item)))return"—";const number=Number(item);return`${number>0?"+":""}${number.toFixed(digits)}`;}
function percentage(item){return item==null||!Number.isFinite(Number(item))?"—":`${Number(item).toFixed(0)}%`;}
function debounce(fn,delay){let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay);};}
function escapeHtml(value){return String(value??"").replace(/[&<>'"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);}
function toast(message){const element=$("#toast");element.textContent=message;element.classList.add("show");setTimeout(()=>element.classList.remove("show"),4000);}
function handleError(error){toast(error.message);if(error.status===401)showLogin();}

async function proxy(endpoint,{method="GET",body=null,query={}}={}){const params=new URLSearchParams({endpoint,...query});return fetchJson(`/api/scoutprint?${params}`,{method,headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});}
async function fetchJson(url,options={}){const response=await fetch(url,options);const payload=await response.json().catch(()=>({}));if(!response.ok){const error=new Error(payload.detail||payload.error||`Request failed (${response.status})`);error.status=response.status;throw error;}return payload;}
