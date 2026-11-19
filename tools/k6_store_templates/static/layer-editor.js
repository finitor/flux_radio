/* Full-screen Flux graphics: transparent=0, ink=1, paper=2. */
(function(root) {
'use strict';
const W=128,H=64,N=W*H, NS='http://www.w3.org/2000/svg';
const blank=()=>new Uint8Array(N);
const hex=(n,w)=>n.toString(16).padStart(w,'0');
function encode(p) {
  const runs=[];
  for(let i=0;i<N;) {
    if(!p[i]) {i++;continue;}
    let j=i+1;while(j<Math.min(N,(Math.floor(i/W)+1)*W)&&p[j]===p[i])j++;
    runs.push(hex(i|(p[i]===2?0x8000:0),4)+hex(j-i,2));i=j;
  }
  if(!runs.length)return '0';
  if(runs.length*3<=2048)return 's'+runs.join('');
  let out='p';for(let i=0;i<N;i+=4)out+=hex((p[i]<<6)|(p[i+1]<<4)|(p[i+2]<<2)|p[i+3],2);
  return out;
}
function decode(s) {
  const p=blank();
  if(s==='0')return p;
  if(/^p[0-9a-f]{4096}$/.test(s)){
    for(let i=0;i<2048;i++){
      const b=parseInt(s.slice(1+i*2,3+i*2),16);
      for(let j=0;j<4;j++){const v=(b>>(6-2*j))&3;if(v===3)throw Error('Reserved pixel state');p[i*4+j]=v;}
    }
    return p;
  }
  if(!/^s(?:[0-9a-f]{6})+$/.test(s)||s.length>4097)throw Error('Invalid layer code');
  let end=0;
  for(let i=1;i<s.length;i+=6){
    const word=parseInt(s.slice(i,i+4),16),start=word&0x7fff,n=parseInt(s.slice(i+4,i+6),16);
    if(start<end||start>=N||!n||n>W-start%W)throw Error('Overlapping or out-of-bounds layer run');
    p.fill(word&0x8000?2:1,start,start+n);end=start+n;
  }
  return p;
}
function parse(s) {
  if(!s.startsWith('l'))throw Error('Invalid layer suffix');
  const parts=s.slice(1).split('.');
  if(parts.length!==3)throw Error('Expected three layers');
  return parts.map(decode);
}
function path(p,value) {
  const d=[];
  for(let y=0;y<H;y++)for(let x=0;x<W;){
    if(p[y*W+x]!==value){x++;continue;}
    const a=x++;while(x<W&&p[y*W+x]===value)x++;
    d.push('M'+a+' '+y+'h'+(x-a)+'v1h-'+(x-a)+'z');
  }
  return d.join('');
}
function render(group,p) {
  group.replaceChildren();
  for(const [v,color] of [[1,'#172211'],[2,'#b7c8a1']]){
    const d=path(p,v);if(!d)continue;
    const e=document.createElementNS(NS,'path');e.setAttribute('d',d);e.setAttribute('fill',color);group.append(e);
  }
}
function line(p,x0,y0,x1,y1,v){
  let dx=Math.abs(x1-x0),sx=x0<x1?1:-1,dy=-Math.abs(y1-y0),sy=y0<y1?1:-1,err=dx+dy;
  while(true){if(x0>=0&&x0<W&&y0>=0&&y0<H)p[y0*W+x0]=v;
    if(x0===x1&&y0===y1)break;const e=2*err;if(e>=dy){err+=dy;x0+=sx;}if(e<=dx){err+=dx;y0+=sy;}}
}
function shape(p,tool,a,b,v){
  if(tool==='box-fill'||tool==='pattern'){
    for(let y=Math.min(a[1],b[1]);y<=Math.max(a[1],b[1]);y++)for(let x=Math.min(a[0],b[0]);x<=Math.max(a[0],b[0]);x++)if(tool==='box-fill'||(x+y)%2===0)p[y*W+x]=v;
  }else if(tool==='box'){
    line(p,a[0],a[1],b[0],a[1],v);line(p,b[0],a[1],b[0],b[1],v);
    line(p,b[0],b[1],a[0],b[1],v);line(p,a[0],b[1],a[0],a[1],v);
  }else line(p,...a,...b,v);
}
function polygon(p,points,v,filled=false){
  if(points.length<2)return;
  if(filled&&points.length>=3){
    for(let y=0;y<H;y++)for(let x=0;x<W;x++){
      let inside=false;
      for(let i=0,j=points.length-1;i<points.length;j=i++){
        const [a,b]=points[i],[c,d]=points[j];
        if((b>y)!==(d>y)&&x<(c-a)*(y-b)/(d-b)+a)inside=!inside;
      }
      if(inside)p[y*W+x]=v;
    }
  }
  for(let i=0;i<points.length;i++)line(p,...points[i],...points[(i+1)%points.length],v);
}
function snap(a,b){
  const dx=b[0]-a[0],dy=b[1]-a[1],angle=Math.round(Math.atan2(dy,dx)/(Math.PI/4))*Math.PI/4;
  const n=Math.hypot(dx,dy);
  return [Math.max(0,Math.min(W-1,Math.round(a[0]+Math.cos(angle)*n))),Math.max(0,Math.min(H-1,Math.round(a[1]+Math.sin(angle)*n)))];
}
function shift(p,dy){
  const q=blank();for(let y=0;y<H;y++)if(y+dy>=0&&y+dy<H)q.set(p.subarray(y*W,(y+1)*W),(y+dy)*W);return q;
}
function create(editor,svg,hooks){
  const q=s=>editor.querySelector(s);
  const bg=q('[data-editor-bg]'),fg=q('[data-editor-overlay]'),guide=q('[data-editor-guide]');
  const ghost=q('[data-editor-ghost]'),draftGroup=q('[data-editor-draft]'),content=q('[data-editor-content]'),protectedAreas=q('[data-editor-protected]');
  const tool=q('[data-layer-tool]'),state=q('[data-layer-state]'),which=q('[data-layer-which]');
  const undo=q('[data-layer-undo]'),redo=q('[data-layer-redo]'),status=q('[data-layer-status]');
  const mode=q('[data-layer-view]'),locks=[0,1,2].map(i=>q('[data-layer-lock="'+i+'"]'));
  let layers=[blank(),blank(),blank()],history=[],future=[],drag=null,points=[],hover=null,anchor=null,lastActive=0;
  const index=()=>Number(which.value);
  const visible=i=>q('[data-layer-visible="'+i+'"]').checked;
  const locked=i=>locks[i].checked;
  const drawing=()=>q('[data-layer-draw]').checked;
  function bars(){undo.disabled=!history.length;redo.disabled=!future.length;}
  function remember(i,p){history.push([i,p.slice()]);if(history.length>40)history.shift();future=[];bars();}
  function cancel(){if(drag){layers[drag.i]=drag.before;drag=null;}points=[];hover=null;anchor=null;}
  function selected(){if(index())hooks.active(index()-1);}
  function drawGhost(p){
    const group=document.createElementNS(NS,'g');group.setAttribute('opacity','.35');
    for(const [v,color] of [[1,'#447da6'],[2,'#b060a0']]){
      const d=path(p,v);if(!d)continue;
      const el=document.createElementNS(NS,'path');el.setAttribute('d',d);el.setAttribute('fill',color);group.append(el);
    }
    ghost.append(group);
  }
  function refresh(active){
    lastActive=active;
    const i=index(),isolate=drawing()&&mode.value==='isolate',onion=drawing()&&mode.value==='onion';
    const show=k=>visible(k)&&(!isolate||k===i);
    render(bg,show(0)?layers[0]:blank());
    render(fg,show(active+1)?layers[active+1]:blank());
    content.style.display=isolate?'none':'';
    protectedAreas.style.display=isolate?'none':'';
    ghost.replaceChildren();
    if(onion)for(let k=1;k<=2;k++)if(k!==active+1&&visible(k))drawGhost(layers[k]);
    // A draft is a hypothetical edited layer, not persisted or sent to the builder.
    draftGroup.replaceChildren();
    if(hover&&drawing()&&!locked(i)&&(points.length||anchor)){
      const p=layers[i].slice(),v=Number(state.value);
      if(points.length){
        const vertices=[...points,hover];
        if(vertices.length>=3)polygon(p,vertices,v,tool.value==='polygon-fill');
        else line(p,...vertices[0],...vertices[1],v);
      }else shape(p,tool.value,anchor,hover,v);
      const target=i===0?bg:fg;
      if(show(i))render(target,p);
      const a=points.at(-1)||anchor,marker=document.createElementNS(NS,'path');
      marker.setAttribute('d','M'+(a[0]+.5)+' '+(a[1]+.5)+'L'+(hover[0]+.5)+' '+(hover[1]+.5));
      marker.setAttribute('stroke','#2e82c9');marker.setAttribute('stroke-width','.65');marker.setAttribute('stroke-dasharray','1 1');
      draftGroup.append(marker);
    }
    const bytes=layers.reduce((n,p)=>{const s=encode(p);return n+(s==='0'?0:(s.length-1)/2);},0);
    status.textContent=bytes+' bytes encoded · '+(locked(i)?'Layer locked.':points.length?'Polygon: click vertices, Enter to close, Esc to cancel.':anchor?'Click endpoint; Shift snaps, Esc cancels.':'Shift-click from last pen point for a line. Live readouts mask artwork; Isolate reveals all pixels.');
    guide.style.display=drawing()&&q('[data-layer-guide]').checked?'':'none';
    svg.classList.toggle('layer-drawing',drawing());
    svg.setAttribute('aria-label',drawing()?'Draw on '+['background','VFO A cursor','VFO B cursor'][i]:'Designer LCD canvas');
  }
  function resetView(){cancel();selected();hooks.update(false);}
  which.addEventListener('change',resetView);
  tool.addEventListener('change',resetView);
  mode.addEventListener('change',()=>hooks.update(false));
  state.addEventListener('change',()=>hooks.update(false));
  for(const el of editor.querySelectorAll('[data-layer-visible],[data-layer-lock],[data-layer-guide]'))el.addEventListener('change',()=>{if(locked(index()))cancel();hooks.update(false);});
  q('[data-layer-draw]').addEventListener('change',resetView);
  function pos(ev){
    const pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;
    const p=pt.matrixTransform(svg.getScreenCTM().inverse());
    return [Math.max(0,Math.min(127,Math.floor(p.x))),Math.max(0,Math.min(63,Math.floor(p.y)))];
  }
  let lastPoint=null,lastLayer=-1;
  function commit(i,p){remember(i,layers[i]);layers[i]=p;hooks.update(true);}
  function finishPolygon(){
    const i=index();if(points.length<3||locked(i))return;
    const p=layers[i].slice();polygon(p,points,Number(state.value),tool.value==='polygon-fill');
    cancel();commit(i,p);
  }
  svg.addEventListener('pointerdown',ev=>{
    if(!drawing()||locked(index())||ev.button!==0)return;
    ev.preventDefault();selected();
    const i=index(),p=pos(ev),v=Number(state.value),t=tool.value;
    if(t.startsWith('polygon')){
      const target=ev.shiftKey&&points.length?snap(points.at(-1),p):p;
      if(!points.length||points.at(-1).join(',')!==target.join(','))points.push(target);
      hover=target;if(ev.detail>=2)finishPolygon();else hooks.update(false);return;
    }
    if(ev.shiftKey&&t==='pen'&&lastLayer===i&&lastPoint){
      const next=layers[i].slice();line(next,...lastPoint,...p,v);lastPoint=p;cancel();commit(i,next);return;
    }
    if(['line','box','box-fill','pattern'].includes(t)){
      if(anchor){const next=layers[i].slice();shape(next,t,anchor,ev.shiftKey&&t==='line'?snap(anchor,p):p,v);cancel();commit(i,next);}
      else{anchor=p;hover=p;hooks.update(false);}return;
    }
    svg.setPointerCapture(ev.pointerId);
    drag={id:ev.pointerId,i,last:p,before:layers[i].slice(),v};line(layers[i],...p,...p,v);hooks.update(false);
  });
  svg.addEventListener('pointermove',ev=>{
    if(!drawing()||locked(index()))return;
    const p=pos(ev);
    if(drag&&drag.id===ev.pointerId){line(layers[drag.i],...drag.last,...p,drag.v);drag.last=p;hooks.update(false);return;}
    if(points.length||anchor){const a=points.at(-1)||anchor;hover=ev.shiftKey&&tool.value==='line'?snap(a,p):p;hooks.update(false);}
    else if(ev.shiftKey&&tool.value==='pen'&&lastPoint&&lastLayer===index()){
      const next=layers[index()].slice();line(next,...lastPoint,...p,Number(state.value));refresh(lastActive);
      render(index()===0?bg:fg,next);
    }else refresh(lastActive);
  });
  svg.addEventListener('pointerleave',()=>{if(!drag){hover=null;refresh(lastActive);}});
  svg.addEventListener('pointerup',ev=>{
    if(!drag||drag.id!==ev.pointerId)return;
    const d=drag;drag=null;remember(d.i,d.before);lastPoint=d.last;lastLayer=d.i;hooks.update(true);
  });
  svg.addEventListener('pointercancel',()=>{cancel();hooks.update(false);});
  document.addEventListener('keydown',ev=>{
    if(!drawing())return;
    if(ev.key==='Escape'){cancel();hooks.update(false);}
    if(ev.key==='Enter'&&points.length>=3&&!['INPUT','SELECT','TEXTAREA','BUTTON'].includes(ev.target.tagName)){ev.preventDefault();finishPolygon();}
  });
  document.addEventListener('keyup',ev=>{if(ev.key==='Shift'&&drawing())refresh(lastActive);});
  q('[data-layer-finish]').addEventListener('click',finishPolygon);
  q('[data-layer-cancel]').addEventListener('click',()=>{cancel();hooks.update(false);});
  function replay(from,to){
    cancel();if(!from.length)return;
    const [i,p]=from.at(-1);if(locked(i))return;
    from.pop();to.push([i,layers[i].slice()]);layers[i]=p;which.value=String(i);selected();bars();hooks.update(true);
  }
  undo.addEventListener('click',()=>replay(history,future));redo.addEventListener('click',()=>replay(future,history));
  q('[data-layer-clear]').addEventListener('click',()=>{const i=index();if(locked(i))return;cancel();commit(i,blank());});
  q('[data-layer-seed]').addEventListener('click',()=>{
    const i=index();if(!i||locked(i))return;cancel();
    const p=blank(),{border,rail,rows}=hooks.legacy(),y=i===1?8:40;
    if(border)line(p,0,y,127,y,1);if(rail)line(p,0,y+1,0,y+22,1);
    for(let r=0;r<8;r++)for(let x=0;x<7;x++)if(rows[r]&(128>>x))p[(y+r)*W+2+x]=1;
    selected();commit(i,p);
  });
  for(const [sel,from,to,dy] of [['[data-layer-copy-ab]',1,2,32],['[data-layer-copy-ba]',2,1,-32]]){
    q(sel).addEventListener('click',()=>{if(locked(to))return;cancel();which.value=String(to);selected();commit(to,shift(layers[from],dy));});
  }
  return {
    cancel,
    snapshot(){return layers.map(p=>Array.from(p));},
    restore(v){cancel();layers=v.map(p=>Uint8Array.from(p));},
    migrateLegacy(border,rail,ys){for(let i=1;i<=2;i++){const y=ys[i-1];if(border)line(layers[i],0,y,127,y,1);if(rail)line(layers[i],0,y+1,0,y+22,1);}},
    load(s){cancel();layers=s?parse(s):[blank(),blank(),blank()];history=[];future=[];lastPoint=null;lastLayer=-1;bars();},
    suffix(){const parts=layers.map((p,i)=>encode(drag&&drag.i===i?drag.before:p));return parts.every(s=>s==='0')?'':'-l'+parts.join('.');},
    hasCursor(a){return layers[a+1].some(Boolean);},
    showLegacy(a){return !(drawing()&&mode.value==='isolate')&&visible(a+1);},
    render:refresh,editing:drawing,layers:()=>layers
  };
}
const api={blank,encode,decode,parse,shape,polygon,snap,shift,create};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FluxLayers=api;
})(typeof window!=='undefined'?window:globalThis);
