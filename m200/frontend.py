"""Clang AST allowlist. No source-text translation or execution of user code."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from .lower import Lowerer
from .model import address, fail, timer_config

SDK = Path(__file__).resolve().parents[1] / "sdk"
WRAPPERS = {
    "ImplicitCastExpr",
    "ParenExpr",
    "ExprWithCleanups",
    "MaterializeTemporaryExpr",
    "ConstantExpr",
}


def strip(node):
    while node.get("kind") in WRAPPERS and len(node.get("inner", [])) == 1:
        node = node["inner"][0]
    return node


def walk(node):
    yield node
    for child in node.get("inner", []):
        yield from walk(child)


def source_location(node):
    loc = node.get("loc") or node.get("range", {}).get("begin", {})
    # A macro expansion is a declaration at the expansion site, not an absent
    # declaration. Its spelling can live in another file or on the #define line.
    while "expansionLoc" in loc:
        loc = loc["expansionLoc"]
    return loc


class Frontend:
    def __init__(self, tree, path):
        self.path = path
        self.nodes = {n["id"]: n for n in walk(tree) if "id" in n}
        self.qualified = {}

        def names(n, prefix=""):
            if n.get("kind") == "NamespaceDecl":
                prefix += n.get("name", "") + "::"
            if n.get("kind") == "FunctionDecl":
                self.qualified[n["id"]] = prefix + n.get("name", "")
            for c in n.get("inner", []):
                names(c, prefix)

        names(tree)
        self.top = []
        for node in tree.get("inner", []):
            loc = source_location(node)
            if loc.get("includedFrom") and loc.get("offset") is not None:
                if not (
                    node.get("kind") == "NamespaceDecl"
                    and node.get("name") == "plc"
                    and loc.get("file") == str(SDK / "plc.hpp")
                ):
                    fail(
                        "only declarations from the bundled plc.hpp header are supported"
                    )
                continue
            if loc.get("offset") is not None:
                if loc.get("file", str(path)) != str(path):
                    fail("declaration originates outside the source and bundled SDK")
                self.top.append(node)
        self.functions = {n["id"]: n for n in self.top if n["kind"] == "FunctionDecl"}
        self.variables = {}
        self.instances = {}
        self.calls = set()
        self.active = []
        self.inputs = {}
        self.outputs = {}
        self.init = []
        self.next_timer = 0
        reserved = set()
        for n in walk(tree):
            if n.get("kind") == "CallExpr":
                name, args = self.call(n)
                if name in ("plc::read_m", "plc::write_m"):
                    reserved.add(self.index(args[0], 1024, n))
        self.lower = Lowerer(reserved)

    def error(self, node, message):
        loc = self.location(node)
        fail("%s:%s:%s: %s" % (loc["file"], loc["line"], loc["column"], message))

    def location(self, node):
        loc = source_location(node)
        offset = loc.get("offset", 0)
        text = self.path.read_text()
        line = text.count("\n", 0, offset) + 1
        column = offset - text.rfind("\n", 0, offset)
        return {"file": self.path.name, "line": line, "column": column}

    def const(self, node):
        node = strip(node)
        if node.get("kind") == "IntegerLiteral":
            return int(node["value"])
        if node.get("kind") == "UnaryOperator" and node.get("opcode") == "-":
            return -self.const(node["inner"][0])
        self.error(node, "a literal integer is required here")

    def index(self, node, count, owner):
        value = self.const(node)
        if not 0 <= value < count:
            self.error(owner, "channel/address outside 0..%d" % (count - 1))
        return value

    def call(self, node):
        children = node.get("inner", [])
        if not children:
            return "", []
        ref = strip(children[0]).get("referencedDecl", {})
        return self.qualified.get(ref.get("id"), ref.get("name", "")), children[1:]

    def input(self, index):
        if index not in self.inputs:
            self.inputs[index] = self.lower.bit("input_%d_snapshot" % index)
        return self.inputs[index]

    def output(self, index):
        if index not in self.outputs:
            self.outputs[index] = self.lower.bit("output_%d_image" % index)
        return self.outputs[index]

    def expr(self, node, env=None, side_effect=False):
        env = env or {}
        node = strip(node)
        kind = node.get("kind")
        children = node.get("inner", [])
        if kind == "CXXBoolLiteralExpr":
            return "1" if node["value"] else "0"
        if kind == "DeclRefExpr":
            ref = node["referencedDecl"]["id"]
            if ref in env:
                return env[ref]
            if ref in self.variables:
                return self.variables[ref]
            self.error(node, "unknown or unsupported variable")
        if kind == "UnaryOperator" and node.get("opcode") == "!":
            return self.lower.neg(self.expr(children[0], env))
        if kind == "BinaryOperator" and node.get("opcode") in (
            "&&",
            "||",
            "^",
            "==",
            "!=",
        ):
            return self.lower.binary(
                node["opcode"], self.expr(children[0], env), self.expr(children[1], env)
            )
        if kind == "CallExpr":
            name, args = self.call(node)
            if name == "plc::input":
                return self.input(self.index(args[0], 24, node))
            if name == "plc::output_state":
                return self.output(self.index(args[0], 16, node))
            if name == "plc::read_m":
                return "%M" + str(self.index(args[0], 1024, node))
            if name == "plc::system":
                a = "%S" + str(self.const(args[0]))
                address(a)
                return a
            if name == "plc::clock_ms":
                periods = {10: 4, 100: 5, 1000: 6, 60000: 7}
                value = self.const(args[0])
                if value not in periods:
                    self.error(node, "clock period must be 10, 100, 1000 or 60000 ms")
                return "%S" + str(periods[value])
            ref = strip(children[0]).get("referencedDecl", {}).get("id")
            if ref in self.functions:
                f = self.functions[ref]
                if ref in self.active:
                    self.error(node, "recursive calls are unsupported")
                params = [c for c in f.get("inner", []) if c["kind"] == "ParmVarDecl"]
                body = next(
                    (c for c in f.get("inner", []) if c["kind"] == "CompoundStmt"), None
                )
                if (
                    f["type"]["qualType"].split("(")[0].strip() != "bool"
                    or body is None
                    or len(body.get("inner", [])) != 1
                    or body["inner"][0]["kind"] != "ReturnStmt"
                ):
                    self.error(f, "helpers must return one pure boolean expression")
                if any(p["type"]["qualType"] != "bool" for p in params):
                    self.error(f, "helper parameters must be bool")
                values = [self.lower.copy(self.expr(a, env)) for a in args]
                self.active.append(ref)
                result = self.expr(
                    body["inner"][0]["inner"][0],
                    dict(zip([p["id"] for p in params], values)),
                )
                self.active.pop()
                return result
            self.error(node, "unsupported call: " + name)
        if kind == "CXXMemberCallExpr":
            if not side_effect:
                self.error(
                    node,
                    "stateful update must be an unconditional standalone initializer or assignment",
                )
            member = children[0]
            obj = strip(member["inner"][0])
            ref = obj.get("referencedDecl", {}).get("id")
            if member.get("name") != "update" or ref not in self.instances:
                self.error(node, "unsupported member call")
            if ref in self.calls:
                self.error(node, "instance updated more than once per scan")
            self.calls.add(ref)
            typ, data = self.instances[ref]
            signal = self.lower.copy(self.expr(children[1], env))
            if typ in ("Ton", "Tof", "Pulse"):
                index, config = data
                return self.lower.timer(index, config, signal)
            if typ == "Clock":
                on_index, on_config, off_index, off_config, phase = data
                on = self.lower.timer(
                    on_index,
                    on_config,
                    self.lower.binary("&&", signal, self.lower.neg(phase)),
                )
                off = self.lower.timer(
                    off_index, off_config, self.lower.binary("&&", signal, phase)
                )
                self.lower.assign(phase, "1", self.lower.binary("&&", signal, on))
                self.lower.assign(
                    phase,
                    "0",
                    self.lower.binary(
                        "&&", signal, self.lower.binary("&&", off, self.lower.neg(on))
                    ),
                )
                self.lower.assign(phase, "0", self.lower.neg(signal))
                return phase
            old = data
            out = (
                self.lower.binary("&&", signal, self.lower.neg(old))
                if typ == "RisingEdge"
                else self.lower.binary("&&", self.lower.neg(signal), old)
            )
            self.lower.assign(old, signal)
            return out
        self.error(node, "unsupported expression: " + str(kind))

    def declaration(self, node, guard=None, global_scope=False):
        if node.get("kind") != "VarDecl":
            self.error(node, "unsupported declaration")
        typ = (
            node["type"]
            .get("desugaredQualType", node["type"]["qualType"])
            .replace("struct ", "")
        )
        if typ.startswith("plc::"):
            if not global_scope:
                self.error(node, "stateful instances must be global")
            kind = typ[5:]
            if kind not in (
                "Ton",
                "Tof",
                "Pulse",
                "Clock",
                "RisingEdge",
                "FallingEdge",
            ):
                self.error(node, "unsupported library instance")
            ctor = next(
                (x for x in node.get("inner", []) if x["kind"] == "CXXConstructExpr"),
                None,
            )
            if ctor is None:
                self.error(node, "missing constructor")
            if kind in ("Ton", "Tof", "Pulse", "Clock"):
                index = self.next_timer
                self.next_timer += 2 if kind == "Clock" else 1
                duration = self.const(ctor["inner"][0])
                config = timer_config(
                    {"Ton": "TON", "Tof": "TOF", "Pulse": "TP", "Clock": "TON"}[kind],
                    duration,
                    index,
                )
                if kind == "Clock":
                    if duration == 0:
                        self.error(node, "Clock half-period must be positive")
                    second = timer_config("TON", duration, index + 1)
                    phase = self.lower.bit(node["name"] + "_phase")
                    self.init.append((phase, "0"))
                    self.instances[node["id"]] = (
                        kind,
                        (index, config, index + 1, second, phase),
                    )
                else:
                    self.instances[node["id"]] = (kind, (index, config))
            else:
                old = self.lower.bit(node["name"] + "_previous")
                self.instances[node["id"]] = (kind, old)
                self.init.append((old, "0"))
            return
        if typ not in ("bool", "const bool"):
            self.error(node, "only bool variables are supported in this prototype")
        if node.get("storageClass") == "static" and not global_scope:
            self.error(node, "local static variables are unsupported")
        initial = [x for x in node.get("inner", []) if x.get("kind") != "AnnotateAttr"]
        if len(initial) != 1:
            self.error(node, "bool variables must have an initializer")
        target = self.lower.bit(node["name"])
        self.variables[node["id"]] = target
        if global_scope:
            value = strip(initial[0])
            if value.get("kind") != "CXXBoolLiteralExpr":
                self.error(node, "global bool initializers must be true or false")
            self.init.append((target, "1" if value["value"] else "0"))
        else:
            self.lower.assign(
                target, self.expr(initial[0], side_effect=guard is None), guard
            )

    def statement(self, node, guard=None):
        old = self.lower.origin
        self.lower.origin = self.location(node)
        try:
            self._statement(node, guard)
        finally:
            self.lower.origin = old

    def _statement(self, node, guard=None):
        kind = node["kind"]
        children = node.get("inner", [])
        if kind == "CompoundStmt":
            for c in children:
                self.statement(c, guard)
        elif kind == "DeclStmt":
            for c in children:
                self.declaration(c, guard)
        elif kind == "IfStmt":
            if node.get("hasInit") or node.get("hasVar") or len(children) not in (2, 3):
                self.error(node, "unsupported if initializer")
            cond = self.lower.copy(self.expr(children[0]), "branch_condition")
            yes = cond if guard is None else self.lower.binary("&&", guard, cond)
            self.statement(children[1], yes)
            if len(children) == 3:
                no = self.lower.neg(cond)
                no = no if guard is None else self.lower.binary("&&", guard, no)
                self.statement(children[2], no)
        elif kind == "BinaryOperator" and node.get("opcode") == "=":
            lhs = strip(children[0])
            ref = lhs.get("referencedDecl", {}).get("id")
            if lhs["kind"] != "DeclRefExpr" or ref not in self.variables:
                self.error(node, "unsupported assignment target")
            self.lower.assign(
                self.variables[ref],
                self.expr(children[1], side_effect=guard is None),
                guard,
            )
        elif kind == "CallExpr":
            name, args = self.call(node)
            if name == "plc::output":
                target = self.output(self.index(args[0], 16, node))
            elif name == "plc::write_m":
                target = "%M" + str(self.index(args[0], 1024, node))
            else:
                self.error(node, "only output/write_m calls may be used as statements")
            self.lower.assign(target, self.expr(args[1]), guard)
        elif kind == "NullStmt":
            pass
        else:
            self.error(node, "unsupported statement: " + kind)

    def compile(self):
        scans = []
        for n in self.top:
            if n["kind"] == "VarDecl":
                self.declaration(n, global_scope=True)
            elif n["kind"] == "FunctionDecl":
                if any(
                    x["kind"] not in ("ParmVarDecl", "CompoundStmt")
                    for x in n.get("inner", [])
                ):
                    self.error(
                        n,
                        "function attributes and unsupported declaration properties are forbidden",
                    )
                if n.get("name") == "scan":
                    scans.append(n)
                else:
                    body = next(
                        (x for x in n.get("inner", []) if x["kind"] == "CompoundStmt"),
                        None,
                    )
                    if body is None:
                        self.error(n, "external functions are unsupported")
                    if (
                        n["type"]["qualType"].split("(")[0].strip() != "bool"
                        or len(body.get("inner", [])) != 1
                        or body["inner"][0]["kind"] != "ReturnStmt"
                    ):
                        self.error(n, "helpers must return one pure boolean expression")
                    if any(
                        x["type"]["qualType"] != "bool" or x.get("inner")
                        for x in n.get("inner", [])
                        if x["kind"] == "ParmVarDecl"
                    ):
                        self.error(n, "helper parameters must be bool without defaults")
            else:
                self.error(n, "unsupported top-level declaration: " + n["kind"])
        if len(scans) != 1 or scans[0]["type"]["qualType"] != "void ()":
            fail("exactly one void scan() definition is required")
        body = next(
            (x for x in scans[0].get("inner", []) if x["kind"] == "CompoundStmt"), None
        )
        if body is None:
            fail("scan() must have a body")
        # Validate even unused helpers with the same expression allowlist, without
        # retaining their emitted gates or changing the real I/O allocation.
        for f in self.functions.values():
            if f.get("name") == "scan":
                continue
            saved = (self.lower, self.inputs, self.outputs, self.active)
            self.lower = Lowerer(self.lower.used)
            self.inputs = {}
            self.outputs = {}
            self.active = [f["id"]]
            params = {
                x["id"]: "0" for x in f.get("inner", []) if x["kind"] == "ParmVarDecl"
            }
            helper_body = next(x for x in f["inner"] if x["kind"] == "CompoundStmt")
            try:
                self.expr(helper_body["inner"][0]["inner"][0], params)
            finally:
                self.lower, self.inputs, self.outputs, self.active = saved
        self.statement(body)
        tail = [
            ["LD " + image, f"ST %Q0.{n}"] for n, image in sorted(self.outputs.items())
        ]
        prefix = [
            ["LD %I0." + str(n), "ST " + v] for n, v in sorted(self.inputs.items())
        ]
        prefix += [
            ["LD %Q0." + str(n), "ST " + v] for n, v in sorted(self.outputs.items())
        ]
        prefix += [["LD %S13", "R " + v] for _, v in sorted(self.outputs.items())]
        for target, value in self.init:
            prefix.append(
                ["LD %S13", "S " + target]
                if value == "1"
                else ["LD %S13", "R " + target]
            )
        self.lower.program.rungs = prefix + self.lower.program.rungs + tail
        self.lower.program.metadata["rung_origins"] = (
            [
                {"generated": "input/output snapshot or RUN initialization"}
                for _ in prefix
            ]
            + self.lower.origins
            + [{"generated": "output commit"} for _ in tail]
        )
        return self.lower.program


def compile_source(path):
    path = Path(path).resolve()
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        fail("clang++ was not found; set M200_CLANG")
    cmd = [
        compiler,
        "-std=c++17",
        "-fsyntax-only",
        "-fno-exceptions",
        "-fno-rtti",
        "-I",
        str(SDK),
        "-Xclang",
        "-ast-dump=json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode:
        fail("Clang rejected C++:\n" + result.stderr)
    program = Frontend(json.loads(result.stdout), path).compile()
    program.metadata.update(
        {
            "source": path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "official_editor": "pending",
            "physical_plc": "pending",
        }
    )
    program.metadata["clang_version"] = subprocess.run(
        [compiler, "--version"], capture_output=True, text=True, timeout=10
    ).stdout.splitlines()[0]
    return program
