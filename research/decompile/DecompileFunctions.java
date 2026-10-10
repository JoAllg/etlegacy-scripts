// Ghidra headless postScript: decompiles the named functions into one C file.
// Args: <func,func,...> <out.c>   (run via decompile.sh)
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.*;

public class DecompileFunctions extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Set<String> wanted = new TreeSet<>(Arrays.asList(args[0].split(",")));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(new FileWriter(args[1]))) {
            out.println("// " + currentProgram.getName() + ": decompiled by Ghidra (research/decompile/decompile.sh)");
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                // a PLT thunk carries the name of the function it jumps to
                if (f.isThunk() || !wanted.remove(f.getName())) continue;
                DecompileResults r = decomp.decompileFunction(f, 120, monitor);
                out.println("\n// ==== " + f.getName() + " @ " + f.getEntryPoint());
                out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed: " + r.getErrorMessage());
            }
            if (!wanted.isEmpty()) out.println("\n// not found: " + String.join(", ", wanted));
        }
    }
}
