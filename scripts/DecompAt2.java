// DecompAt.java — decompile specific addresses (creating functions where missing).
// Args: <outFile> <addrHex> [<addrHex> ...]   (Ghidra addresses = ELF vaddr + 0x10000)
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompAt2 extends GhidraScript {
	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		String outPath = args[0];
		DecompInterface decomp = new DecompInterface();
		decomp.setOptions(new DecompileOptions());
		if (!decomp.openProgram(currentProgram)) {
			println("ERROR: cannot open program");
			return;
		}
		PrintWriter w = new PrintWriter(new FileWriter(outPath, true));
		for (int i = 1; i < args.length; i++) {
			Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.decode(args[i]));
			FunctionManager fm = currentProgram.getFunctionManager();
			Function f = fm.getFunctionAt(a);
			if (f == null) {
				f = fm.getFunctionContaining(a);
			}
			if (f == null) {
				// try thumb bit
				f = fm.getFunctionAt(a.add(1));
			}
			if (f == null || f.getBody().getNumAddresses() == 0) {
				println("creating function at " + a);
				try {
					ghidra.program.model.lang.Register tReg = currentProgram.getLanguage().getRegister("T");
					if (tReg != null) {
						currentProgram.getProgramContext().setValue(tReg, a, a, 1);
					}
				} catch (Exception e) {
					println("T-set failed: " + e);
				}
				disassemble(a);
				createFunction(a, null);
				f = fm.getFunctionAt(a);
				if (f == null && a.getOffset() % 2 == 0) {
					// try with thumb bit set address
					Address ta = a.add(1);
					createFunction(ta, null);
					f = fm.getFunctionAt(ta);
					if (f == null) f = fm.getFunctionAt(a);
				}
			}
			w.println("\n// ----- " + a + " : queried -----");
			if (f == null) {
				w.println("// NO FUNCTION at " + a);
				continue;
			}
			w.println("// function: " + f.getName() + " @ " + f.getEntryPoint());
			try {
				DecompileResults res = decomp.decompileFunction(f, 180, monitor);
				if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
					w.println(res.getDecompiledFunction().getC());
				} else {
					w.println("// DECOMPILE FAILED: " + res.getErrorMessage());
				}
			} catch (Exception e) {
				w.println("// EXCEPTION: " + e.getMessage());
			}
		}
		w.close();
		decomp.dispose();
		println("done -> " + outPath);
	}
}
