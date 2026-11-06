"""G01 restricted C++ integration, kept separate from the general AST walker."""

import re
from .boolean_banks import BooleanConfig, word_bit, word_object, validate_operand
from .model import address
from .numeric import boolean

DECLARATIONS = ("plc::BooleanContext", "plc::BooleanWord")
CALLS = ("plc::read_bit", "plc::write_bit", "plc::set_bit", "plc::reset_bit")


def text(owner, node):
    from .frontend import strip
    node = strip(node)
    raw = node.get("value", "")
    # Address literals are ASCII and canonical; escapes/macros cannot introduce
    # opcodes, arbitrary source fragments or hidden address characters.
    m = re.fullmatch(r'"([%A-Za-z0-9.:]+)"', raw)
    if node.get("kind") != "StringLiteral" or m is None:
        owner.error(node, "Boolean address must be an ordinary canonical ASCII literal")
    value = m[1]
    if any(len(part) > 1 and part.startswith("0") for part in re.findall(r"[0-9]+", value)):
        owner.error(node, "Boolean address decimal components must be canonical (no leading zeroes)")
    return value


def prepare(owner, tree, walk, reserved, reserved_words):
    cfg = BooleanConfig()
    seen_context = False
    for node in walk(tree):
        if node.get("kind") != "VarDecl" or node.get("type", {}).get("qualType") not in DECLARATIONS:
            continue
        typ = node["type"]["qualType"]
        ctor = next((n for n in node.get("inner",[]) if n.get("kind") == "CXXConstructExpr"),None)
        args = [] if ctor is None else ctor.get("inner",[])
        if typ == "plc::BooleanContext":
            if seen_context or len(args) != 2:
                owner.error(node,"one global BooleanContext with two literal bool flags is required")
            from .frontend import strip
            flags = [int(strip(n)["value"]) if strip(n).get("kind") == "CXXBoolLiteralExpr" else owner.const(n) for n in args]
            if any(v not in (0,1) for v in flags):
                owner.error(node,"BooleanContext flags must be true or false")
            cfg.input_image_stable,cfg.native_expression_edges = map(bool,flags)
            seen_context = True
        elif typ == "plc::BooleanWord":
            if len(args) != 1:
                owner.error(node,"BooleanWord requires one IO word address")
            value = text(owner,args[0])
            if value in cfg.word_objects:
                owner.error(node,"duplicate BooleanWord identity")
            word_object(value)
            cfg.word_objects.append(value)
    cfg.validate()
    for node in walk(tree):
        if node.get("kind") != "CallExpr":
            continue
        name,args = owner.call(node)
        if name not in CALLS:
            continue
        if len(args) != (1 if name == "plc::read_bit" else 2):
            owner.error(node,"invalid Boolean operand API arity")
        arg = text(owner,args[0])
        if ":X" in arg:
            bank,index,_,_ = word_bit(arg)
            if bank == "MW":
                if index >= (owner.word_count or 8000):
                    owner.error(node,"Boolean word bit outside WordMemory image")
                reserved_words.add(index)
        else:
            kind,index = address(arg)
            if kind not in ("M", "I0.", "Q0.", "S", "constant"):
                owner.error(node,"use the configured native resource's typed methods for block properties")
            if kind == "M":
                if index >= (owner.bit_count or 1024):
                    owner.error(node,"Boolean bit outside BitMemory image")
                reserved.add(index)
    owner.boolean_config = cfg
    owner.boolean_stacks = {}
    owner.boolean_stack_conditional_depth = 0


def attach(owner):
    cfg = owner.boolean_config
    if cfg != BooleanConfig():
        owner.lower.program.boolean = cfg


def declaration(owner,node,guard,global_scope):
    typ = node.get("type",{}).get("qualType")
    if typ in DECLARATIONS:
        if not global_scope:
            owner.error(node,"Boolean configuration must be global")
        return True
    if typ == "plc::BooleanStack":
        if global_scope or guard is not None or owner.active or owner.in_subroutine is not None:
            owner.error(node,"BooleanStack must be an unconditional local scan object")
        owner.boolean_stacks[node["id"]] = []
        return True
    return False


def operand(owner,node,action=None):
    arg = text(owner,node)
    from .il import bit_operand
    bit_operand(arg, action is not None and not (arg.startswith("%S") and arg[2:].isdigit()))
    validate_operand(owner.lower.program,arg,action)
    if arg.startswith("%I0.") and ":" not in arg:
        owner.inputs.setdefault(int(arg[4:]), arg)
    elif arg.startswith("%Q0.") and ":" not in arg:
        owner.output(int(arg[4:]))
    return arg


def read(owner,args,node):
    arg = operand(owner,args[0])
    # Read at the C++ evaluation point. Do not move hardware/system reads over
    # other operands, writes or a call into a preempting context.
    if owner.lower.guard is None:
        return owner.lower.copy(arg,"boolean_operand_snapshot")
    out = owner.lower.bit("boolean_operand_snapshot")
    end = owner.lower.new_label()
    owner.lower.assign(out,"0")
    owner.lower.jump(end,owner.lower.guard,negate=True)
    owner.lower.rung("LD " + arg,"ST " + out)
    owner.lower.label(end)
    return out


def write(owner,name,args,node,guard):
    action = {"plc::write_bit":"ST","plc::set_bit":"S","plc::reset_bit":"R"}[name]
    arg = operand(owner,args[0],action)
    value = boolean(owner.expr(args[1]))
    if action == "ST":
        owner.lower.assign(arg,value,guard)
    else:
        signal = value if guard is None else owner.lower.binary("&&",guard,value)
        owner.lower.rung("LD " + signal,action + " " + arg)


def member(owner,node,env):
    from .frontend import strip
    children = node.get("inner",[])
    method = children[0]
    obj = strip(method.get("inner",[{}])[0])
    ref = obj.get("referencedDecl",{}).get("id")
    if ref not in owner.boolean_stacks:
        return False,None
    if owner.active:
        owner.error(node,"BooleanStack operations cannot be hidden inside pure helpers")
    entries = owner.boolean_stacks[ref]
    name,args = method.get("name"),children[1:]
    if name in ("push", "pop") and owner.boolean_stack_conditional_depth:
        owner.error(node, "BooleanStack push/pop in a short-circuit operand requires dynamic stack state; use an explicit balanced if branch")
    if name == "push" and len(args) == 1:
        if len(entries) == 32:
            owner.error(node,"BooleanStack exceeds documented32-expression capacity")
        value = boolean(owner.expr(args[0],env))
        target = owner.lower.bit("boolean_stack_snapshot")
        owner.lower.assign(target,value,owner.lower.guard)
        entries.append((target,owner.lower.guard))
        return True,None
    if name in ("peek","pop") and not args:
        if not entries:
            owner.error(node,"BooleanStack " + name + " without push")
        if name == "pop" and entries[-1][1] != owner.lower.guard:
            owner.error(node,"BooleanStack pop crosses a conditional execution context")
        value = owner.lower.copy(entries[-1][0],"boolean_stack_result")
        if name == "pop":
            entries.pop()
        return True,value
    owner.error(node,"unsupported BooleanStack method/arity")


def open_stacks(owner):
    return {key:tuple(values) for key,values in owner.boolean_stacks.items() if values}


def require_stacks(owner, expected, node):
    """Each alternative starts and finishes with the post-condition stack."""
    if open_stacks(owner) != expected:
        owner.error(node, "BooleanStack must be balanced within each branch context")
