/* Nested LCD layout authoring prototype. Integer coordinates, relative to parent. */
(function(root){
'use strict';
const NS='http://www.w3.org/2000/svg';
const defaults=[
 ['status',null,0,0,128,8],['callsign','status',16,0,30,8],['dual-watch','status',57,0,10,8],
 ['battery','status',109,0,17,8],['vfo-a',null,0,8,128,24],['vfo-b',null,0,40,128,24],
 ['signal',null,0,32,128,8],['rssi','signal',2,0,60,8],['meter','signal',62,0,65,8]
];
for(const side of ['a','b']){
 const p='vfo-'+side;
 defaults.push([p+'-marker',p,2,0,7,8],[p+'-state',p,12,0,10,8],[p+'-channel',p,2,8,30,8],
 [p+'-frequency',p,44,0,82,17],[p+'-mode',p,2,18,12,6]);
}
const modeNames=['power','tone','offset','bandwidth','reverse','break-in','repeater'];
const modeWidths=[16,24,4,16,4,20,32],modeOffsets=[13,30,55,60,77,83,83];
for(const side of ['a','b'])for(let i=0;i<7;i++)defaults.push(['vfo-'+side+'-'+modeNames[i],'vfo-'+side,2+modeOffsets[i],18,modeWidths[i],6]);
defaults.push(['power-save','status',0,0,10,8],['vox','status',84,0,10,8],['lock','status',99,0,10,8]);
const samples={'power-save':'PS',vox:'VX',lock:'LK',callsign:'AG7SU','dual-watch':'DW',battery:'▰',rssi:'-73dBm S9',meter:'▂▃▄▅▆▇▇▇▇',marker:'▸',state:'RX',channel:'VFO',mode:'FM',power:'LOW',tone:'TSQL',offset:'+',bandwidth:'NAR',reverse:'R','break-in':'BK-SE',repeater:'REV +600'};
function sample(n,state){
 if(state && Object.hasOwn(state,n.id))return state[n.id];return n.id.endsWith('frequency')?(n.id.includes('-a-')?'146.52000':'440.85000'):(samples[n.id.replace(/^vfo-[ab]-/,'')]||'');}
function visualExtent(n,state){
 const key=n.id.replace(/^vfo-[ab]-/,'');
 if(n.id.endsWith('frequency'))return {w:n.font==='custom'?72:n.font==='compact'?54:82,h:n.font==='custom'?12:n.font==='compact'?10:17};
 if(['battery','meter','marker'].includes(key))return {w:n.w,h:n.h};
 return {w:Math.max(1,sample(n,state).length)*(n.h===6?4:5),h:n.h};
}
const make=()=>defaults.map(([id,parent,x,y,w,h])=>({id,parent,x,y,w,h,font:'factory'}));
function absolute(nodes,id){
 let x=0,y=0,n=nodes.find(n=>n.id===id),guard=0;
 while(n){x+=n.x;y+=n.y;n=n.parent?nodes.find(p=>p.id===n.parent):null;if(++guard>nodes.length)throw Error('Cyclic layout');}
 return {x,y};
}
function snap(value,step){return Math.round(value/step)*step;}
function extent(nodes,id,state){
 const n=nodes.find(v=>v.id===id), kids=nodes.filter(v=>v.parent===id);
 if(!kids.length){
  const {w,h}=visualExtent(n,state);
  return {x:0,y:0,w,h};
 }
 const boxes=kids.map(k=>{const b=extent(nodes,k.id,state);return {x:k.x+b.x,y:k.y+b.y,w:b.w,h:b.h};});
 const x=Math.min(...boxes.map(b=>b.x)),y=Math.min(...boxes.map(b=>b.y));
 return {x,y,w:Math.max(...boxes.map(b=>b.x+b.w))-x,h:Math.max(...boxes.map(b=>b.y+b.h))-y};
}
function move(nodes,id,x,y,step=1,align=false,state){
 const n=nodes.find(n=>n.id===id);if(!n)throw Error('Unknown widget');
 const p=n.parent?absolute(nodes,n.parent):{x:0,y:0}, b=extent(nodes,id,state);
 x=snap(x,step);y=snap(y,step);
 if(align){
  const peers=nodes.filter(v=>v.parent===n.parent&&v.id!==id);
  function near(value,axis,span){
   const candidates=[-b[axis]-p[axis],(axis==='x'?128:64)-span-b[axis]-p[axis]];
   for(const v of peers){
    const r=extent(nodes,v.id,state);
    for(const a of [0,.5,1])for(const c of [0,.5,1])
     candidates.push(v[axis]+r[axis]+a*(axis==='x'?r.w:r.h)-b[axis]-c*span);
   }
   const closest=candidates.reduce((best,v)=>Math.abs(v-value)<Math.abs(best-value)?v:best,Infinity);
   return Math.abs(closest-value)<=2?Math.round(closest):value;
  }
  x=near(x,'x',b.w);y=near(y,'y',b.h);
 }
 n.x=Math.max(-p.x-b.x,Math.min(128-p.x-b.x-b.w,x));
 n.y=Math.max(-p.y-b.y,Math.min(64-p.y-b.y-b.h,y));
}
const childIds=['callsign','dual-watch','battery','rssi','meter',...['a','b'].flatMap(side=>['marker','state','channel','frequency','mode'].map(k=>'vfo-'+side+'-'+k)),...['a','b'].flatMap(side=>modeNames.map(k=>'vfo-'+side+'-'+k)),'power-save','vox','lock'];
function encodeGroups(nodes,children=false){
 const groups=['status','vfo-a','vfo-b','signal','battery'];
 const out=[];
 for(const id of groups){
  const p=absolute(nodes,id),f=nodes.find(n=>n.id===id+'-frequency');
  out.push(id==='battery'&&children?109:p.x,p.y,f&&f.font==='compact'?2:f&&f.font==='factory'?1:0);
 }
 if(out[12]!==109||out[13]!==out[1])throw Error('Battery must remain at the native status coordinate');
 const occupied=new Set();
 for(let i=0;i<4;i++){const h=i===1||i===2?24:8;for(let y=out[3*i+1];y<out[3*i+1]+h;y++){if(occupied.has(y)||y>=64||out[i*3]!==0)throw Error('Legacy runtime requires full-width groups');occupied.add(y);}}
 if(children){for(const id of childIds){const n=nodes.find(n=>n.id===id);if(n.x<0||n.y<0)throw Error('Legacy runtime requires positive child offsets');out.push(n.x,n.y);}out.push(0,0,0,0,0);}
 return out.map(v=>v.toString(16).padStart(2,'0')).join('');
}
function encodeFree(nodes){
 const out=[];
 for(const n of nodes.filter(v=>childIds.includes(v.id))){
  const id=n.id,p=absolute(nodes,id),b=extent(nodes,id);
  const w=n.id.endsWith('frequency')&&n.font==='custom'?72:n.id.endsWith('frequency')&&n.font==='compact'?54:n.w,h=n.id.endsWith('frequency')&&n.font==='custom'?12:n.id.endsWith('frequency')&&n.font==='compact'?10:n.h;
  if(p.x<0||p.y<0||p.x+w>128||p.y+h>64)throw Error(id+' needs room for its longest value ('+w+' × '+h+')');
  out.push(childIds.indexOf(id),p.x,p.y,n.id.endsWith('frequency')&&n.font==='custom'?2:n.id.endsWith('frequency')&&n.font==='compact'?1:0,n.opaque?1:0);
 }
 return out.map(v=>v.toString(16).padStart(2,'0')).join('');
}
function create(editor,changed){
 const q=s=>editor.querySelector(s),svg=q('[data-layout-canvas]'),tree=q('[data-layout-tree]'),controls=q('[data-layout-controls]');
 if(!svg)return;
 let nodes=make(),id='vfo-a',drag=null,enabled=false,state={},history=[],future=[];
 const preview=k=>q('[data-preview-'+k+']');
 function previewState(){
   const side=preview('active').value,rx=preview('rx').value,n=Number(preview('signal').value);
   state={callsign:preview('call').value.toUpperCase(),'dual-watch':preview('dual').checked?'DW':'','power-save':preview('save').checked?'PS':'',vox:preview('vox').checked?'VX':'',lock:preview('lock').checked?'LK':'',rssi:rx==='off'?'':(n>9?-73+(n-9)*10:-127+n*6)+'dBm '+(n>9?'+'+(n-9)*10:'S'+n)};
   for(const k of ['a','b']){
     const p='vfo-'+k+'-',get=f=>q('[data-preview-'+f+'="'+k+'"]').value;
     const hz=Number(get('frequency'));state[p+'frequency']=Number.isFinite(hz)&&hz>=0&&hz<1000?hz.toFixed(5).padStart(9,' '):sample({id:p+'frequency'});
     state[p+'state']=rx===k?'RX':'';state[p+'marker']=side===k?'>':'';
     for(const f of ['mode','power','bandwidth'])state[p+f]=get(f);
     state[p+'tone']='';state[p+'reverse']='';state[p+'offset']='';state[p+'break-in']='';state[p+'repeater']='';
   }
 }
 const snapshot=()=>({nodes:JSON.parse(JSON.stringify(nodes)),glyphs:Array.from(glyphs),hasFont,enabled});
 function remember(){history.push(snapshot());if(history.length>40)history.shift();future=[];historyButtons();}
 function historyButtons(){q('[data-layout-undo]').disabled=!history.length;q('[data-layout-redo]').disabled=!future.length;}
 function replay(from,to){if(!from.length)return;to.push(snapshot());const v=from.pop();nodes=v.nodes;glyphs=Uint8Array.from(v.glyphs);hasFont=v.hasFont;enabled=v.enabled;historyButtons();fontGrid();render();if(changed)changed();}
 q('[data-layout-undo]').onclick=()=>replay(history,future);q('[data-layout-redo]').onclick=()=>replay(future,history);
 for(const el of editor.querySelectorAll('[data-preview-active],[data-preview-rx],[data-preview-call],[data-preview-battery],[data-preview-signal],[data-preview-dual],[data-preview-save],[data-preview-vox],[data-preview-lock],[data-preview-frequency],[data-preview-mode],[data-preview-power],[data-preview-bandwidth],[data-preview-guides]'))el.addEventListener('input',()=>{previewState();render();});
 previewState();
 // Original seven-segment starter patterns, not a bundled third-party font.
 const segments=['ab cdef','bc','abdeg','abcdg','bcfg','acdfg','acdefg','abc','abcdefg','abcdfg'].map(s=>s.replaceAll(' ',''));
 const coords={a:[1,0,6,1],b:[6,1,1,5],c:[6,6,1,5],d:[1,11,6,1],e:[1,6,1,5],f:[1,1,1,5],g:[1,5,6,1]};
 const starter=()=>{const a=new Uint8Array(132);for(let d=0;d<10;d++)for(const k of segments[d]){const [x,y,w,h]=coords[k];for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++)a[d*12+j]|=128>>i;}a[10*12+10]=24;a[10*12+11]=24;return a;};
 let glyphs=starter(),hasFont=false,glyphIndex=0;
 const fontSuffix=()=>hasFont?'-f'+Array.from(glyphs,v=>v.toString(16).padStart(2,'0')).join(''):'';
 const canvas=q('[data-font-grid]'),select=q('[data-font-char]');
 function fontGrid(){canvas.replaceChildren();for(let y=0;y<12;y++)for(let x=0;x<8;x++){const b=document.createElement('button');b.type='button';b.setAttribute('aria-label','Pixel '+x+','+y);b.setAttribute('aria-pressed',String(!!(glyphs[glyphIndex*12+y]&(128>>x))));b.onclick=()=>{remember();glyphs[glyphIndex*12+y]^=128>>x;hasFont=true;fontGrid();render();notify();};canvas.append(b);}}
 for(let i=0;i<11;i++)select.add(new Option(i===10?'.':String(i),String(i)));
 select.onchange=()=>{glyphIndex=Number(select.value);fontGrid();};
 q('[data-font-reset]').onclick=()=>{remember();glyphs=starter();hasFont=true;fontGrid();render();notify();};
 q('[data-font-invert]').onclick=()=>{remember();for(let y=0;y<12;y++)glyphs[glyphIndex*12+y]^=255;hasFont=true;fontGrid();render();notify();};
 q('[data-font-clear]').onclick=()=>{remember();glyphs.fill(0,glyphIndex*12,glyphIndex*12+12);hasFont=true;fontGrid();render();notify();};
 q('[data-font-import]').onchange=async e=>{const f=e.target.files[0],msg=q('[data-font-message]');if(!f)return;try{if(f.size!==132)throw Error('Expected exactly 132 bytes (11 glyphs × 12 rows).');const bytes=new Uint8Array(await f.arrayBuffer());for(let i=0;i<132;i+=12)if(!bytes.slice(i,i+12).some(Boolean))throw Error('Every glyph must contain ink.');remember();glyphs=bytes;hasFont=true;fontGrid();render();notify();msg.textContent='Font imported.';}catch(err){msg.textContent=err.message;}finally{e.target.value='';}};
 q('[data-font-export]').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([glyphs]));a.download='flux-frequency.raw';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
 fontGrid();
 const field=k=>q('[data-layout-'+k+']'),sel=()=>nodes.find(n=>n.id===id);
 const label=n=>n.id.replace(/-mode$/,'-modulation').replace(/^vfo-([ab])-/,(_,s)=>s.toUpperCase()+' · ').replaceAll('-',' ');
 function element(tag,props){const el=document.createElementNS(NS,tag);Object.entries(props).forEach(([k,v])=>el.setAttribute(k,v));return el;}
 function render(){
  svg.replaceChildren(element('rect',{width:128,height:64,fill:'#b7c8a1'}));
  const step=Number(field('snap').value);
  if(step>1&&preview('guides').checked){const g=element('g',{stroke:'#758b71','stroke-width':'.15',opacity:'.45'});for(let x=step;x<128;x+=step)g.append(element('path',{d:'M'+x+' 0V64'}));for(let y=step;y<64;y+=step)g.append(element('path',{d:'M0 '+y+'H128'}));svg.append(g);}
  for(const n of nodes){
    const p=absolute(nodes,n.id),b=extent(nodes,n.id,state),group=element('g',{'data-widget':n.id,transform:'translate('+(p.x+b.x)+' '+(p.y+b.y)+')'});
    const isGroup=nodes.some(c=>c.parent===n.id);
    const r=element('rect',{width:b.w,height:b.h,fill:isGroup?'none':'#b7c8a1','fill-opacity':n.opaque?'1':'0',stroke:preview('guides').checked?(n.id===id?'#2467c3':'#69866c'):'none','stroke-width':n.id===id?'.7':'.25','stroke-dasharray':isGroup?'2 1':'none','pointer-events':'all'});
    group.append(r);
    if(!isGroup){
      const value=sample(n,state);
      if(n.id==='battery'){const bars=Number(preview('battery').value);group.append(element('rect',{x:2,y:0,width:15,height:7,fill:'none',stroke:'#172211','stroke-width':1}));group.append(element('rect',{x:0,y:2,width:2,height:3,fill:'#172211'}));for(let i=0;i<bars;i++)group.append(element('rect',{x:4+(3-i)*3,y:1,width:2,height:5,fill:'#172211'}));}else if(n.id==='meter'){if(preview('rx').value!=='off')for(let i=0;i<Number(preview('signal').value);i++){const h=Math.min(i+1,7);group.append(element('rect',{x:i*5,y:8-h,width:4,height:h,fill:i<9?'#172211':'none',stroke:i<9?'none':'#172211','stroke-width':1}));}}else if(n.font==='custom'&&n.id.endsWith('frequency')){
        for(const [i,ch] of Array.from(value).entries()){const d=ch==='.'?10:Number(ch);if(ch===' '||!Number.isInteger(d))continue;for(let y=0;y<12;y++)for(let x=0;x<8;x++)if(glyphs[d*12+y]&(128>>x))group.append(element('rect',{x:i*8+x,y,width:1,height:1,fill:'#172211','pointer-events':'none'}));}
      }else{
      const draw=(text,key,ox=0,oy=0)=>{const f=root.FluxLCDFonts[key];let d='';for(const [i,ch] of Array.from(text).entries()){const rows=f.glyphs[ch]||f.glyphs['?']||[];for(let y=0;y<rows.length;y++)for(let x=0;x<f.w;x++)if(rows[y]&(1<<x))d+='M'+(ox+i*f.w+x)+' '+(oy+y)+'h1v1h-1z';}if(d)group.append(element('path',{d,fill:'#172211','shape-rendering':'crispEdges','pointer-events':'none'}));};
      if(n.id.endsWith('frequency')&&n.font==='factory'){draw(value.slice(0,7),'large');draw(value.slice(7),'compact',70);}
      else draw(value,n.font==='compact'?'compact':n.h===6?'mode':'small');}
    }
    svg.append(group);
  }
  const n=sel(),b=extent(nodes,id,state);for(const k of ['x','y','font'])field(k).value=n[k];field('w').value=b.w;field('h').value=b.h;
  field('font').disabled=!n.id.endsWith('frequency');
  field('opaque').checked=!!n.opaque;field('opaque').disabled=!childIds.includes(n.id);
  tree.value=id;
 }
 function choose(next){id=next;render();}
 function point(e){const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());}
 for(const n of nodes){const opt=new Option((n.parent?'  ↳ ':'')+label(n),n.id);tree.add(opt);}
 tree.onchange=()=>choose(tree.value);
 svg.addEventListener('pointerdown',e=>{
  const hit=e.target.closest('[data-widget]');if(!hit||e.button!==0)return;
  let next=nodes.find(n=>n.id===hit.dataset.widget);
  if(e.shiftKey&&next.parent)next=nodes.find(n=>n.id===next.parent);
  id=next.id;remember();const p=point(e);drag={id,x:next.x,y:next.y,px:p.x,py:p.y};svg.setPointerCapture(e.pointerId);e.preventDefault();render();
 });
 svg.addEventListener('pointermove',e=>{if(!drag)return;const p=point(e);move(nodes,id,drag.x+p.x-drag.px,drag.y+p.y-drag.py,Number(field('snap').value),field('align').checked&&!e.altKey,state);render();});
 for(const event of ['pointerup','pointercancel'])svg.addEventListener(event,()=>{if(drag){drag=null;notify();}});
 for(const k of ['x','y'])field(k).onchange=()=>{remember();move(nodes,id,Number(field('x').value),Number(field('y').value),1,false,state);render();notify();};
 field('font').onchange=()=>{remember();sel().font=field('font').value;if(sel().font==='custom')hasFont=true;render();notify();};
 field('snap').onchange=render;
 field('opaque').onchange=()=>{remember();sel().opaque=field('opaque').checked;render();notify();};
 for(const [key,delta] of [['front',1],['back',-1]])field(key).onclick=()=>{const n=sel();if(!childIds.includes(n.id))return;remember();nodes=nodes.filter(v=>v!==n);if(delta>0)nodes.push(n);else nodes.splice(nodes.filter(v=>!v.parent).length,0,n);render();notify();};
 function notify(){enabled=true;try{encodeFree(nodes);q('[data-layout-message]').textContent=hasFont&&Array.from({length:11},(_,i)=>glyphs.slice(i*12,i*12+12).some(Boolean)).includes(false)?'A custom font glyph is empty; add ink before exporting.':'Layout selected · 160 bytes of widget descriptors'+(hasFont?' + 132 font bytes':'')+'.';if(changed)changed();}catch(e){q('[data-layout-message]').textContent=e.message;}}
 q('[data-layout-reset]').onclick=()=>{remember();nodes=make();choose('vfo-a');notify();};
 q('[data-layout-package]').onclick=async()=>{
  const msg=q('[data-layout-message]');
  try{
   const base=q('[data-editor-custom]').value.replace(/(?:-f[0-9a-f]{264})?-w[0-9a-f]+$/,'');
   const token=base+fontSuffix()+'-w'+encodeFree(nodes);
   const data=new FormData();data.append('theme',token);
   const r=await fetch('/themes/export',{method:'POST',body:data});
   if(!r.ok)throw Error((await r.json()).error||'Export failed');
   const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download='flux-layout.fluxtheme';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   msg.textContent='Runtime child layout exported.';
  }catch(e){msg.textContent=e.message;}
 };
 q('[data-layout-save]').onclick=()=>{const blob=new Blob([JSON.stringify({version:2,widgets:nodes},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='flux-layout.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
 render();
 return {
   suffix(){return enabled?fontSuffix()+'-w'+encodeFree(nodes):'';},
   load(hex,fontHex){
     glyphs=fontHex?Uint8Array.from(fontHex.match(/../g).map(x=>parseInt(x,16))):starter();hasFont=!!fontHex;fontGrid();
     nodes=make();enabled=!!hex;history=[];future=[];historyButtons();
     if(hex){
       const b=hex.match(/../g).map(x=>parseInt(x,16));
       if(b.length===160||b.length===145||b.length===75){
       const order=[];
       for(let i=0;i<b.length;i+=5){const n=nodes.find(v=>v.id===childIds[b[i]]);if(!n)throw Error('Unknown widget');const p=absolute(nodes,n.parent);n.x=b[i+1]-p.x;n.y=b[i+2]-p.y;n.font=b[i+3]===2?'custom':b[i+3]===1?'compact':'factory';n.opaque=!!b[i+4];order.push(n);}
       nodes=nodes.filter(n=>!n.parent).concat(order,nodes.filter(n=>n.parent&&!order.includes(n)));
     }else if(b.length===45){
       for(const [i,key] of childIds.entries()){
         const n=nodes.find(v=>v.id===key),p=absolute(nodes,n.parent);
         n.x=b[i*3]-p.x;n.y=b[i*3+1]-p.y;n.font=b[i*3+2]===1?'compact':'factory';
       }
     }else for(const [i,key] of ['status','vfo-a','vfo-b','signal'].entries()){
         const n=nodes.find(v=>v.id===key);n.x=b[i*3];n.y=b[i*3+1];
         const f=nodes.find(v=>v.id===key+'-frequency');if(f)f.font=b[i*3+2]===2?'compact':'factory';
       }
       if(b.length===50)for(const [i,key] of childIds.slice(0,15).entries()){
         const n=nodes.find(v=>v.id===key);n.x=b[15+i*2];n.y=b[16+i*2];
       }
     }
     render();
   }
 };
}
const api={make,absolute,extent,move,snap,encodeGroups,encodeFree,create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FluxLayout=api;
})(typeof window!=='undefined'?window:globalThis);
