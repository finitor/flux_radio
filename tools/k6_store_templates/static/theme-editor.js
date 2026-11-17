'use strict';
(function () {
  const editor = document.querySelector('[data-theme-editor]');
  if (!editor) return;
  const q = s => editor.querySelector(s);
  const radio = q('[data-editor-custom]'), border = q('[data-editor-border]'), rail = q('[data-editor-rail]');
  const grid = q('[data-editor-pixels]'), focus = q('[data-editor-focus]'), code = q('[data-editor-code]');
  const library = q('[data-editor-library]'), name = q('[data-editor-name]'), message = q('[data-editor-message]');
  const key = 'flux-theme-library-v1';
  const valid = token => /^custom-[01]{2}-[0-9a-f]{16}$/.test(token) &&
    token.slice(10).match(/../g).every(x => !(parseInt(x, 16) & 1)) &&
    token !== 'custom-00-0000000000000000';
  let rows = Array(8).fill(0), active = 0, saved = [];
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
    const token = 'custom-'+Number(border.checked)+Number(rail.checked)+'-'+rows.map(x=>x.toString(16).padStart(2,'0')).join('');
    radio.value = token; code.value = token;
    focus.replaceChildren();
    const top = active ? 40 : 8;
    if (border.checked) rect(0,top,128,1);
    if (rail.checked) rect(0,top+1,1,22);
    buttons.forEach((b,i) => {
      const x=i%7,y=Math.floor(i/7), on=!!(rows[y] & (128>>x));
      b.setAttribute('aria-pressed', String(on));
      if(on) rect(x+2,top+y,1,1);
    });
    if(select) {
      radio.checked=true;
      radio.dispatchEvent(new Event('change',{bubbles:true}));
      message.textContent=valid(token) ? 'Custom theme selected for the next build.' : 'Add a visible marker or border before building.';
    }
  }
  function load(token, select) {
    if (!valid(token)) return;
    border.checked=token[7]==='1'; rail.checked=token[8]==='1';
    rows=token.slice(10).match(/../g).map(x=>parseInt(x,16)); update(select);
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
    active=Number(b.dataset.editorVfo);
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
    if(!valid(token)) { message.textContent='Invalid theme code. Check the flags and eight pixel rows.'; return; }
    load(token,true); name.value=''; library.value='';
  });
  refresh(); if(valid(radio.value)) load(radio.value,false); else update(false);
})();

