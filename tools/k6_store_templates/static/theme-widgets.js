/* Bounded battery and S-meter glyph editors; row-major LCD pixels. */
(function () {
'use strict';
const NS='http://www.w3.org/2000/svg';
const normal=()=>Array(7).fill(0xf0),over=()=>[0xf0,0x90,0x90,0x90,0x90,0x90,0xf0];
const meterDefault=()=>[...normal(),...over()].map(x=>x.toString(16).padStart(2,'0')).join('');
const outline=[0x1f,0xff,0x80,0x60,0,0x80,0x40,0,0x80,0x40,0,0x80,0x40,0,0x80,0x60,0,0x80,0x1f,0xff,0x80,0,0,0];
const segment=[0xc0,0,0xc0,0xc0,0xc0,0,0xc0,0];
const hex=xs=>Array.from(xs,x=>x.toString(16).padStart(2,'0')).join('');
const bytes=s=>Uint8Array.from(s.match(/../g).map(x=>parseInt(x,16)));
function set(p,x,y,stride,on){const i=y*stride+(x>>3),mask=128>>(x%8);p[i]=on?p[i]|mask:p[i]&~mask;}
function get(p,x,y,stride){return !!(p[y*stride+(x>>3)]&(128>>(x%8)));}
function batteryDefault(){
  const all=new Uint8Array(120);
  for(let n=0;n<5;n++){
    const p=Uint8Array.from(outline);
    for(let i=4-n;i<4;i++)for(let y=0;y<8;y++)for(let x=0;x<2;x++)set(p,4+i*3+x,y,3,!!(segment[y]&(128>>x)));
    all.set(p,n*24);
  }
  return all;
}
function rect(group,x,y,w,h,fill){
  const e=document.createElementNS(NS,'rect');
  for(const [k,v] of Object.entries({x,y,width:w,height:h}))e.setAttribute(k,v);
  if(fill)e.setAttribute('fill',fill);group.append(e);
}
function glyph(g,p,w,h,stride,x,y){
  for(let r=0;r<h;r++)for(let c=0;c<w;c++)if(get(p,c,r,stride))rect(g,x+c,y+r,1,1);
}
function grid(root,w,h,read,toggle){
  const cells=[];
  root.style.gridTemplateColumns='repeat('+w+',minmax(12px,20px))';
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const b=document.createElement('button');b.type='button';
    b.setAttribute('aria-label','Pixel '+(x+1)+', '+(y+1));
    b.addEventListener('click',()=>toggle(x,y));
    root.append(b);cells.push(b);
  }
  return ()=>cells.forEach((b,i)=>b.setAttribute('aria-pressed',String(read(i%w,Math.floor(i/w)))));
}
function create(editor,changed,preview){
  const q=s=>editor.querySelector(s);
  const font=q('[data-theme-font]'),inset=q('[data-theme-inset]'),style=q('[data-theme-meter-style]'),splash=q('[data-theme-splash]');
  const meterPanel=q('[data-theme-custom-meter]'),batteryPanel=q('[data-theme-custom-battery]'),batteryOn=q('[data-theme-battery-on]');
  const signal=q('[data-theme-signal]'),charge=q('[data-theme-charge]'),batteryLevel=q('[data-theme-battery-edit]');
  const meterGroup=q('[data-editor-meter]'),batteryGroup=q('[data-editor-battery]');
  let m=bytes(meterDefault()),b=batteryDefault();
  const drawMeter=[0,1].map(i=>grid(q('[data-theme-meter-grid="'+i+'"]'),5,7,
    (x,y)=>get(m.subarray(i*7),x,y,1),
    (x,y)=>{const p=m.subarray(i*7);set(p,x,y,1,!get(p,x,y,1));changed();}));
  const drawBattery=grid(q('[data-theme-battery-grid]'),17,8,
    (x,y)=>get(b.subarray(Number(batteryLevel.value)*24),x,y,3),
    (x,y)=>{const p=b.subarray(Number(batteryLevel.value)*24);set(p,x,y,3,!get(p,x,y,3));changed();});
  const meterText=q('[data-theme-meter-level]'),batteryText=q('[data-theme-battery-level]');
  function render(){
    meterPanel.hidden=style.value!=='3';batteryPanel.hidden=!batteryOn.checked;
    drawMeter.forEach(f=>f());drawBattery();
    const n=Number(signal.value),bars=Number(charge.value);
    meterText.textContent=n+' / 13';batteryText.textContent=bars+' / 4';
    meterGroup.replaceChildren();batteryGroup.replaceChildren();
    const reading=n>9?'+ '+((n-9)*10):'S'+n;
    const label=document.createElementNS(NS,'text');label.setAttribute('x','2');label.setAttribute('y','38');label.setAttribute('font-size','6');
    label.textContent=(n>9?-73+(n-9)*10:-127+n*6)+'dBm '+reading;meterGroup.append(label);
    if(style.value==='3'){
      for(let i=0;i<n;i++)glyph(meterGroup,m.subarray(i<9?0:7),5,7,1,62+i*5,33);
    }else if(style.value==='2'){
      if(n>0)rect(meterGroup,62,33,Math.min(n,9)*5-1,7);
      if(n>9){const w=(n-9)*5-1;rect(meterGroup,107,33,w,1);rect(meterGroup,107,39,w,1);rect(meterGroup,107,34,1,5);rect(meterGroup,106+w,34,1,5);}
    }else{
      for(let i=0;i<n;i++){const h=style.value==='1'?7:Math.min(i+1,7),x=62+i*5;
        if(i<9)rect(meterGroup,x,40-h,4,h);
        else{rect(meterGroup,x,40-h,4,1);rect(meterGroup,x,39,4,1);rect(meterGroup,x,41-h,1,h-2);rect(meterGroup,x+3,41-h,1,h-2);}
      }
    }
    glyph(batteryGroup,(batteryOn.checked?b:batteryDefault()).subarray(bars*24),17,8,3,109,0);
    for(const el of editor.querySelectorAll('[data-editor-frequency]')){
      const top=Number(el.dataset.editorFrequency),x=126-Number(inset.value),compact=font.value==='1';
      const value=top===8?'146.52000':'440.85000';
      el.replaceChildren();
      const text=(v,px,py,size,w)=>{
        const t=document.createElementNS(NS,'text');
        t.setAttribute('x',px);t.setAttribute('y',py);t.setAttribute('font-size',size);
        t.setAttribute('textLength',w);t.setAttribute('lengthAdjust','spacingAndGlyphs');t.textContent=v;el.append(t);
      };
      if(compact)text(value,x-54,top+7,10,54);
      else{text(value.slice(0,7),x-82,top+13,17,70);text(value.slice(7),x-12,top+7,10,12);}
    }
    const logo=q('[data-theme-boot-logo]');logo.replaceChildren();
    const logos=[
      [0,0xf0,0x3f8,0xff0,0x1f80,0x3c00,0x7800,0xffe0,0xfff8,0x7c,0x1e,0xf,7,3,0,0],
      [0,0x180,0x3c0,0x7e0,0xff0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0xff0,0x7e0,0x3c0,0x180,0],
      [0x180,0x5a0,0x990,0x1188,0x2184,0x180,0x3c0,0x3c0,0x7e0,0x7e0,0xff0,0xff0,0x1ff8,0x3ffc,0x7ffe,0]
    ];
    logos[Number(splash.value)].forEach((row,y)=>{for(let x=0;x<16;x++)if(row&(0x8000>>x))rect(logo,x+20,y+8,1,1);});
  }
  for(const el of [font,inset,style,splash,batteryOn])el.addEventListener('change',changed);
  for(const el of [signal,charge,batteryLevel])el.addEventListener('input',()=>{if(el===batteryLevel)charge.value=el.value;preview();});
  for(const el of editor.querySelectorAll('[data-theme-meter-preset]'))el.addEventListener('click',()=>{
    const [i,kind]=el.dataset.themeMeterPreset.split(':');const v=kind==='continuous'?Array(7).fill(0xf8):kind==='solid'?normal():kind==='hollow'?over():kind==='clear'?Array(7).fill(0):Number(i)?over():normal();
    m.set(v,Number(i)*7);changed();
  });
  q('[data-theme-battery-reset]').addEventListener('click',()=>{b=batteryDefault();changed();});
  q('[data-theme-battery-copy]').addEventListener('click',()=>{const n=Number(batteryLevel.value);if(n<4){b.copyWithin((n+1)*24,n*24,n*24+24);batteryLevel.value=String(n+1);charge.value=String(n+1);changed();}});
  return {
    render,
    suffix(){const digits=font.value+inset.value+style.value+splash.value;
      return (digits==='0000'?'':'-'+digits)+(style.value==='3'?'-m'+hex(m):'')+(batteryOn.checked?'-b'+hex(b):'');},
    load(parts){
      const d=parts.find(x=>/^[01][0-3][0-3][0-2]$/.test(x))||'0000';
      [font.value,inset.value,style.value,splash.value]=d.split('');
      const bm=parts.find(x=>x.startsWith('m')),bt=parts.find(x=>x.startsWith('b'));
      m=bm?bytes(bm.slice(1)):bytes(meterDefault());b=bt?bytes(bt.slice(1)):batteryDefault();batteryOn.checked=!!bt;
    }
  };
}
window.FluxWidgets={create};
})();
