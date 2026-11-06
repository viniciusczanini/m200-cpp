"""Public production guards are observed; this code supplies no ALU oracle."""

import os
import shutil
import subprocess
import sys


def taint_probe(*,engine,request,repo,work):
    if engine=="vm":
        return taint_vm(request,repo)
    if engine!="sdk":raise ValueError("Unknown numeric backend")
    compiler=os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:raise AssertionError("clang++ missing")
    lines=[];observations=[]
    for step in request["steps"]:
        if "op" in step:
            arguments=",".join("true" if a is True else "false" if a is False else str(a) for a in step["args"])
            lines.append("plc::"+step["op"]+"("+arguments+");")
        else:
            for probe in step["observe"]:
                n=probe.get("index",0)
                expression={"i16":f"plc::read_word({n})","i32":f"plc::read_dword({n})","bit":f"plc::read_word_bit({n},{probe.get('bit',0)})","s18":"plc::system(18)","s17":"plc::system(17)"}[probe["kind"]]
                lines.append("{std::fflush(stdout);pid_t pid=fork();if(pid<0)return 9;if(pid==0){volatile long long value=(long long)("+expression+");(void)value;_exit(0);}int status=0;if(waitpid(pid,&status,0)<0)return 10;bool known=WIFEXITED(status)&&WEXITSTATUS(status)==0;if(known){std::printf(\"1 %lld\\n\",(long long)("+expression+"));}else{std::printf(\"0\\n\");}}")
                observations.append(probe)
    source=work/"taint-host.cpp"
    source.write_text("#include <cstdio>\n#include <unistd.h>\n#include <sys/wait.h>\n#define PLC_NATIVE\n#include <plc.hpp>\nint main(){\n"+"\n".join(lines)+"\nreturn 0;}\n")
    binary=work/"taint-host"
    compiled=subprocess.run([compiler,"-std=c++17","-O0","-I",str(repo/"sdk"),str(source),"-o",str(binary)],capture_output=True,text=True,timeout=60)
    (work/"compile.log").write_text(compiled.stdout+compiled.stderr)
    if compiled.returncode:raise AssertionError("SDK guard harness compile failed:\n"+compiled.stderr)
    completed=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
    (work/"execution.log").write_text(completed.stdout+completed.stderr)
    if completed.returncode:raise AssertionError("SDK parent guard harness failed: "+str(completed.returncode))
    rows=completed.stdout.splitlines()
    if len(rows)!=len(observations):raise AssertionError("SDK guard observation count mismatch")
    result=[]
    for probe,line in zip(observations,rows):
        values=[int(v) for v in line.split()];row={**probe,"known":bool(values[0])}
        if row["known"]:
            if len(values)!=2:raise AssertionError("Missing known numeric value")
            row["value"]=bool(values[1]) if probe["kind"] in ("bit","s17","s18") else values[1]
        result.append(row)
    return result


def taint_vm(request,repo):
    sys.path.insert(0,str(repo))
    from m200.il import Machine
    from m200.model import Program,CompileError
    from m200.numeric import Number,evaluate
    from m200.scalar_numeric import known
    machine=Machine(Program([["LD 1","[%MW120:=0]"]]))
    result=[]
    banks={"word":("MW","i16"),"dword":("MD","i32"),"real":("MF","f32")}
    for step in request["steps"]:
        if "op" in step:
            op,args=step["op"],step["args"]
            if op=="clear_arithmetic_error":machine.arithmetic.clear(18)
            elif op=="clear_shift_carry":machine.arithmetic.clear(17)
            elif op=="write_word_bit":machine.write("%%MW%d:X%d"%(args[0],args[1]),args[2])
            elif op.startswith("copy_"):
                bank,_=banks[op[5:]];assert machine.copy_number("%"+bank+str(args[0]),"%"+bank+str(args[1]))
            elif op.startswith("write_"):
                bank,_=banks[op[6:]];machine.write_number("%"+bank+str(args[0]),args[1])
            else:
                stem,suffix=op.split("_");bank,kind=banks[suffix]
                value=evaluate(stem+"_"+kind,args[1:],kind,flags=machine.arithmetic)
                machine.write_number("%"+bank+str(args[0]),value)
        else:
            for probe in step["observe"]:
                row={**probe,"known":True}
                try:
                    kind=probe["kind"]
                    if kind in ("s17","s18"):value=machine.read("%S"+kind[1:],{})
                    elif kind=="bit":value=machine.read("%%MW%d:X%d"%(probe["index"],probe["bit"]),{})
                    else:
                        bank={"i16":"MW","i32":"MD","f32":"MF"}[kind]
                        value=known(machine.read_number(Number(kind,"%"+bank+str(probe["index"]))))
                    row["value"]=value
                except CompileError as error:
                    if "indeterminate" not in str(error):raise
                    row["known"]=False
                result.append(row)
    return result


def constant_bounds(*,engine,request,repo,work):
    compiler=os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:raise AssertionError("clang++ missing")
    if engine=="vm":
        sys.path.insert(0,str(repo))
        from m200.frontend import compile_source
        from m200.il import Machine
        from m200.model import CompileError
    result=[]
    for probe in request["probes"]:
        folder=work/probe["name"];folder.mkdir(parents=True,exist_ok=True)
        source=folder/"probe.cpp";source.write_text("#include <plc.hpp>\n"+probe["source"]+"\n")
        if engine=="vm":
            try:Machine(compile_source(source)).step(dt_ms=0);accepted=True
            except CompileError as error:
                (folder/"diagnostic.txt").write_text(str(error)+"\n");accepted=False
        elif engine=="sdk":
            harness=folder/"host.cpp";harness.write_text("#define PLC_NATIVE\n"+source.read_text()+"\nint main(){scan();return 0;}\n")
            binary=folder/"host"
            compiled=subprocess.run([compiler,"-std=c++17","-O0","-I",str(repo/"sdk"),str(harness),"-o",str(binary)],capture_output=True,text=True,timeout=60)
            (folder/"compile.log").write_text(compiled.stdout+compiled.stderr)
            if compiled.returncode:raise AssertionError("Bounds host must compile before runtime rejection: "+probe["name"]+"\n"+compiled.stderr)
            completed=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
            (folder/"execution.log").write_text("exit="+str(completed.returncode)+"\n"+completed.stdout+completed.stderr)
            accepted=completed.returncode==0
        else:raise ValueError("Unknown bounds backend")
        result.append({"name":probe["name"],"accepted":accepted})
    return result
