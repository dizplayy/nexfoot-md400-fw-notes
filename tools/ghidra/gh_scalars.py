# Find instructions that reference scalar addresses inside given ranges.
# Usage: -postScript gh_scalars.py ranges.txt
# ranges.txt: "<start-hex> <end-hex>" per line (e.g. "5970 5990").
from ghidra.program.model.scalar import Scalar

try:
    path = getScriptArgs()[0]
except Exception:
    path = "ranges.txt"

ranges = []
for line in open(path):
    line = line.strip().split("#")[0].strip()
    if line:
        s, e = line.split()[:2]
        ranges.append((int(s, 16), int(e, 16)))

listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()

for ins in listing.getInstructions(True):
    hits = []
    for op_i in range(ins.getNumOperands()):
        for obj in ins.getOpObjects(op_i):
            if isinstance(obj, Scalar):
                v = obj.getUnsignedValue()
                for lo, hi in ranges:
                    if lo <= v <= hi:
                        hits.append(v)
    if hits:
        f = fm.getFunctionContaining(ins.getAddress())
        print("%s  %-40s %s  vals=%s" % (
            ins.getAddress(), str(ins),
            ("[" + f.getName() + "]") if f else "",
            ",".join("%#x" % v for v in hits)))
