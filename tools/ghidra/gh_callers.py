# List callers of one or more addresses, with a short context window.
# Usage: -postScript gh_callers.py callers.txt   (one hex address per line)
from ghidra.program.model.scalar import Scalar

try:
    path = getScriptArgs()[0]
except Exception:
    path = "callers.txt"

targets = []
for line in open(path):
    line = line.strip().split("#")[0].strip()
    if line:
        targets.append(int(line, 16))

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()
refmgr = currentProgram.getReferenceManager()

for t in targets:
    a = space.getAddress(t)
    print("\n===== callers of %08x =====" % t)
    for r in refmgr.getReferencesTo(a):
        frm = r.getFromAddress()
        if not str(r.getReferenceType()).startswith("UNCONDITIONAL_CALL"):
            continue
        f = fm.getFunctionContaining(frm)
        print("  call@%s func=%s" % (frm, f.getName() if f else "?"))
        cur = frm
        lines = []
        for _ in range(12):
            prev = listing.getInstructionBefore(cur)
            if prev is None:
                break
            lines.append("      %s  %s" % (prev.getAddress(), prev))
            cur = prev.getAddress()
        for ln in reversed(lines):
            print(ln)
