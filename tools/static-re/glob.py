import sys,re,subprocess
b=sys.argv[1]; wanted=" ".join(sys.argv[2:]).split()  # list of name=func
segs=[];cur={}
for l in subprocess.run(['otool','-l',b],capture_output=True,text=True).stdout.splitlines():
    l=l.strip().split()
    if l and l[0] in('vmaddr','vmsize','fileoff','filesize'): cur[l[0]]=int(l[1],0)
    if l and l[0]=='filesize': segs.append(dict(cur))
data=open(b,'rb').read()
def rd(va,n):
    for s in segs:
        if s['vmaddr']<=va<s['vmaddr']+s['filesize']: o=s['fileoff']+va-s['vmaddr']; return data[o:o+n]
sym={}
for l in open(b+'.nm'):
    a,s=l.rstrip('\n').split('\t')
    if a!='U': sym[s]=int(a,16)
for w in wanted:
    name,fn=w.split('=')
    va=sym.get('_'+fn+'Tv_')
    if va is None: print(name,'no Tv_'); continue
    cnt=int.from_bytes(rd(va+24,8),'little'); raw=rd(va+40,cnt*8)
    print(name, cnt, [hex(int.from_bytes(raw[i:i+8],'little')) for i in range(0,len(raw),8)])
