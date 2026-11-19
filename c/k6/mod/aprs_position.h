/* Strict APRS station-position extraction, after AX.25 FCS validation.
   No ambiguous, third-party, object/item or digipeated fixes.
   SPDX-License-Identifier: MIT */
#ifndef FLUX_APRS_POSITION_H
#define FLUX_APRS_POSITION_H
#include "aprs_packet.h"
typedef uint32_t (*ap_div_t)(uint32_t,uint32_t);
AP_FN int ap_equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
AP_FN int32_t ap_scaled(unsigned deg,unsigned hundredths,ap_div_t div){
  return (int32_t)(deg*100000u+div(hundredths*100000u+3000u,6000u));
}
AP_FN int ap_full_coord(const uint8_t *p,int lon,int32_t *v,ap_div_t div){
  unsigned k=lon?3:2,i,d=0,m=0;
  if(!ap_coord(p,lon))return 0;
  for(i=0;i<k;i++)d=d*10+p[i]-'0';
  for(i=k;i<k+5;i++){if(i==k+2)continue;if(p[i]==' ')return 0;m=m*10+p[i]-'0';}
  *v=ap_scaled(d,m,div);
  if(p[k+5]=='S'||p[k+5]=='W')*v=-*v;
  return 1;
}
AP_FN uint32_t ap_base91(const uint8_t *p){
  unsigned i,v=0;for(i=0;i<4;i++){if(p[i]<33||p[i]>123)return 0xffffffffu;v=v*91+p[i]-33;}return v;
}
AP_FN uint32_t ap_ratio_e5(uint32_t n,uint32_t den,ap_div_t div){
  unsigned i,q=div(n,den),r=n-q*den;
  for(i=0;i<5;i++){unsigned d=div(r*10,den);q=q*10+d;r=r*10-d*den;}
  return q+(r*2>=den);
}
AP_FN int ap_timestamp(const uint8_t *p){
  unsigned i,a,b,c;
  for(i=0;i<6;i++)if(p[i]<'0'||p[i]>'9')return 0;
  a=10*(p[0]-'0')+p[1]-'0';b=10*(p[2]-'0')+p[3]-'0';c=10*(p[4]-'0')+p[5]-'0';
  return p[6]=='h'?(a<24&&b<60&&c<60):((p[6]=='z'||p[6]=='/')&&a>=1&&a<=31&&b<24&&c<60);
}
AP_FN int ap_position(const uint8_t *f,unsigned n,const char *source,int32_t *lat,int32_t *lon,ap_div_t div){
  unsigned end,h,i,off=1,dt[6],d,m;int32_t la,lo;char call[10];
  const uint8_t *p;
  if(n<17||!ap_address(call,f)||f[6]&1||!ap_address(call,f+7)||!ap_equal(call,source))return 0;
  end=0;
  for(h=7;h+7<=n&&h<70;h+=7){
    if(!ap_address(call,f+h)||(h>=14&&(f[h+6]&128)))return 0;
    if(f[h+6]&1){end=h+7;break;}
  }
  if(!end||end+2>=n||f[end]!=3||f[end+1]!=0xf0)return 0;
  p=f+end+2;n-=end+2;
  if(p[0]=='/'||p[0]=='@'){if(n<8||!ap_timestamp(p+1))return 0;off=8;}
  else if(p[0]==0x60||p[0]==0x27){
    if(n<9)return 0;
    for(i=0;i<6;i++){
      unsigned c=f[i]>>1;
      if(c>='0'&&c<='9')dt[i]=c-'0';
      else if(i<3&&c>='A'&&c<='J')dt[i]=c-'A';
      else if(c>='P'&&c<='Y')dt[i]=c-'P';
      else return 0; /* Mic-E ambiguity rejected */
    }
    d=10*dt[0]+dt[1];m=1000*dt[2]+100*dt[3]+10*dt[4]+dt[5];
    if(d>90||m>=6000||(d==90&&m))return 0;
    la=ap_scaled(d,m,div);if((f[3]>>1)<'P')la=-la;
    if(p[1]<28||p[1]>127||p[2]<28||p[2]>127||p[3]<28||p[3]>127)return 0;
    d=p[1]-28+((f[4]>>1)>='P'?100:0);
    if(d>=180&&d<=189)d-=80;else if(d>=190&&d<=199)d-=190;
    m=p[2]-28;if(m>=60)m-=60;m=m*100+p[3]-28;
    if(d>180||m>=6000||(d==180&&m))return 0;
    lo=ap_scaled(d,m,div);if((f[5]>>1)>='P')lo=-lo;
    goto accept;
  }else if(p[0]!='!'&&p[0]!='=')return 0;
  if(n>=off+19&&ap_full_coord(p+off,0,&la,div)&&ap_full_coord(p+off+9,1,&lo,div))goto accept;
  /* Compressed station position: symbol table, 4 latitude, 4 longitude,
     symbol, 3 compression bytes. No partial uncompressed fallback. */
  if(n>=off+13&&(p[off]=='/'||p[off]=='\\'||(p[off]>='A'&&p[off]<='Z')||(p[off]>='a'&&p[off]<='j'))){
    uint32_t a=ap_base91(p+off+1),b=ap_base91(p+off+5);
    if(a>180u*380926u||b>360u*190463u)return 0;
    la=9000000-(int32_t)ap_ratio_e5(a,380926,div);
    lo=-18000000+(int32_t)ap_ratio_e5(b,190463,div);
    goto accept;
  }
  return 0;
accept:
  if(la < -9000000||la>9000000||lo < -18000000||lo>18000000)return 0;
  *lat=la;*lon=lo;return 1;
}
#endif
