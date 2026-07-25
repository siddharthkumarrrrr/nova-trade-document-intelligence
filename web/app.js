const $=s=>document.querySelector(s), esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const form=$('#uploadForm'), file=$('#document');
file.onchange=()=>$('#filename').textContent=file.files[0]?.name||'No file selected';
function loading(on){$('#progress').classList.toggle('hidden',!on);form.querySelector('button').disabled=on}
function render(run){
  $('#result').classList.remove('hidden'); $('#outcome').textContent=run.decision.outcome.replaceAll('_',' ');
  $('#reasoning').textContent=run.decision.reasoning; $('#customer').textContent=run.validation.customer;
  const s=run.validation.summary; $('#counts').innerHTML=['match','mismatch','uncertain'].map(k=>`<div class="count"><b>${s[k]}</b>${k}</div>`).join('');
  $('#fields').innerHTML=run.validation.results.map(r=>`<div class="field"><div><div class="fieldname">${esc(r.field.replaceAll('_',' '))}</div><div class="evidence">“${esc(r.evidence)}” · page ${esc(r.page)}</div></div><div><b>${esc(r.found)}</b><div class="meter"><i style="width:${r.confidence*100}%"></i></div><div class="evidence">${Math.round(r.confidence*100)}% confidence${r.expected?' · expected '+esc(r.expected):''}</div></div><span class="status ${r.status}">${r.status}</span></div>`).join('');
  $('#trace').innerHTML=[['Extractor','Evidence-bound fields captured'],['Validator',`${s.match} match · ${s.mismatch} mismatch · ${s.uncertain} uncertain`],['Router',run.decision.outcome.replaceAll('_',' ')],['Storage','SQLite audit record committed']].map(x=>`<div class="traceitem"><b>${x[0]}</b><span>${x[1]}</span></div>`).join('');
  $('#draftWrap').classList.toggle('hidden',!run.decision.draft_amendment); $('#draft').value=run.decision.draft_amendment||'';
}
form.onsubmit=async e=>{e.preventDefault();$('#error').classList.add('hidden');loading(true);try{const data=new FormData(form),res=await fetch('/api/process',{method:'POST',body:data}),body=await res.json();if(!res.ok)throw Error(body.error);render(body);loadRuns()}catch(e){$('#error').textContent=e.message;$('#error').classList.remove('hidden')}finally{loading(false)}};
$('#queryForm').onsubmit=async e=>{e.preventDefault();const res=await fetch('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('#question').value})}),body=await res.json();$('#answer').textContent=body.answer+' · '+body.grounding};
async function loadRuns(){const body=await (await fetch('/api/runs')).json();$('#runs').innerHTML=body.runs.length?body.runs.map(r=>`<div class="run"><b>${esc(r.filename)}</b><span>${new Date(r.created_at).toLocaleString()}</span><span class="status ${r.decision?.outcome==='auto_approve'?'match':r.decision?.outcome==='amendment_request'?'mismatch':'uncertain'}">${esc(r.decision?.outcome||r.status)}</span></div>`).join(''):'<p class="muted">No runs yet.</p>'}
$('#refresh').onclick=loadRuns;loadRuns();
