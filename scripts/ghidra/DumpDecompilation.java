// DumpDecompilation.java — Ghidra headless post-script
// Usage: analyzeHeadless <projloc> <projname> -import <file> -postScript DumpDecompilation.java <outfile.c>
// Emits full decompiled C for every function, ordered by address.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DumpDecompilation extends GhidraScript {
	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		String outPath = args.length > 0 ? args[0] : "decomp-out.c";

		DecompInterface decomp = new DecompInterface();
		decomp.setOptions(new DecompileOptions());
		if (!decomp.openProgram(currentProgram)) {
			println("ERROR: cannot open program for decompilation");
			return;
		}

		PrintWriter w = new PrintWriter(new FileWriter(outPath));
		w.println("// ===== " + currentProgram.getExecutablePath() + " =====");
		w.println("// program: " + currentProgram.getName());

		FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
		int ok = 0, fail = 0;
		while (it.hasNext() && !monitor.isCancelled()) {
			Function f = it.next();
			String name = f.getName();
			try {
				DecompileResults res = decomp.decompileFunction(f, 120, monitor);
				w.println("\n// ----- " + f.getEntryPoint() + " : " + name + " -----");
				if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
					w.println(res.getDecompiledFunction().getC());
					ok++;
				} else {
					w.println("// DECOMPILE FAILED: " + res.getErrorMessage());
					fail++;
				}
			} catch (Exception e) {
				w.println("// EXCEPTION: " + e.getMessage());
				fail++;
			}
		}
		w.close();
		decomp.dispose();
		println("Dumped " + ok + " functions (" + fail + " failed) -> " + outPath);
	}
}
