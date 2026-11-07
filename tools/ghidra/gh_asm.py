# Assemble q32s instructions and print their bytes (no memory writes).
# Usage: -postScript gh_asm.py asm.txt
# asm.txt: first line "0xADDR", following lines: one instruction each.
from ghidra.app.plugin.assembler import AssemblySelector
from ghidra.app.plugin.assembler.sleigh import SleighAssemblerBuilder


class FirstSel(AssemblySelector):
    def select(self, *args):
        it = args[0].iterator()
        return it.next() if it.hasNext() else None


try:
    path = getScriptArgs()[0]
except Exception:
    path = "asm.txt"

lines = [l.rstrip("\n") for l in open(path) if l.strip() and not l.strip().startswith("#")]
addr = int(lines[0], 16)
code = lines[1:]

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
builder = SleighAssemblerBuilder(currentProgram.getLanguage())
asm = builder.getAssembler(FirstSel())

cur = space.getAddress(addr)
for ln in code:
    try:
        bs = asm.assembleLine(cur, ln)
        print("%s  %-28s %s" % (cur, ln, "".join("%02x" % (x & 0xFF) for x in bs)))
        cur = cur.add(len(bs))
    except Exception as e:
        print("%s  %-28s ERROR %s" % (cur, ln, str(e)[:100].replace("\n", " ")))
