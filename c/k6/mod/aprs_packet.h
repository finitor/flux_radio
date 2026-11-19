/* Small allocation-free APRS UI-frame parser. No RF or platform dependencies.
   SPDX-License-Identifier: MIT */
#ifndef FLUX_APRS_PACKET_H
#define FLUX_APRS_PACKET_H
#include <stdint.h>
#define AP_FN static __attribute__((unused))
#define AP_TEXT 57
typedef struct {
  char src[10], dst[10], to[10], text[AP_TEXT], pos[9+11];
  uint8_t type, hops, path, symbol, table;
  uint16_t len;
} ap_packet_t;
enum {AP_UNKNOWN,AP_POSITION,AP_MESSAGE,AP_STATUS,AP_WEATHER,AP_OBJECT,AP_TELEMETRY,AP_MICE,AP_ITEM,AP_THIRD};
AP_FN void ap_copy(char *dst,unsigned cap,const uint8_t *src,unsigned n){
  unsigned i;
  if(n>=cap)n=cap-1;
  for(i=0;i<n;i++)dst[i]=src[i]>=32&&src[i]<=126?(char)src[i]:'?';
  dst[n]=0;
}
AP_FN int ap_address(char out[10],const uint8_t *a){
  unsigned i=0,n=0,ssid=(a[6]>>1)&15;
  int pad=0;
  for(;i<6;i++){
    unsigned c=a[i]>>1;
    if(a[i]&1)return 0;
    if(c==' '){pad=1;continue;}
    if(pad||!((c>='A'&&c<='Z')||(c>='0'&&c<='9')))return 0;
    out[n++]=(char)c;
  }
  if(!n)return 0;
  if(ssid){out[n++]='-';if(ssid>=10)out[n++]='1';out[n++]=(char)('0'+(ssid>=10?ssid-10:ssid));}
  out[n]=0;return 1;
}
AP_FN const char *ap_type(uint8_t k){
  switch(k){case AP_POSITION:return "POS";case AP_MESSAGE:return "MSG";case AP_STATUS:return "STATUS";
  case AP_WEATHER:return "WX";case AP_OBJECT:return "OBJ";case AP_TELEMETRY:return "TLM";
  case AP_MICE:return "MIC-E";case AP_ITEM:return "ITEM";case AP_THIRD:return "3RD";default:return "DATA";}
}
AP_FN int ap_coord(const uint8_t *p,int lon){
  unsigned i,d=0,k=lon?3:2,deg=0,m=0;
  for(i=0;i<k;i++){if(p[i]<'0'||p[i]>'9')return 0;deg=deg*10+p[i]-'0';}
  if(p[k+2]!='.'||deg>(lon?180u:90u))return 0;
  for(i=k;i<k+5;i++){
    if(i==k+2)continue;
    if(p[i]==' '){d=1;continue;} /* position ambiguity */
    if(d||p[i]<'0'||p[i]>'9')return 0;
    m=m*10+p[i]-'0';
    if(i==k&&p[i]>'5')return 0;
  }
  if(deg==(lon?180u:90u)&&(m||d))return 0;
  return lon?(p[k+5]=='E'||p[k+5]=='W'):(p[k+5]=='N'||p[k+5]=='S');
}
/* Caller has checked FCS; length excludes FCS. Unknown formats stay visible as text.
   Uncompressed positions only are interpreted; Mic-E/compressed are labelled, not guessed. */
AP_FN int ap_parse(ap_packet_t *a,const uint8_t *f,unsigned n){
  unsigned h=0,i,off=0,end=0;
  const uint8_t *p;
  char addr[10];
  a->type=AP_UNKNOWN;a->hops=a->path=a->symbol=a->table=0;
  a->src[0]=a->dst[0]=a->to[0]=a->text[0]=a->pos[0]=0;
  if(n<17||!ap_address(a->dst,f)||!ap_address(a->src,f+7)||(f[6]&1))return 0;
  for(h=7;h+7<=n&&h<70;h+=7){
    if(!ap_address(addr,f+h))return 0;
    if(h>=14){a->path++;if(f[h+6]&128)a->hops++;}
    if(f[h+6]&1){end=h+7;break;}
  }
  if(!end||end+2>=n||f[end]!=3||f[end+1]!=0xF0)return 0;
  p=f+end+2;n-=end+2;a->len=(uint16_t)n;
  switch(p[0]){
  case '!':case '=':a->type=AP_POSITION;off=1;break;
  case '/':case '@':a->type=AP_POSITION;off=8;break;
  case ':':
    if(n>=11&&p[10]==':'){
      a->type=AP_MESSAGE;ap_copy(a->to,sizeof a->to,p+1,9);
      for(i=9;i&&a->to[i-1]==' ';i--)a->to[i-1]=0;
      off=11;
    }break;
  case '>':a->type=AP_STATUS;off=1;break;
  case '_':a->type=AP_WEATHER;off=1;break;
  case ';':a->type=AP_OBJECT;off=1;break;
  case ')':a->type=AP_ITEM;off=1;break;
  case 'T':if(n>=2&&p[1]=='#'){a->type=AP_TELEMETRY;off=2;}break;
  case 0x60:case 0x27:a->type=AP_MICE;break;
  case '}':a->type=AP_THIRD;off=1;break;
  }
  if(a->type==AP_POSITION&&off+19<=n&&ap_coord(p+off,0)&&ap_coord(p+off+9,1)){
    ap_copy(a->pos,9,p+off,8);a->pos[8]=' ';
    ap_copy(a->pos+9,10,p+off+9,9);
    a->table=p[off+8];a->symbol=p[off+18];
    off+=19;
    if(a->symbol=='_')a->type=AP_WEATHER;
  }
  if(off>n)off=0;
  ap_copy(a->text,sizeof a->text,p+off,n-off);
  return 1;
}
#endif
