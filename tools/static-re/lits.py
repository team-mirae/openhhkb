import sys,re,subprocess
b=sys.argv[1]
segs=[]
cur={}
for l in subprocess.run(['otool','-l',b],capture_output=True,text=True).stdout.splitlines():
    l=l.strip().split()
    if not l: continue
    if l[0] in('vmaddr','vmsize','fileoff','filesize'): cur[l[0]]=int(l[1],0)
    if l[0]=='filesize': segs.append(dict(cur))
data=open(b,'rb').read()
def rd(va,n):
    for s in segs:
        if s['vmaddr']<=va<s['vmaddr']+s['filesize']: o=s['fileoff']+va-s['vmaddr']; return data[o:o+n]
mangled=dict(l.split('\t') for l in open(b+'.nm').read().splitlines() if '\t' in l)
for a,s in sorted(((a,s) for a,s in mangled.items() if re.search(r'(Tv\d*_|Tv_)$',s)), key=lambda x:x[0]):
    dem=subprocess.run(['xcrun','swift-demangle','--simplified','--compact'],input=s,capture_output=True,text=True).stdout.strip()
    if 'Driver' not in dem and 'Constants' not in dem: continue
    va=int(a,16); h=rd(va,40)
    if not h: continue
    cnt=int.from_bytes(h[24:32],'little')
    body=rd(va+40,min(cnt,512)) if cnt<100000 else b''
    print(f"{a[-9:]} n={cnt:<4} {dem[:90]}\n    {body.hex(' ')}")
