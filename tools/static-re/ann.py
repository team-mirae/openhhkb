import sys,re,subprocess
b,start,end=sys.argv[1],sys.argv[2],sys.argv[3]
stubs={}
for l in subprocess.run(['objdump','--macho','--indirect-symbols',b],capture_output=True,text=True).stdout.splitlines():
    m=re.match(r'0x0*([0-9a-f]+)\s+\d+\s+(\S+)',l)
    if m: stubs[m.group(1)]=m.group(2)
syms={}
for l in open(b+'.map'):
    a,s=l.rstrip('\n').split('\t',1)
    if a!='U' and a.strip(): syms[a.lstrip('0')]=s
out=subprocess.run(['objdump','-d','--no-show-raw-insn',f'--start-address=0x{start}',f'--stop-address=0x{end}',b],capture_output=True,text=True).stdout
regs={}
for l in out.splitlines():
    m=re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)',l)
    if not m: continue
    addr,op,args=m.groups(); args=re.sub(r'\s*<[^>]*>','',args); note=''
    mm=re.match(r'([wx]\d+), #(-?0x[0-9a-f]+|-?\d+)(?:, lsl #(\d+))?',args)
    if op=='mov' and mm:
        r='x'+mm.group(1)[1:]; regs[r]=int(mm.group(2),0)&0xffffffffffffffff
    elif op=='movk' and mm:
        r='x'+mm.group(1)[1:]; sh=int(mm.group(3) or 0); v=int(mm.group(2),0)
        regs[r]=(regs.get(r,0)&~(0xffff<<sh))|(v<<sh)
        s=regs[r].to_bytes(8,'little').rstrip(b'\0')
        if s and all(32<=c<127 for c in s): note=f'  ; "{s.decode()}"'
    t=re.search(r'0x([0-9a-f]+)',args)
    if op in('bl','b') and t:
        a=t.group(1); note='  ; '+(stubs.get(a) or syms.get(a,'?'))[:120]
    print(f'{addr}: {op} {args}{note}')
