'use strict';
(function () {
  const editor = document.querySelector('[data-theme-editor]');
  if (!editor) return;
  const q = s => editor.querySelector(s);
  const layout=window.FluxLayout.create(editor,()=>update(true));
  const radio = q('[data-editor-custom]'), border = q('[data-editor-border]'), rail = q('[data-editor-rail]');
  const grid = q('[data-editor-pixels]'), focus = q('[data-editor-focus]'), code = q('[data-editor-code]');
  const library = q('[data-editor-library]'), name = q('[data-editor-name]'), message = q('[data-editor-message]');
  const key = 'flux-theme-library-v1';
  const layers = window.FluxLayers.create(editor,q('[data-editor-screen]'),{active:setActive,update,legacy:()=>({border:border.checked,rail:rail.checked,rows})});
  function valid(token) {
    if (typeof token!=='string'||token.length>13400) return false;
    const m=token.match(/^custom-([01]{2})-([0-9a-f]{16})(?:-([01][0-3][0-2][0-2]|[01][0-3]3[0-2]-m[0-9a-f]{28}))?(?:-b([0-9a-f]{240}))?(?:-(l[^-]+))?(?:-f([0-9a-f]{264}))?(?:-w([0-9a-f]{30}|[0-9a-f]{100}|[0-9a-f]{150}|[0-9a-f]{290}|[0-9a-f]{320}))?$/);
    if(!m||m[2].match(/../g).some(x=>parseInt(x,16)&1))return false;
    try {
      const ps=m[5]?window.FluxLayers.parse(m[5]):null;
      if(m[4]){
        const b=m[4].match(/../g).map(x=>parseInt(x,16));
        for(let i=0;i<120;i+=24){const g=b.slice(i,i+24);if(!g.some(Boolean)||g.some((x,j)=>j%3===2&&(x&127)))return false;}
      }
      if(ps&&ps.slice(1).some(p=>p.some(Boolean)&&!p.includes(1)))return false;
      if(Number(m[1])===0&&parseInt(m[2],16)===0&&(!ps||!ps.slice(1).every(p=>p.includes(1))))return false;
      if(m[3]&&m[3].includes('-m')){
        const bytes=m[3].split('-m')[1].match(/../g).map(x=>parseInt(x,16));
        if(bytes.some(x=>x&7)||!bytes.slice(0,7).some(Boolean)||!bytes.slice(7).some(Boolean))return false;
      }
      return true;
    }catch(_){return false;}
  }
  let rows=Array(8).fill(0),active=0,saved=[];
  const widgets=window.FluxWidgets.create(editor,()=>update(true),()=>update(false));
  function setActive(x){active=x;editor.querySelectorAll('[data-editor-vfo]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.editorVfo)===active)));}
  try { saved = JSON.parse(localStorage.getItem(key) || '[]').filter(x => x && typeof x.name === 'string' && valid(x.token)); } catch (_) {}
  const buttons = [];
  for (let y=0; y<8; y++) for (let x=0; x<7; x++) {
    const b = document.createElement('button');
    b.type = 'button'; b.setAttribute('aria-label', 'Pixel '+(x+1)+', '+(y+1));
    b.addEventListener('click', () => { rows[y] ^= 128 >> x; update(true); });
    grid.append(b); buttons.push(b);
  }
  function rect(x,y,w,h) {
    const el = document.createElementNS('http://www.w3.org/2000/svg','rect');
    for (const [k,v] of Object.entries({x,y,width:w,height:h})) el.setAttribute(k,v);
    focus.append(el);
  }
  function update(select) {
    const token = 'custom-'+Number(border.checked)+Number(rail.checked)+'-'+rows.map(x=>x.toString(16).padStart(2,'0')).join('')+widgets.suffix()+layers.suffix()+layout.suffix();
    radio.value = token; code.value = token;
    focus.replaceChildren();
    const top = active ? 40 : 8;
    if (layers.showLegacy(active)&&(border.checked||(!rail.checked&&!rows.some(Boolean)))) rect(0,top,128,1);
    if (layers.showLegacy(active)&&rail.checked) rect(0,top+1,1,22);
    buttons.forEach((b,i) => {
      const x=i%7,y=Math.floor(i/7), on=!!(rows[y] & (128>>x));
      b.setAttribute('aria-pressed', String(on));
      if(on&&layers.showLegacy(active)) rect(x+2,top+y,1,1);
    });
    widgets.render();
    layers.render(active);
    if(select) {
      radio.checked=true;
      radio.dispatchEvent(new Event('change',{bubbles:true}));
      message.textContent=valid(token) ? 'Custom theme selected.' : 'Add a visible marker or border before building.';
    }
  }
  function load(token, select) {
    if (!valid(token)) return;
    border.checked=token[7]==='1'; rail.checked=token[8]==='1';
    const parts=token.split('-'); rows=parts[2].match(/../g).map(x=>parseInt(x,16));
    const w=parts.at(-1).startsWith('w')?parts.pop().slice(1):''; const f=parts.at(-1).startsWith('f')?parts.pop().slice(1):'';layout.load(w,f);
    const l=parts.at(-1).startsWith('l')?parts.pop():'';
    layers.load(l);widgets.load(parts.slice(3));update(select);
  }
  function refresh() {
    library.replaceChildren(new Option('Choose saved theme',''));
    saved.forEach((item,i)=>library.add(new Option(item.name,String(i))));
  }
  function persist() {
    try { localStorage.setItem(key,JSON.stringify(saved)); refresh(); return true; }
    catch(_) { message.textContent='Browser storage unavailable. Keep the theme code to reuse it.'; return false; }
  }
  border.addEventListener('change',()=>update(true)); rail.addEventListener('change',()=>update(true));
  editor.querySelectorAll('[data-editor-vfo]').forEach(b=>b.addEventListener('click',()=>{
    setActive(Number(b.dataset.editorVfo));
    editor.querySelectorAll('[data-editor-vfo]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
    update(false);
  }));
  editor.querySelectorAll('[data-editor-preset]').forEach(b=>b.addEventListener('click',()=>{
    rows=({arrow:[192,240,252,254,252,240,192,0],diamond:[16,56,124,254,124,56,16,0],clear:Array(8).fill(0)})[b.dataset.editorPreset].slice();
    update(true);
  }));
  q('[data-editor-save]').addEventListener('click',()=>{
    const n=name.value.trim();
    if(!n || !valid(radio.value)) { message.textContent='Enter a name and make a visible indicator.'; return; }
    const i=saved.findIndex(x=>x.name===n), item={name:n,token:radio.value};
    if(i<0) saved.push(item); else saved[i]=item;
    if(persist()) { library.value=String(saved.findIndex(x=>x.name===n)); message.textContent='Saved '+n+' in this browser.'; }
  });
  library.addEventListener('change',()=>{
    if(library.value==='') return;
    const item=saved[Number(library.value)]; if(!item) return;
    name.value=item.name; load(item.token,true);
  });
  q('[data-editor-delete]').addEventListener('click',()=>{
    if(library.value==='') return;
    saved.splice(Number(library.value),1);
    if(persist()) { name.value=''; message.textContent='Saved theme deleted; current design retained.'; }
  });
  q('[data-editor-import]').addEventListener('click',()=>{
    const token=code.value.trim();
    if(!valid(token)) { message.textContent='Invalid theme code. Check the marker, layout and layers.'; return; }
    load(token,true); name.value=''; library.value='';
  });
  q('[data-editor-file]').addEventListener('change',async e=>{
    const file=e.target.files[0]; if(!file)return;
    if(file.size>8192){message.textContent='Theme exceeds 8 KiB.';return;}
    try {
      const data=new FormData();data.append('theme',file);
      const r=await fetch('/themes/import',{method:'POST',body:data}),j=await r.json();
      if(!r.ok||!valid(j.theme))throw Error(j.error||'Invalid theme');
      load(j.theme,true);name.value=file.name.replace(/\.[^.]+$/,'');message.textContent='Imported '+file.name;
    }catch(err){message.textContent=err.message;}finally{e.target.value='';}
  });
  q('[data-editor-export]').addEventListener('click',async ()=>{
    try {
      const data=new FormData();data.append('theme',radio.value);
      const r=await fetch('/themes/export',{method:'POST',body:data});
      if(!r.ok)throw Error((await r.json()).error||'Export failed');
      const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');
      a.href=url;a.download=(name.value.trim()||'flux-theme')+'.fluxtheme';a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      message.textContent='Theme package exported. Load it in the simulator.';
    }catch(err){message.textContent=err.message;}
  });
  const base = q('[data-editor-base]');
  function loadBase(token, select) {
    if (!valid(token)) return;
    load(token, select);
    name.value = ''; library.value = '';
    base.value = token;
  }
  q('[data-editor-load-base]').addEventListener('click', () => loadBase(base.value, true));
  document.querySelectorAll('[data-builder-themes] input[name="theme"]').forEach(b => {
    b.addEventListener('change', () => {
      if (!b.checked) return;
      const option = [...base.options].find(o => o.dataset.themeId === b.value);
      if (option) loadBase(option.value, false);
    });
  });
  refresh(); if(valid(radio.value)) load(radio.value,false); else update(false);
  base.value = radio.value;
})();

