const $=s=>document.querySelector(s), esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const form=$('#uploadForm'), file=$('#document');
let runCache=new Map();
file.onchange=()=>$('#filename').textContent=file.files[0]?.name||'No file selected';
function loading(on){$('#progress').classList.toggle('hidden',!on);form.querySelector('button').disabled=on}
function hideError(){$('#error').classList.add('hidden')}
function showError(message){
  $('#error').innerHTML=`<span>${esc(message)}</span><button type="button" class="close-button" aria-label="Close error">×</button>`;
  $('#error').classList.add('dismissible');
  $('#error').classList.remove('hidden');
  $('#error .close-button').onclick=hideError;
}
function render(run,fromHistory=false){
  $('#result').classList.remove('hidden'); $('#outcome').textContent=run.decision.outcome.replaceAll('_',' ');
  let loadedNotice=$('#loadedNotice');
  if(!loadedNotice){
    loadedNotice=document.createElement('div');
    loadedNotice.id='loadedNotice';
    loadedNotice.className='loaded-notice hidden';
    $('#result').prepend(loadedNotice);
  }
  loadedNotice.innerHTML=fromHistory?`<span>Loaded complete saved data for ${esc(run.filename)}</span>`:'';
  loadedNotice.classList.toggle('hidden',!fromHistory);
  $('#closeResult').onclick=()=>{
    $('#result').classList.add('hidden');
    if(fromHistory)document.querySelector('.history').scrollIntoView({behavior:'smooth',block:'start'});
  };
  $('#reasoning').textContent=run.decision.reasoning; $('#customer').textContent=run.validation.customer;
  const s=run.validation.summary; $('#counts').innerHTML=['match','mismatch','uncertain'].map(k=>`<div class="count"><b>${s[k]}</b>${k}</div>`).join('');
  $('#fields').innerHTML=run.validation.results.map(r=>`<div class="field"><div><div class="fieldname">${esc(r.field.replaceAll('_',' '))}</div><div class="evidence">“${esc(r.evidence)}” · page ${esc(r.page)}</div></div><div><b>${esc(r.found)}</b><div class="meter"><i style="width:${r.confidence*100}%"></i></div><div class="evidence">${Math.round(r.confidence*100)}% confidence${r.expected?' · expected '+esc(r.expected):''}</div></div><span class="status ${r.status}">${r.status}</span></div>`).join('');
  $('#trace').innerHTML=[['Extractor','Evidence-bound fields captured'],['Validator',`${s.match} match · ${s.mismatch} mismatch · ${s.uncertain} uncertain`],['Router',run.decision.outcome.replaceAll('_',' ')],['Storage','SQLite audit record committed']].map(x=>`<div class="traceitem"><b>${x[0]}</b><span>${x[1]}</span></div>`).join('');
  $('#draftWrap').classList.toggle('hidden',!run.decision.draft_amendment); $('#draft').value=run.decision.draft_amendment||'';
}
form.onsubmit=async e=>{e.preventDefault();hideError();loading(true);try{const data=new FormData(form),res=await fetch('/api/process',{method:'POST',body:data}),body=await res.json();if(!res.ok)throw Error(body.error);render(body);loadRuns()}catch(e){showError(e.message)}finally{loading(false)}};
$('#queryForm').onsubmit=async e=>{e.preventDefault();const res=await fetch('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('#question').value})}),body=await res.json();$('#answer').textContent=body.answer+' · '+body.grounding};
async function loadRuns(){
  const body=await (await fetch('/api/runs')).json();
  runCache=new Map(body.runs.map(run=>[String(run.id),run]));
  $('#runs').innerHTML=body.runs.length
    ?body.runs.map(r=>`<div class="run"><b>${esc(r.filename)}</b><span>${new Date(r.created_at).toLocaleString()}</span><span class="status ${r.decision?.outcome==='auto_approve'?'match':r.decision?.outcome==='amendment_request'?'mismatch':'uncertain'}">${esc(r.decision?.outcome||r.status)}</span><button type="button" class="run-action" data-run-id="${esc(r.id)}" ${r.decision&&r.validation&&r.extracted?'':'disabled'}>${r.decision&&r.validation&&r.extracted?'View full data':'Incomplete'}</button></div>`).join('')
    :'<p class="muted">No runs yet.</p>';
  document.querySelectorAll('.run-action[data-run-id]').forEach(button=>button.onclick=()=>{
    const run=runCache.get(button.dataset.runId);
    if(!run?.decision||!run?.validation||!run?.extracted){
      showError('This run is incomplete and has no final result to display.');
      return;
    }
    hideError();
    render(run,true);
    $('#result').scrollIntoView({behavior:'smooth',block:'start'});
  });
}
$('#refresh').onclick=loadRuns;loadRuns();
