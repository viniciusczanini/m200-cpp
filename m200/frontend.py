"""Clang AST allowlist. No source-text translation or execution of user code."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .lower import Lowerer
from .model import address, fail, timer_config
from .numeric import Number, OPS, READS, WRITES, TYPES, boolean, expect, literal
from .modbus import ModbusConfig
from .communication import KINDS, BOOL_FIELDS, NUM_FIELDS

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
    # Clang stores partially initialized arrays outside `inner`: the first
    # entry is the implicit zero filler and the rest are explicit initializers.
    for child in node.get("array_filler", []):
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
                # The file path alone does not establish header integrity: user
                # macros can inject arbitrary declarations inside this namespace.
                for descendant in walk(node):
                    locations = [descendant.get("loc", {})]
                    locations += list(descendant.get("range", {}).values())
                    if any(
                        "expansionLoc" in p or "spellingLoc" in p for p in locations
                    ):
                        fail("macros may not alter declarations inside the bundled SDK")
                continue
            if loc.get("offset") is not None:
                if loc.get("file", str(path)) != str(path):
                    fail("declaration originates outside the source and bundled SDK")
                self.top.append(node)
        self.functions = {n["id"]: n for n in self.top if n["kind"] == "FunctionDecl"}
        self.variables = {}
        self.arrays = {}
        self.instances = {}
        self.calls = set()
        self.active = []
        self.inputs = {}
        self.outputs = {}
        self.init = []
        self.next_timer = 0
        self.communication_specs = {}
        self.explicit_communications = {}
        self.communication_modes = {k: set() for k in KINDS}
        self.communication_ids = {k: set() for k in KINDS}
        self.next_communication = {k: 0 for k in KINDS}
        self.comm_observed = set()
        reserved = set()
        reserved_words = set()
        for n in walk(tree):
            if n.get("kind") == "VarDecl" and n.get("type", {}).get(
                "desugaredQualType", n.get("type", {}).get("qualType", "")
            ) in ["plc::" + k for k in KINDS]:
                cfg = self.communication_config(n)
                self.communication_specs[n["id"]] = cfg
                reserved_words.update(
                    range(cfg.index_data, cfg.index_data + cfg.data_words)
                )
                if cfg.kind == "WRITE_READ_VAR":
                    reserved_words.update(
                        range(cfg.index_data_in, cfg.index_data_in + cfg.read_quantity)
                    )
            if n.get("kind") == "CallExpr":
                name, args = self.call(n)
                if name in ("plc::read_m", "plc::write_m"):
                    reserved.add(self.index(args[0], 1024, n))
                key = name.removeprefix("plc::")
                if key in READS or key in WRITES:
                    typ = (READS | WRITES)[key]
                    index = self.index(args[0], 8000 - TYPES[typ][1] + 1, n)
                    reserved_words.update(range(index, index + TYPES[typ][1]))
        self.lower = Lowerer(reserved, reserved_words)
        self.loops = []
        self.source_labels = {}
        if any(len(modes) > 1 for modes in self.communication_modes.values()):
            fail(
                "do not mix automatic and explicit communication indices of the same kind"
            )

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
        if node.get("kind") == "DeclRefExpr":
            ref = self.nodes.get(node.get("referencedDecl", {}).get("id"), {})
            if ref.get("kind") == "EnumConstantDecl" and len(ref.get("inner", [])) == 1:
                return self.const(ref["inner"][0])
        if node.get("kind") == "IntegerLiteral":
            return int(node["value"])
        if node.get("kind") == "UnaryOperator" and node.get("opcode") == "-":
            return -self.const(node["inner"][0])
        self.error(node, "a literal integer is required here")

    def communication_config(self, node):
        kind = node["type"].get("desugaredQualType", node["type"]["qualType"])[5:]
        ctor = next(
            (x for x in node.get("inner", []) if x["kind"] == "CXXConstructExpr"), None
        )
        if ctor is None:
            self.error(
                node, "native communication configuration requires a constructor"
            )
        args = [self.const(x) for x in ctor.get("inner", [])]
        if any(not -2147483648 <= x <= 2147483647 for x in args):
            self.error(
                node,
                "communication constructor value exceeds its signed 32-bit representation",
            )
        count = 9 if kind == "WriteReadVar" else 7
        explicit = len(args) == count + 1
        self.communication_modes[kind].add(explicit)
        if explicit:
            index = args.pop(0)
            if not 0 <= index < 32 or index in self.communication_ids[kind]:
                self.error(node, "invalid or duplicate explicit communication index")
            self.communication_ids[kind].add(index)
            self.explicit_communications[node["id"]] = index
        if len(args) != count:
            self.error(node, "invalid communication constructor arguments")
        link = {1: "SL1", 2: "ETH1"}.get(args[0])
        if link is None:
            self.error(node, "unsupported embedded communication link")
        cfg = dict(kind=KINDS[kind], link=link, id=args[1], timeout_100ms=args[2])
        if kind == "WriteReadVar":
            cfg.update(
                first_obj=args[3],
                quantity=args[4],
                index_data=args[5],
                first_read_obj=args[6],
                read_quantity=args[7],
                index_data_in=args[8],
            )
        else:
            cfg.update(
                obj_type=args[3],
                first_obj=args[4],
                quantity=args[5],
                index_data=args[6],
            )
        return ModbusConfig(**cfg)

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

    def array_element(self, node):
        base, subscript = node["inner"]
        base = strip(base)
        ref = base.get("referencedDecl", {}).get("id")
        if base.get("kind") != "DeclRefExpr" or ref not in self.arrays:
            self.error(node, "array access requires a declared fixed-capacity array")
        elements = self.arrays[ref]
        return elements[self.index(subscript, len(elements), node)]

    def expr(self, node, env=None, side_effect=False):
        env = env or {}
        node = strip(node)
        kind = node.get("kind")
        children = node.get("inner", [])
        if kind == "CXXBoolLiteralExpr":
            return "1" if node["value"] else "0"
        if kind == "IntegerLiteral":
            if "unsigned" in node.get("type", {}).get("qualType", ""):
                self.error(node, "unsigned numeric literals/promotions are unsupported")
            return Number("literal", node["value"])
        if kind == "FloatingLiteral":
            if node["type"]["qualType"] != "float":
                self.error(node, "REAL literals require the f suffix")
            return literal(float(node["value"]), "f32")
        if kind == "DeclRefExpr":
            ref = node["referencedDecl"]["id"]
            if ref in env:
                return env[ref]
            if ref in self.variables:
                return self.variables[ref]
            self.error(node, "unknown or unsupported variable")
        if kind == "ArraySubscriptExpr":
            return self.array_element(node)
        if kind == "UnaryOperator" and node.get("opcode") == "!":
            return self.lower.neg(self.expr(children[0], env))
        if kind == "UnaryOperator" and node.get("opcode") == "-":
            value = self.expr(children[0], env)
            if not isinstance(value, Number) or value.code.startswith("%"):
                self.error(
                    node,
                    "numeric negation requires a literal; use plc::sub_* for variables",
                )
            return (
                Number(value.kind, str(-int(value.code)))
                if value.kind == "literal"
                else literal(-float(value.code), value.kind)
            )
        if kind == "BinaryOperator" and node.get("opcode") in (
            "&&",
            "||",
            "^",
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
        ):
            a = self.expr(children[0], env)
            old_guard = self.lower.guard
            if node["opcode"] in ("&&", "||"):
                boolean(a)
                rhs_guard = a if node["opcode"] == "&&" else self.lower.neg(a)
                self.lower.guard = (
                    rhs_guard
                    if old_guard is None
                    else self.lower.binary("&&", old_guard, rhs_guard)
                )
            try:
                b = self.expr(children[1], env)
            finally:
                self.lower.guard = old_guard
            if isinstance(a, Number) or isinstance(b, Number):
                if node["opcode"] not in ("==", "!=", "<", ">", "<=", ">="):
                    self.error(
                        node, "numeric operators require explicit plc::* intrinsics"
                    )
                return self.lower.comparison(node["opcode"], a, b)
            return self.lower.binary(node["opcode"], a, b)
        if kind == "CallExpr":
            name, args = self.call(node)
            key = name.removeprefix("plc::")
            if key in READS:
                typ = READS[key]
                index = self.index(args[0], 8000 - TYPES[typ][1] + 1, node)
                return Number(typ, "%" + TYPES[typ][0] + str(index))
            if key in OPS:
                typ, argtypes, _, _ = OPS[key]
                values = []
                for arg, argkind in zip(args, argtypes):
                    if argkind == "shift":
                        n = self.const(arg)
                        if not 1 <= n <= (16 if typ == "i16" else 32):
                            self.error(node, "shift count outside operand width")
                        values.append(n)
                    else:
                        values.append(expect(self.expr(arg, env), argkind))
                return self.lower.numeric(key, values)
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
            member = children[0]
            obj = strip(member.get("inner", [{}])[0])
            ref = obj.get("referencedDecl", {}).get("id")
            if ref in self.instances and self.instances[ref][0] in KINDS:
                typ, (key, cfg) = self.instances[ref]
                name = member.get("name")
                if name != "update":
                    self.comm_observed.add(ref)
                    suffix = {v: k for k, v in BOOL_FIELDS.items()}.get(name)
                    if suffix:
                        return key + "." + suffix
                    suffix = {v[1]: k for k, v in NUM_FIELDS.items()}.get(name)
                    if suffix:
                        return Number(NUM_FIELDS[suffix][0], key + "." + suffix)
                    self.error(node, "unsupported communication status getter")
                if not side_effect:
                    self.error(
                        node, "communication update must be unconditional once per scan"
                    )
                if ref in self.calls:
                    self.error(node, "instance updated more than once per scan")
                self.calls.add(ref)
                execute = self.lower.copy(boolean(self.expr(children[1], env)))
                abort = boolean(self.expr(children[2], env))
                self.lower.program.communications[key] = cfg
                if abort == "0":
                    self.lower.rung("BLK " + key, "LD " + execute, "EXECUTE", "END_BLK")
                else:
                    abort = self.lower.copy(abort)
                    self.lower.rung(
                        "BLK " + key,
                        "LD " + execute,
                        "EXECUTE",
                        "LD " + abort,
                        "ABORT",
                        "END_BLK",
                    )
                return key + ".DONE"
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
            signal = self.lower.copy(boolean(self.expr(children[1], env)))
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
        array = re.fullmatch(
            r"(?:const )?(bool|plc::i16|plc::i32|plc::f32)\s*\[([0-9]+)\]",
            node["type"]["qualType"],
        )
        if array:
            self.array_declaration(
                node, array.group(1), int(array.group(2)), guard, global_scope
            )
            return
        typ = (
            node["type"]
            .get("desugaredQualType", node["type"]["qualType"])
            .replace("struct ", "")
        )
        numeric_kind = {"plc::i16": "i16", "plc::i32": "i32", "plc::f32": "f32"}.get(
            node["type"]["qualType"].removeprefix("const ")
        )
        if numeric_kind:
            if node.get("storageClass") == "static" and not global_scope:
                self.error(node, "local static variables are unsupported")
            initial = node.get("inner", [])
            if len(initial) != 1:
                self.error(node, "numeric variables require one initializer")
            value = expect(self.expr(initial[0]), numeric_kind)
            target = self.lower.word(
                numeric_kind, node["name"], persistent=global_scope
            )
            self.variables[node["id"]] = target
            if global_scope:
                if value.code.startswith("%"):
                    self.error(node, "global numeric initializer must be a literal")
                self.init.append((target, value))
            else:
                self.lower.assign(target, value, guard)
            return
        if typ.startswith("plc::"):
            if not global_scope:
                self.error(node, "stateful instances must be global")
            kind = typ[5:]
            if kind in KINDS:
                cfg = self.communication_specs[node["id"]]
                index = self.explicit_communications.get(
                    node["id"], self.next_communication[kind]
                )
                if index >= 32:
                    self.error(node, "native communication instance capacity exceeded")
                self.next_communication[kind] += 1
                self.instances[node["id"]] = (kind, ("%" + cfg.kind + str(index), cfg))
                return
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
                    phase = self.lower.bit(node["name"] + "_phase", persistent=True)
                    self.init.append((phase, "0"))
                    self.instances[node["id"]] = (
                        kind,
                        (index, config, index + 1, second, phase),
                    )
                else:
                    self.instances[node["id"]] = (kind, (index, config))
            else:
                old = self.lower.bit(node["name"] + "_previous", persistent=True)
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
        target = self.lower.bit(node["name"], persistent=global_scope)
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

    def array_declaration(self, node, typ, count, guard, global_scope):
        if node.get("storageClass") == "extern":
            self.error(node, "extern array declarations are not implemented")
        if node.get("storageClass") == "static" and not global_scope:
            self.error(node, "local static arrays are not implemented")
        kind = typ.removeprefix("plc::")
        capacity = 1024 if kind == "bool" else 8000 // TYPES[kind][1]
        if not 1 <= count <= capacity:
            self.error(node, "array capacity exceeds target memory")
        initial = node.get("inner", [])
        if len(initial) > 1 or (initial and initial[0].get("kind") != "InitListExpr"):
            self.error(node, "array requires a brace initializer")
        if not initial and not global_scope:
            self.error(node, "local arrays require initialization before use")
        values = []
        if initial:
            init = initial[0]
            values = init.get("inner", [])
            if "array_filler" in init:
                filler, *values = init["array_filler"]
                if filler.get("kind") != "ImplicitValueInitExpr":
                    self.error(init, "unknown array initialization filler")
        if len(values) > count:
            self.error(node, "too many array initializers")
        elements = [
            self.lower.bit(f"{node['name']}_{i}", persistent=global_scope)
            if kind == "bool"
            else self.lower.word(kind, f"{node['name']}_{i}", persistent=global_scope)
            for i in range(count)
        ]
        self.arrays[node["id"]] = elements
        for i, target in enumerate(elements):
            value = (
                self.expr(values[i])
                if i < len(values)
                else ("0" if kind == "bool" else literal(0, kind))
            )
            value = boolean(value) if kind == "bool" else expect(value, kind)
            if global_scope:
                code = value.code if isinstance(value, Number) else value
                if code.startswith("%"):
                    self.error(node, "global array initializers must be literals")
                self.init.append((target, value))
            else:
                self.lower.assign(target, value, guard)

    def statement(self, node, guard=None):
        old = self.lower.origin
        old_guard = self.lower.guard
        self.lower.origin = self.location(node)
        self.lower.guard = guard
        try:
            self._statement(node, guard)
        finally:
            self.lower.origin = old
            self.lower.guard = old_guard

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
            if any(n.get("kind") == "LabelStmt" for n in walk(node)):
                self.branch_with_labels(node, guard)
                return
            cond = self.lower.copy(boolean(self.expr(children[0])), "branch_condition")
            yes = cond if guard is None else self.lower.binary("&&", guard, cond)
            self.statement(children[1], yes)
            if len(children) == 3:
                no = self.lower.neg(cond)
                no = no if guard is None else self.lower.binary("&&", guard, no)
                self.statement(children[2], no)
        elif kind in ("WhileStmt", "ForStmt", "DoStmt"):
            self.loop(node, guard)
        elif kind in ("BreakStmt", "ContinueStmt"):
            if not self.loops:
                self.error(node, "break/continue requires an enclosing loop")
            self.lower.jump(self.loops[-1][kind], guard if guard is not None else "1")
        elif kind == "LabelStmt":
            self.lower.label(self.source_labels[node["declId"]])
            self.statement(children[0], guard)
        elif kind == "GotoStmt":
            label = self.source_labels.get(node.get("targetLabelDeclId"))
            if label is None:
                self.error(node, "goto target is outside scan()")
            self.lower.jump(label, guard if guard is not None else "1")
        elif kind == "BinaryOperator" and node.get("opcode") == "=":
            lhs = strip(children[0])
            ref = lhs.get("referencedDecl", {}).get("id")
            if lhs["kind"] == "ArraySubscriptExpr":
                target = self.array_element(lhs)
            elif lhs["kind"] == "DeclRefExpr" and ref in self.variables:
                target = self.variables[ref]
            else:
                self.error(node, "unsupported assignment target")
            self.lower.assign(
                target,
                self.expr(children[1], side_effect=guard is None),
                guard,
            )
        elif kind == "CallExpr":
            name, args = self.call(node)
            if name == "plc::output":
                target = self.output(self.index(args[0], 16, node))
            elif name == "plc::write_m":
                target = "%M" + str(self.index(args[0], 1024, node))
            elif name.removeprefix("plc::") in WRITES:
                typ = WRITES[name.removeprefix("plc::")]
                index = self.index(args[0], 8000 - TYPES[typ][1] + 1, node)
                target = Number(typ, "%" + TYPES[typ][0] + str(index))
            else:
                self.error(node, "only output/write_m calls may be used as statements")
            self.lower.assign(target, self.expr(args[1]), guard)
        elif kind == "CXXMemberCallExpr":
            self.expr(node, side_effect=guard is None)
        elif kind == "NullStmt":
            pass
        else:
            self.error(node, "unsupported statement: " + kind)

    def branch_with_labels(self, node, guard):
        # A goto may enter the branch without executing its condition. A guard
        # bit computed before the label would then be stale or uninitialized.
        children = node["inner"]
        end = self.lower.new_label()
        otherwise = self.lower.new_label() if len(children) == 3 else end
        if guard is not None:
            self.lower.jump(end, guard, negate=True)
        old_guard = self.lower.guard
        self.lower.guard = None
        try:
            self.lower.jump(otherwise, boolean(self.expr(children[0])), negate=True)
            self.statement(children[1])
            if len(children) == 3:
                self.lower.jump(end)
                self.lower.label(otherwise)
                self.statement(children[2])
            self.lower.label(end)
        finally:
            self.lower.guard = old_guard

    def loop(self, node, guard):
        children = node.get("inner", [])
        kind = node["kind"]
        head, end = self.lower.new_label(), self.lower.new_label()
        update = self.lower.new_label() if kind in ("ForStmt", "DoStmt") else head
        if guard is not None:
            self.lower.jump(end, guard, negate=True)
        # Once entered, control transfers implement activation. Predicating the
        # body with its outer condition would incorrectly re-read that condition
        # after an assignment changes it within the loop.
        old_guard = self.lower.guard
        self.lower.guard = None
        try:
            if kind == "ForStmt":
                if len(children) != 5 or children[1].get("kind"):
                    self.error(node, "for condition declarations are not implemented")
                initial, _, condition, increment, body = children
                if initial.get("kind"):
                    self.statement(initial)
            elif kind == "WhileStmt":
                if len(children) != 2:
                    self.error(node, "while condition declarations are not implemented")
                condition, body = children
                increment = None
            else:
                body, condition = children
                increment = None
            self.lower.label(head)
            if kind != "DoStmt" and condition.get("kind"):
                self.lower.jump(end, boolean(self.expr(condition)), negate=True)
            self.loops.append({"BreakStmt": end, "ContinueStmt": update})
            try:
                self.statement(body)
            finally:
                self.loops.pop()
            if update != head:
                self.lower.label(update)
            if increment is not None and increment.get("kind"):
                self.statement(increment)
            if kind == "DoStmt":
                self.lower.jump(head, boolean(self.expr(condition)))
            else:
                self.lower.jump(head)
            self.lower.label(end)
        finally:
            self.lower.guard = old_guard

    def compile(self):
        scans = []
        for n in self.top:
            if n["kind"] == "VarDecl":
                self.declaration(n, global_scope=True)
            elif n["kind"] == "FunctionDecl":
                if n.get("variadic"):
                    self.error(n, "variadic helpers are unsupported")
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
                boolean(self.expr(helper_body["inner"][0]["inner"][0], params))
            finally:
                self.lower, self.inputs, self.outputs, self.active = saved
        self.source_labels = {
            n["declId"]: self.lower.new_label()
            for n in walk(body)
            if n.get("kind") == "LabelStmt"
        }
        self.statement(body)
        if self.comm_observed - self.calls:
            fail("communication status read without an unconditional update per scan")
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
        prefix += self.lower.constant_rungs
        for target, value in self.init:
            if isinstance(target, Number):
                prefix.append(["LD %S13", "[" + target.code + ":=" + value.code + "]"])
                continue
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
        return self.lower.storage.finalize(self.lower.program, self.lower.constants)


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
