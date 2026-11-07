# Linear disassembly of one or more address ranges.
# Usage: -postScript gh_ranges.py ranges.txt
# ranges.txt: "<start-hex> <end-hex>" per line.
from ghidra.app.cmd.disassemble import DisassembleCommand

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

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()


def A(x):
    return space.getAddress(x)


for s, e in ranges:
    print("\n===== %08x .. %08x =====" % (s, e))
    cur = A(s)
    n = 0
    while cur <= A(e) and n < 2000:
        i = listing.getInstructionAt(cur)
        if i is None:
            DisassembleCommand(cur, None, True).applyTo(currentProgram, monitor)
            i = listing.getInstructionAt(cur)
            if i is None:
                cur = cur.add(1)
                continue
        f = fm.getFunctionContaining(cur)
        print("  %s  %-40s %s" % (cur, str(i), ("[" + f.getName() + "]") if f else ""))
        cur = cur.add(i.getLength())
        n += 1
