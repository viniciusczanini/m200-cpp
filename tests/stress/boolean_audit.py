# ruff: noqa: E402
#!/usr/bin/env python3
"""Bounded deterministic, local-only audit; writes solely below --output.
Run via make stress (output is a fresh directory outside the repository).
No installs, network, firmware, Git mutations, or production writes.
"""

import argparse
import copy
import json
import random
import resource
import subprocess
import sys
import time
from pathlib import Path
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--seed", type=int, default=20020261105)
parser.add_argument("--programs", type=int, default=16)
parser.add_argument("--frames", type=int, default=768)
parser.add_argument("--stress-frames", type=int, default=10000)
a = parser.parse_args()
repo = a.repo.resolve()
out = a.output.resolve()
if out == repo or repo in out.parents:
    raise SystemExit("Output must be outside repository")
if (
    not 1 <= a.programs <= 64
    or not 1 <= a.frames <= 10000
    or not 1 <= a.stress_frames <= 100000
):
    raise SystemExit("Audit size limits exceeded")
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo))
resource.setrlimit(resource.RLIMIT_CPU, (240, 240))
resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.native import run_native
from m200.model import CompileError
from m200.reverse import to_cpp
from m200.project import load_project, write_project
from m200.cli import build_artifacts, decompile_file, read_program

started = time.time()
rng = random.Random(a.seed)
results = []
head = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=10
).stdout.strip()
if not head and (repo / ".audit-source-head").exists():
    head = (repo / ".audit-source-head").read_text().strip()
status_before = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=repo,
    capture_output=True,
    text=True,
    timeout=10,
).stdout


def record(name, kind, **fields):
    r = dict(name=name, result=kind, **fields)
    results.append(r)
    print(json.dumps(r, sort_keys=True), flush=True)


def source(name, body, include=True):
    p = out / (name + ".cpp")
    p.write_text(("#include <plc.hpp>\n" if include else "") + body + "\n")
    return p


def frames(n):
    return [
        {
            "dt_ms": rng.choice([0, 1, 2, 9, 10, 17, 100, 1000, 60000]),
            "inputs": {str(i): bool(rng.getrandbits(1)) for i in range(24)},
        }
        for _ in range(n)
    ]


def differential(name, s, fs, recompile=False):
    try:
        p = compile_source(s)
        validate(p)
        m = Machine(p)
        emitted = [m.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in fs]
        native = run_native(s, fs)
        rev = out / (name + ".audit.cpp")
        rev.write_text(to_cpp(p))
        reconstructed = run_native(rev, fs)
        if emitted != native or emitted != reconstructed:
            first = next(
                i
                for i in range(len(fs))
                if emitted[i] != native[i] or emitted[i] != reconstructed[i]
            )
            (out / (name + ".mismatch.json")).write_text(
                json.dumps(
                    dict(
                        frame=first,
                        trace=fs[: first + 1],
                        native=native[first],
                        il=emitted[first],
                        reverse=reconstructed[first],
                    ),
                    indent=2,
                )
            )
            record(
                name,
                "BUG",
                reason="Native/IL/reverse semantic divergence",
                first_mismatch=first,
                frames=len(fs),
                source=str(s),
            )
            return p
        if recompile:
            try:
                q = compile_source(rev)
                qm = Machine(q)
                again = [qm.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in fs]
                if again != emitted:
                    record(name, "BUG", reason="Recompiled reverse divergence")
                    return p
            except CompileError as e:
                record(name + "_reverse_recompile", "LIMITATION", reason=str(e))
                recompile = False
        record(
            name,
            "PASS",
            frames=len(fs),
            rungs=len(p.rungs),
            instructions=sum(map(len, p.rungs)),
            memory_bits=len(p.symbols),
            timers=len(p.timers),
            reverse_recompiled=recompile,
        )
        return p
    except CompileError as e:
        record(name, "REJECT", reason=str(e), source=str(s))
    except Exception as e:
        record(name, "CRASH", reason=repr(e), source=str(s))


def expect_reject(name, fn):
    try:
        fn()
        record(name, "BUG", reason="Malformed/unsupported input was accepted")
    except CompileError as e:
        record(name, "PASS_REJECT", reason=str(e))
    except (ValueError, OSError, KeyError) as e:
        record(name, "CLEAN_ERROR", reason=repr(e))
    except Exception as e:
        record(name, "CRASH", reason=repr(e))


# Seeded finite boolean programs. Explicit scopes, shadowing, repeated helpers,
# integer-promoted XOR, sequential assignments and raw-memory reservations.
leaves = [
    "plc::input(0)",
    "plc::input(1)",
    "plc::input(2)",
    "plc::input(3)",
    "state",
    "a",
    "b",
    "true",
    "false",
    "plc::read_m(0)",
    "plc::read_m(499)",
    "plc::read_m(500)",
    "plc::read_m(1023)",
    "plc::output_state(0)",
]


def expr(depth):
    if depth == 0 or rng.random() < 0.3:
        return rng.choice(leaves)
    if rng.random() < 0.22:
        return "!(" + expr(depth - 1) + ")"
    return (
        "("
        + expr(depth - 1)
        + " "
        + rng.choice(["&&", "||", "^", "==", "!="])
        + " "
        + expr(depth - 1)
        + ")"
    )


for i in range(a.programs):
    body = """#define LOCAL bool a=plc::input(0),b=plc::input(1);
#define H(x,y) helper((x),(y))
bool state=false;
bool helper(bool x,bool y){return (x^y)==(!x&&!y);}
bool nested(bool x){return helper(x,helper(!x,x));}
void scan(){LOCAL
plc::write_m(0,a);plc::write_m(499,b);plc::write_m(500,!a);plc::write_m(1023,!b);
if(a){bool a=!b;plc::output(4,a);}else{bool b=!a;plc::output(4,b);}
"""
    body += "\n".join(
        "plc::output(%d,H(%s,%s));" % (j, expr(2), expr(2)) for j in range(4)
    )
    body += "\nif(a){state=!state;}else if(b){state=nested(b);}plc::output(5,state);plc::output(6,plc::output_state(0));}\n"
    differential(
        "boolean_%02d" % i,
        source("boolean_%02d" % i, body),
        frames(a.frames),
        recompile=i == 0,
    )

stateful = """plc::Clock c0{5};plc::Clock c1{100};plc::Ton ton{0};plc::Tof tof{9};plc::Pulse pulse{10};plc::Ton longton{10000};
plc::RisingEdge rise;plc::FallingEdge fall;bool state=true;
void scan(){bool a=plc::input(0),b=plc::input(1);bool q0=c0.update(a);bool q1=c1.update(a||b);
bool q2=ton.update(a);bool q3=tof.update(b);bool q4=pulse.update(a!=b);bool q5=longton.update(!a);
bool q6=rise.update(q0);bool q7=fall.update(q1);if(q6){state=!state;}
plc::output(0,q0);plc::output(1,q1);plc::output(2,q2);plc::output(3,q3);plc::output(4,q4);plc::output(5,q5);
plc::output(6,q6);plc::output(7,q7);plc::output(8,state);plc::output(9,plc::system(13));plc::output(10,plc::clock_ms(60000));}"""
differential(
    "stateful_10000", source("stateful_10000", stateful), frames(a.stress_frames)
)
for kind in ["Ton", "Tof", "Pulse", "Clock", "RisingEdge", "FallingEdge"]:
    init = "{5}" if kind in ("Ton", "Tof", "Pulse", "Clock") else ""
    body = (
        "plc::%s item%s;void scan(){bool q=item.update(plc::input(0));plc::output(0,q);}"
        % (kind, init)
    )
    differential("class_" + kind, source("class_" + kind, body), frames(512))

macro = """#define input(x) input(x); void output(int,bool); __attribute__((constructor)) inline void before_scan(){output(0,true);} bool ignored(x)
#include <plc.hpp>
#undef input
void scan(){}"""
differential(
    "sdk_macro_constructor_escape",
    source("sdk_macro_constructor_escape", macro, False),
    [{}, {}],
)

# Accepted-edge and deliberate rejection families.
for name, body in {
    "helper_variadic": "bool f(bool a,...){return a;}void scan(){plc::output(0,f(plc::input(0),true));}",
    "edge_global_copy": "plc::RisingEdge a;plc::RisingEdge b=a;void scan(){bool q=b.update(plc::input(0));plc::output(0,q);}",
    "bool_aggregate_init": "void scan(){bool a{plc::input(0)};plc::output(0,a);}",
    "auto_bool": "void scan(){auto a=plc::input(0);plc::output(0,a);}",
}.items():
    differential(name, source(name, body), frames(128))
for name, body in {
    "int_promotion_arithmetic": "void scan(){bool a=plc::input(0);bool q=a+a;plc::output(0,q);}",
    "bitwise_or": "void scan(){plc::output(0,plc::input(0)|plc::input(1));}",
    "conditional_update": "plc::Ton t{5};void scan(){if(plc::input(0)){bool q=t.update(true);}}",
    "duplicate_update": "plc::RisingEdge e;void scan(){bool a=e.update(true),b=e.update(false);}",
    "update_in_helper": "plc::Ton t{5};bool f(bool a){return t.update(a);}void scan(){plc::output(0,f(true));}",
    "update_temporary": "void scan(){bool q=plc::RisingEdge{}.update(true);plc::output(0,q);}",
    "dynamic_address": "void scan(){plc::write_m(plc::input(0),true);}",
    "unused_integer": "int never_used=1;void scan(){}",
    "local_static": "void scan(){static bool a=false;plc::output(0,a);}",
}.items():
    s = source("reject_" + name, body)
    expect_reject("reject_" + name, lambda s=s: compile_source(s))

# XML scalar ambiguity, attributes, duplicates, broken graph, depth/DTD and UTF-16.
base_source = source(
    "xml_base",
    "plc::Ton t{20};void scan(){bool q=t.update(plc::input(0));plc::output(0,q);}",
)
p = compile_source(base_source)
base = out / "base.smbp"
write_project(p, repo / "tests/fixtures/synthetic.smbp", base)
base_bytes = base.read_bytes()
mutations = [
    (
        "fast_period_nested",
        "SoftwareConfiguration",
        "<FastTask><Period>255<UnknownActive>true</UnknownActive></Period></FastTask>",
    ),
    ("timer_preset_nested", ".//TimerTM/Preset", "<UnknownActive>true</UnknownActive>"),
    (
        "il_instruction_nested",
        ".//InstructionLine",
        "<UnknownInstruction>JMP %L9</UnknownInstruction>",
    ),
    ("unknown_software", "SoftwareConfiguration", "<UnknownTask>true</UnknownTask>"),
    ("duplicate_timer_preset", ".//TimerTM", "<Preset>9999</Preset>"),
    ("duplicate_root_name", ".", "<Name>second</Name>"),
    (
        "unknown_cpu",
        "HardwareConfiguration/Plc/Cpu",
        "<ActiveUnknown>true</ActiveUnknown>",
    ),
]
for name, parent, xml in mutations:
    root = ET.fromstring(base_bytes)
    root.find(parent).append(ET.fromstring(xml))
    dest = out / (name + ".smbp")
    ET.ElementTree(root).write(dest)
    expect_reject(name, lambda dest=dest: load_project(dest))
for name, path in [("attribute", ".//TimerTM"), ("graph_attribute", ".//LadderEntity")]:
    root = ET.fromstring(base_bytes)
    root.find(path).set("Executable", "true")
    dest = out / (name + ".smbp")
    ET.ElementTree(root).write(dest)
    expect_reject(name, lambda dest=dest: load_project(dest))
root = ET.fromstring(base_bytes)
root.find(".//InstructionLine").text = "JMP %L9"
dest = out / "unknown_il.smbp"
ET.ElementTree(root).write(dest)
expect_reject("unknown_il", lambda: load_project(dest))
for n in [64, 256, 1300]:
    dest = out / ("deep_%d.smbp" % n)
    dest.write_text(
        "<ProjectDescriptor>" + "<x>" * n + "</x>" * n + "</ProjectDescriptor>"
    )
    expect_reject("deep_%d" % n, lambda dest=dest: load_project(dest))
for enc in ["utf-8", "utf-16"]:
    dest = out / ("dtd_" + enc + ".smbp")
    dest.write_bytes(
        (
            '<?xml version="1.0" encoding="'
            + enc
            + '"?><!DOCTYPE ProjectDescriptor [<!ENTITY x "TM200CE40T">]><ProjectDescriptor><HardwareConfiguration><Plc><Cpu><Reference>&x;</Reference></Cpu></Plc></HardwareConfiguration><SoftwareConfiguration><Pous/></SoftwareConfiguration></ProjectDescriptor>'
        ).encode(enc)
    )
    expect_reject("dtd_" + enc, lambda dest=dest: load_project(dest))

# JSON timer alias and unexpected field families.
program = p.as_dict()
json_cases = {}
x = copy.deepcopy(program)
x["timers"]["00"] = dict(x["timers"]["0"])
json_cases["timer_index_alias"] = x
x = copy.deepcopy(program)
x["unknown_execution"] = {"jump": "%L1"}
json_cases["unknown_json_field"] = x
for name, x in json_cases.items():
    dest = out / (name + ".json")
    dest.write_text(json.dumps(x))
    expect_reject(name, lambda dest=dest: read_program(dest))

# Artifact preservation and decompile collision tests. Only files in this out tree.
art = out / "artifacts"
build_artifacts(p, art)
manual = art / "program.il"
manual.write_bytes(b"MANUAL EDIT\n")
before = {x.name: x.read_bytes() for x in art.iterdir()}
expect_reject("modified_artifact_preserved", lambda: build_artifacts(p, art))
assert before == {x.name: x.read_bytes() for x in art.iterdir()}
art2 = out / "artifacts_unknown"
build_artifacts(p, art2)
(art2 / "do-not-delete.txt").write_text("manual")
before = {x.name: x.read_bytes() for x in art2.iterdir()}
expect_reject("unknown_file_preserved", lambda: build_artifacts(p, art2))
assert before == {x.name: x.read_bytes() for x in art2.iterdir()}
art3 = out / "artifacts_symlink"
build_artifacts(p, art3)
victim = out / "external-victim.il"
victim.write_bytes((art3 / "program.il").read_bytes())
original = victim.read_bytes()
(art3 / "program.il").unlink()
(art3 / "program.il").symlink_to(victim)
build_artifacts(p, art3)
assert victim.read_bytes() == original and not (art3 / "program.il").is_symlink()
record("owned_artifact_symlink_victim_preserved", "PASS")
expect_reject("decompile_same_source", lambda: decompile_file(base, base))
alias = out / "source-alias.cpp"
alias.symlink_to(base)
expect_reject("decompile_source_symlink", lambda: decompile_file(base, alias))
assert base.read_bytes() == base_bytes
new = out / "decompiled.cpp"
decompile_file(base, new)
assert Path(str(new) + ".configuration.smbp").read_bytes() == base_bytes
record("decompile_configuration_byte_preservation", "PASS")
status_after = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=repo,
    capture_output=True,
    text=True,
    timeout=10,
).stdout
summary = dict(
    head=head,
    seed=a.seed,
    elapsed_seconds=round(time.time() - started, 3),
    config=vars(a) | {"repo": str(repo), "output": str(out)},
    results=results,
    repository_status_unchanged=status_before == status_after,
    status_before=status_before,
    status_after=status_after,
)
summary["config"]["repo"] = str(a.repo)
summary["config"]["output"] = str(a.output)
(out / "results.json").write_text(json.dumps(summary, indent=2))
counts = {
    k: sum(r["result"] == k for r in results)
    for k in sorted({r["result"] for r in results})
}
print(
    json.dumps(
        {
            "summary": counts,
            "elapsed_seconds": summary["elapsed_seconds"],
            "head": head,
            "repository_status_unchanged": status_before == status_after,
        }
    ),
    flush=True,
)
