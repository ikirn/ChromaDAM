'use strict';
const $ = (id) => document.getElementById(id);
const state = {view: 'library', assets: [], detail: null, cutout: false, refining: false, similar: '', revision: 0, health: null, uploading: false};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let searchController, toastTimer, inputTimer, contrastRevision = 0;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail); } catch {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}
function json(method, body) {return {method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)};}
function toast(message) {clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false; toastTimer = setTimeout(() => $('toast').hidden = true, 5000);}
function showDialog(id) {if (!$(id).open) $(id).showModal();}
function setNotice(message) {$('notice').textContent = message; $('notice').hidden = !message;}

async function refreshHealth() {
  const data = await api('/api/health');
  state.health = data;
  $('total-stat').textContent = data.assets;
  $('nav-count').textContent = data.assets;
  $('fav-count').textContent = data.favorites;
  $('indexed-stat').textContent = data.indexed;
  $('engine-stat').textContent = data.ai.sam_ready && data.ai.clip_ready ? 'AI engines available' : 'Baseline mode active';
  $('engine-sub').textContent = `${data.ai.segmentation} · ${data.ai.search}`;
  $('sam-state').textContent = data.ai.segmentation;
  $('clip-state').textContent = data.ai.search;
  $('reindex-btn').disabled = !data.ai.clip_ready;
  $('pipeline-index-info').textContent = `${data.indexed} of ${data.assets} assets have CLIP embeddings. Semantic searches exclude assets without embeddings; rebuild the index after AI setup.`;
  const errors = Object.entries(data.ai.errors).map(([key,value]) => `${key}: ${value}`).join(' · ');
  $('pipeline-errors').textContent = errors;
  $('pipeline-errors').hidden = !errors;
  return data;
}

async function loadAssets() {
  searchController?.abort();
  const controller = searchController = new AbortController();
  const params = new URLSearchParams({q:$('query').value, sort:$('sort').value,
    min_percentage:$('minimum').value || '0', tolerance:$('tolerance').value || '25'});
  const family = $('color-family').value;
  if (family) params.set('color', family === 'custom' ? $('color-picker').value : family);
  if (state.view === 'favorites') params.set('favorite','true');
  if (state.similar) params.set('similar_to',state.similar);
  try {
    const data = await api(`/api/assets?${params}`, {signal:controller.signal});
    if (controller !== searchController) return;
    state.assets = data.items;
    renderAssets(data);
    const notices = [];
    if (data.mode === 'keyword fallback') notices.push('Keyword mode: searching file names and tags. Install the AI models for visual and natural-language search.');
    if (data.unindexed) notices.push(`${data.unindexed} matching assets have no CLIP embeddings. Rebuild missing embeddings on the AI pipeline page.`);
    if (data.filters.color?.startsWith('#')) notices.push(`Hex matching uses ΔE76 ≤ ${data.filters.tolerance} between the chosen color and palette averages.`);
    setNotice(notices.join(' '));
  } catch (error) {
    if (error.name !== 'AbortError') {setNotice(error.message); toast(error.message);}
  }
}

function renderAssets(data) {
  $('results-count').textContent = data.total;
  $('footer-count').textContent = `${data.total} ${data.total === 1 ? 'asset' : 'assets'} shown`;
  $('colors-stat').textContent = data.items.reduce((sum,a) => sum+a.palette.length,0);
  $('search-mode').textContent = state.similar ? 'Visually similar assets · CLIP' : data.mode === 'browse' ? 'Your visual collection' : `${data.mode} · ranked results`;
  $('empty').hidden = data.total > 0;
  const searching = $('query').value || $('color-family').value || state.similar || state.view === 'favorites';
  $('empty').querySelector('h2').textContent = searching ? 'No matches in this shade of the library.' : 'A blank canvas, full of possibilities.';
  $('empty').querySelector('p').textContent = searching ? 'Try another description, lower the color percentage, or reset your filters.' : 'Upload your first image to discover its subject, palette, and visual story.';
  $('asset-grid').innerHTML = data.items.map(a => `<article class="asset-card">
    <button class="favorite-button ${a.favorite?'is-favorite':''}" data-fav="${a.id}" aria-label="${a.favorite?'Remove from':'Add to'} favorites" aria-pressed="${a.favorite}"><svg><use href="#i-star"/></svg></button>
    <button class="asset-open" data-open="${a.id}" aria-label="Inspect ${esc(a.name)}">
      <div class="asset-image"><img src="${a.image_url}" alt="${esc(a.name)}" loading="lazy"><span class="asset-type">${esc(a.name.split('.').pop().slice(0,5).toUpperCase())}</span></div>
      <div class="asset-card-body"><div class="asset-title"><h3>${esc(a.name)}</h3><span>${a.width} × ${a.height}</span></div><div class="asset-card-meta">${esc(a.tags?.length ? a.tags.slice(0,3).join(' · ') : 'Ready to explore')} · ${Math.max(1,Math.round(a.bytes/1024))} KB</div><div class="mini-palette">${a.palette.map(p=>`<i style="background:${p.hex}" title="${p.hex} · ${p.percentage.toFixed(1)}%"></i>`).join('')}<span>${a.palette.length} colors</span></div></div>
      <div class="asset-card-footer"><span class="method">${esc(a.method)}</span><span>${a.matched_percentage != null ? `${a.matched_percentage.toFixed(1)}% color match` : a.similarity != null ? `Similarity ${a.similarity.toFixed(3)}` : 'View palette'} <span class="arrow">↗</span></span></div>
    </button></article>`).join('');
}

function switchView(view) {
  state.view = view;
  for (const id of ['library','lab','pipeline']) $(`${id}-view`).hidden = id !== (view === 'favorites' ? 'library' : view);
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view === view));
  $('breadcrumb').textContent = {library:'Asset library',favorites:'Favorites',lab:'Color & accessibility',pipeline:'AI pipeline'}[view];
  if (view === 'library' || view === 'favorites') {$('all-tab').firstChild.textContent = view === 'favorites' ? 'Favorites ' : 'All assets '; loadAssets();}
  if (view === 'lab') updateContrast();
  if (view === 'pipeline') refreshHealth().catch(e=>toast(e.message));
}

async function uploadFiles(files) {
  if (state.uploading) {toast('Please wait for the current upload batch to finish.');return;}
  const images = [...files];
  if (!images.length) return;
  state.uploading = true;
  showDialog('upload-dialog');
  $('upload-progress').replaceChildren();
  $('upload-zone').style.opacity = '.5';
  try {
    for (const file of images) {
      const row = document.createElement('div');row.className = 'upload-progress-item';
      const name = document.createElement('span');name.textContent = file.name;
      const result = document.createElement('span');result.textContent = 'Analyzing…';row.append(name,result);$('upload-progress').append(row);
      const started = Date.now();
      const progressTimer = setInterval(() => {
        const seconds = Math.floor((Date.now() - started) / 1000);
        result.textContent = seconds < 15 ? `Analyzing · ${seconds}s` : `Processing on CPU · ${seconds}s`;
      }, 1000);
      try {
        if (file.size > 20*1024*1024) throw new Error('Exceeds 20 MB');
        const form = new FormData();form.append('file',file);
        const asset = await api(`/api/assets?k=${$('cluster-count').value}`,{method:'POST',body:form});
        clearInterval(progressTimer);
        result.textContent = `✓ ${asset.method} · ${Math.round((Date.now() - started) / 1000)}s`;
        await Promise.all([loadAssets(),refreshHealth()]);
      } catch(e) {clearInterval(progressTimer);result.textContent = `Failed: ${e.message}`;result.style.color = '#b05651';}
    }
  } finally {state.uploading=false;$('upload-zone').style.opacity='1';$('file-input').value='';}
}

async function openDetail(id) {
  try {state.detail=await api(`/api/assets/${id}`);state.cutout=false;state.refining=false;renderDetail();showDialog('detail-dialog');}
  catch(e){toast(e.message);}
}
function renderDetail() {
  const a=state.detail;if(!a)return;
  $('detail-name').textContent=a.name;$('edit-name').value=a.name;$('edit-tags').value=(a.tags||[]).join(', ');
  $('coverage').textContent=`${a.coverage.toFixed(1)}% of image selected`;
  $('detail-method').textContent=a.method;
  $('detail-meta').textContent=`${a.width} × ${a.height} px · Uploaded ${new Date(a.created).toLocaleDateString()} · ${a.palette.length} dominant colors`;
  $('detail-confidence').textContent=a.sam_score != null ? `MobileSAM mask quality score: ${a.sam_score.toFixed(3)}. Raw model output, not a measured accuracy; inspect the cutout for correctness.` : a.method === 'Image alpha' ? 'Foreground comes from the image’s existing transparency.' : a.method === 'Full image (uniform color)' ? 'This is a solid-color image with no distinguishable subject. The palette describes the entire image.' : 'Baseline segmentation was used. Install AI models for MobileSAM analysis.';
  $('ratio-bar').innerHTML=a.palette.map(p=>`<i style="background:${p.hex};flex:${p.percentage}" title="${p.hex} ${p.percentage.toFixed(1)}%"></i>`).join('');
  $('swatches').innerHTML=a.palette.map(p=>`<div class="swatch-row"><span class="swatch-chip" style="background:${p.hex}"></span><button data-copy="${p.hex}" aria-label="Copy ${p.hex}">${p.hex}<small>RGB ${p.rgb.join(', ')} · ${p.family}</small></button><span>${p.percentage.toFixed(1)}%</span></div>`).join('');
  for (const format of ['json','tailwind','css']) $(`export-${format}`).href=`/api/assets/${a.id}/export?format=${format}`;
  $('download-cutout').href=a.cutout_url;
  $('detail-favorite').textContent=a.favorite?'★ Favorited':'☆ Favorite';
  $('detail-favorite').setAttribute('aria-pressed',String(a.favorite));
  $('similar-btn').disabled=!state.health?.ai.clip_ready;
  updateDetailImage();
}
function updateDetailImage(){
  const a=state.detail;
  $('detail-image').src=(state.cutout?a.cutout_url:a.image_url)+`?v=${state.revision}`;
  $('detail-image').classList.toggle('refining',state.refining);
  $('detail-image-wrap').classList.toggle('checker',state.cutout);
  $('original-tab').classList.toggle('selected',!state.cutout);$('cutout-tab').classList.toggle('selected',state.cutout);
  $('refine-btn').textContent=state.refining?'Cancel refinement':'Refine subject';
  $('refine-hint').textContent=state.refining?'Click on the main subject in the image. The background will be removed again.':'Need a better mask? Select “Refine subject”, then click your subject.';
}

async function updateContrast(){
  const revision=++contrastRevision, fg=$('fg').value,bg=$('bg').value;
  $('fg-value').textContent=fg.toUpperCase();$('bg-value').textContent=bg.toUpperCase();
  $('contrast-preview').style.color=fg;$('contrast-preview').style.background=bg;
  try{
    const result=await api(`/api/contrast?${new URLSearchParams({foreground:fg,background:bg})}`);
    if(revision!==contrastRevision)return;
    $('ratio').textContent=result.ratio.toFixed(2);
    $('contrast-results').innerHTML=[['AA · Normal text','aa_normal'],['AA · Large text','aa_large'],['AAA · Normal text','aaa_normal'],['AAA · Large text','aaa_large']].map(([label,key])=>`<div class="contrast-result">${label}<span class="${result[key]?'pass':'fail'}">${result[key]?'✓ Pass':'✕ Fail'}</span></div>`).join('');
  }catch(e){toast(e.message);}
}

document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close).close()));
for(const id of ['guide-btn','help-btn']) $(id).addEventListener('click',()=>showDialog('guide-dialog'));
for(const id of ['upload-btn','empty-upload']) $(id).addEventListener('click',()=>showDialog('upload-dialog'));
$('upload-zone').addEventListener('click',()=>$('file-input').click());
$('upload-zone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('file-input').click();}});
$('file-input').addEventListener('change',e=>uploadFiles(e.target.files));
let dragDepth=0;
document.addEventListener('dragenter',e=>{if([...e.dataTransfer.types].includes('Files')){e.preventDefault();dragDepth++;$('drop-overlay').hidden=false;}});
document.addEventListener('dragover',e=>{if([...e.dataTransfer.types].includes('Files'))e.preventDefault();});
document.addEventListener('dragleave',e=>{e.preventDefault();if(--dragDepth<=0){dragDepth=0;$('drop-overlay').hidden=true;}});
document.addEventListener('drop',e=>{e.preventDefault();dragDepth=0;$('drop-overlay').hidden=true;if(e.dataTransfer.files.length){if($('detail-dialog').open)$('detail-dialog').close();if($('guide-dialog').open)$('guide-dialog').close();uploadFiles(e.dataTransfer.files);}});
$('search-form').addEventListener('submit',e=>{e.preventDefault();state.similar='';loadAssets();});
$('query').addEventListener('input',()=>{clearTimeout(inputTimer);inputTimer=setTimeout(()=>{state.similar='';loadAssets();},450);});
for(const id of ['minimum','tolerance']) $(id).addEventListener('change',()=>{if($(id).checkValidity())loadAssets();else $(id).reportValidity();});
$('sort').addEventListener('change',loadAssets);
$('color-family').addEventListener('change',()=>{const custom=$('color-family').value==='custom';$('color-picker').hidden=!custom;$('tolerance-wrap').hidden=!custom;loadAssets();});
$('color-picker').addEventListener('change',loadAssets);
$('reset-btn').addEventListener('click',()=>{$('query').value='';$('color-family').value='';$('minimum').value=0;$('color-picker').hidden=true;$('tolerance-wrap').hidden=true;state.similar='';loadAssets();});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)&&!document.querySelector('dialog[open]')){e.preventDefault();switchView('library');$('query').focus();}});
$('asset-grid').addEventListener('click',async e=>{const fav=e.target.closest('[data-fav]');if(fav){try{const a=state.assets.find(a=>a.id===fav.dataset.fav);await api(`/api/assets/${a.id}`,json('PATCH',{favorite:!a.favorite}));await Promise.all([loadAssets(),refreshHealth()]);}catch(error){toast(error.message);}return;}const open=e.target.closest('[data-open]');if(open)openDetail(open.dataset.open);});
$('original-tab').addEventListener('click',()=>{state.cutout=false;updateDetailImage();});
$('cutout-tab').addEventListener('click',()=>{state.cutout=true;state.refining=false;updateDetailImage();});
$('refine-btn').addEventListener('click',()=>{state.refining=!state.refining;state.cutout=false;updateDetailImage();});
$('detail-image').addEventListener('click',async e=>{
  if(!state.refining)return;
  const rect=e.target.getBoundingClientRect(),assetId=state.detail.id;
  state.refining=false;$('refine-btn').disabled=true;$('refine-hint').textContent='Refining the subject and recalculating its palette…';
  try{state.detail=await api(`/api/assets/${assetId}/segment`,json('POST',{x:(e.clientX-rect.left)/rect.width,y:(e.clientY-rect.top)/rect.height,k:state.detail.palette.length < 3 ? 5:state.detail.palette.length}));state.cutout=true;state.revision++;renderDetail();await Promise.all([loadAssets(),refreshHealth()]);toast('Subject and palette updated.');}
  catch(error){toast(error.message);updateDetailImage();}finally{$('refine-btn').disabled=false;}
});
$('swatches').addEventListener('click',async e=>{const b=e.target.closest('[data-copy]');if(b){try{await navigator.clipboard.writeText(b.dataset.copy);toast(`${b.dataset.copy} copied`);}catch{toast(`Color: ${b.dataset.copy}`);}}});
$('save-details').addEventListener('click',async()=>{try{state.detail=await api(`/api/assets/${state.detail.id}`,json('PATCH',{name:$('edit-name').value,tags:$('edit-tags').value.split(',').map(x=>x.trim()).filter(Boolean)}));renderDetail();await loadAssets();toast('Asset details saved.');}catch(e){toast(e.message);}});
$('detail-favorite').addEventListener('click',async()=>{try{state.detail=await api(`/api/assets/${state.detail.id}`,json('PATCH',{favorite:!state.detail.favorite}));renderDetail();await Promise.all([loadAssets(),refreshHealth()]);}catch(e){toast(e.message);}});
$('similar-btn').addEventListener('click',()=>{state.similar=state.detail.id;$('query').value='';$('detail-dialog').close();switchView('library');});
$('delete-btn').addEventListener('click',async()=>{if(!confirm(`Delete “${state.detail.name}” from this local library?`))return;try{await api(`/api/assets/${state.detail.id}`,{method:'DELETE'});$('detail-dialog').close();state.detail=null;await Promise.all([loadAssets(),refreshHealth()]);toast('Asset deleted.');}catch(e){toast(e.message);}});
for(const id of ['fg','bg']) $(id).addEventListener('input',updateContrast);
$('reindex-btn').addEventListener('click',async()=>{const button=$('reindex-btn');button.disabled=true;button.textContent='Indexing assets…';try{const result=await api('/api/reindex',{method:'POST'});toast(`${result.indexed} missing embeddings added.`);}catch(e){toast(e.message);}finally{button.textContent='Rebuild missing embeddings';await refreshHealth().catch(e=>toast(e.message));}});

(async()=>{try{await refreshHealth();await loadAssets();}catch(e){setNotice(`Cannot reach the local API. ${e.message}`);$('engine-stat').textContent='Server unavailable';}})();
