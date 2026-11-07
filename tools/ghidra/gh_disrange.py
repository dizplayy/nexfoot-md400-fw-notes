# Disassemble a range in an already-open program.
# Usage: -postScript gh_disrange.py range.txt   ("<start-hex> <end-hex>")
from ghidra.app.cmd.disassemble import DisassembleCommand

try:
    args = getScriptArgs()
    lo, hi = [int(x, 16) for x in open(args[0]).read().split()[:2]]
except Exception:
    lo, hi = 0x1E00000, 0x1E00100

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
listing = currentProgram.getListing()

cur = space.getAddress(lo)
end = space.getAddress(hi)
while cur <= end:
    ins = listing.getInstructionAt(cur)
    if ins is None:
        DisassembleCommand(cur, None, True).applyTo(currentProgram, monitor)
        ins = listing.getInstructionAt(cur)
        if ins is None:
            cur = cur.add(1)
            continue
    print("%s  %s" % (cur, ins))
    cur = cur.add(ins.getLength())
