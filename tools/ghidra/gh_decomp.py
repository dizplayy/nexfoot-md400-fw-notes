# Decompile a list of addresses (creating functions if missing).
# Usage: analyzeHeadless ... -postScript gh_decomp.py targets.txt
# targets.txt: one hex address per line, '#' starts a comment.
from ghidra.app.cmd.disassemble import DisassembleCommand
from ghidra.app.cmd.function import CreateFunctionCmd
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

try:
    path = getScriptArgs()[0]
except Exception:
    path = "targets.txt"

targets = []
for line in open(path):
    line = line.strip().split("#")[0].strip()
    if line:
        targets.append(int(line, 16))

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
fm = currentProgram.getFunctionManager()
di = DecompInterface()
di.openProgram(currentProgram)
mon = ConsoleTaskMonitor()

for t in targets:
    a = space.getAddress(t)
    f = fm.getFunctionAt(a) or fm.getFunctionContaining(a)
    if f is None or f.getEntryPoint() != a:
        DisassembleCommand(a, None, True).applyTo(currentProgram, mon)
        CreateFunctionCmd(a).applyTo(currentProgram, mon)
        f = fm.getFunctionAt(a) or fm.getFunctionContaining(a)
    print("\n==================== %08x %s ====================" % (t, f.getName() if f else "(nofunc)"))
    if f is None:
        continue
    res = di.decompileFunction(f, 90, mon)
    if not res.decompileCompleted():
        print("decompile failed:", res.getErrorMessage())
        continue
    print(res.getDecompiledFunction().getC())
