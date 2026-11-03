#!/usr/bin/env python3
# Decomprime un .cxp CX-Programmer nel suo .cxt testuale. Uso: python -I cxp_explode.py progetto.cxp progetto.cxt
import sys
def build(rep):
    lens=[]
    for r in rep: lens+= [r&15]*((r>>4)+1)
    cnt=[0]*14
    for l in lens: cnt[l]+=1
    sym=[s for l in range(1,14) for s,x in enumerate(lens) if x==l]
    return cnt,sym
LEN=build([2,35,36,53,38,23]); DIST=build([2,20,53,230,247,151,248])
BASE=[3,2,4,5,6,7,8,9,10,12,16,24,40,72,136,264]; EXTRA=[0]*8+[1,2,3,4,5,6,7,8]
class B:
    def __init__(s,d): s.d=d;s.p=0;s.n=0;s.b=0
    def bits(s,c):
        while s.n<c: s.b|=s.d[s.p]<<s.n;s.p+=1;s.n+=8
        v=s.b&((1<<c)-1);s.b>>=c;s.n-=c;return v
    def dec(s,h):
        cnt,sym=h;code=first=idx=0
        for l in range(1,14):
            code|=s.bits(1)^1;c=cnt[l]
            if code<first+c: return sym[idx+code-first]
            idx+=c;first=(first+c)<<1;code<<=1
        raise ValueError('bad code')
d=open(sys.argv[1],'rb').read(); assert d[0]==0 and d[1] in(4,5,6)
dic=d[1]; s=B(d[2:]); o=bytearray()
while True:
    if s.bits(1):
        x=s.dec(LEN); n=BASE[x]+s.bits(EXTRA[x])
        if n==519: break
        k=2 if n==2 else dic
        dist=(s.dec(DIST)<<k)+s.bits(k)+1
        for _ in range(n): o.append(o[-dist])
    else: o.append(s.bits(8))
open(sys.argv[2],'wb').write(o); print('out',len(o))
