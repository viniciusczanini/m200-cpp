"""Real constructor bounds, with independent positive controls and no skips."""

import os
import shutil
import subprocess
import sys


def constructor_bounds(*,engine,request,repo,work):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ missing; no constructor probe is skipped")
    results = []
    if engine == "vm":
        sys.path.insert(0,str(repo))
        from m200.frontend import compile_source
        from m200.il import Machine
        from m200.model import CompileError
    for probe in request["probes"]:
        directory = work/probe["name"]
        directory.mkdir(parents=True,exist_ok=True)
        source = directory/"constructor.cpp"
        text = "#include <plc.hpp>\n"+probe["declarations"]+"\nvoid scan(){a.execute(false);}\n"
        source.write_text(text)
        if engine == "vm":
            try:
                program = compile_source(source)
                Machine(program).step(dt_ms=0)
                accepted = True
            except CompileError as error:
                (directory/"diagnostic.txt").write_text(str(error)+"\n")
                accepted = False
        elif engine == "sdk":
            harness = directory/"harness.cpp"
            harness.write_text("#define PLC_NATIVE\n"+text+"\nint main(){scan();return 0;}\n")
            binary = directory/"constructor"
            compiled = subprocess.run([compiler,"-std=c++17","-O0","-I",str(repo/"sdk"),str(harness),"-o",str(binary)],capture_output=True,text=True,timeout=60)
            (directory/"compile.log").write_text(compiled.stdout+compiled.stderr)
            if compiled.returncode:
                raise AssertionError("Constructor harness must compile before runtime rejection: "+probe["name"]+"\n"+compiled.stderr)
            completed = subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
            (directory/"execution.log").write_text("exit="+str(completed.returncode)+"\n"+completed.stdout+completed.stderr)
            accepted = completed.returncode == 0
        else:
            raise ValueError("Unknown G07 constructor backend")
        results.append({"name":probe["name"],"accepted":accepted})
    return results
