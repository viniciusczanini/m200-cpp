"""Call-aware scratch interference without flattening or unrolling SR bodies.

Return edges conservatively include every call continuation of that SR. This
can overestimate liveness, but never aliases a live caller value with a callee
write. Persistent objects remain uniquely allocated by Storage.
"""

from collections import deque

from .flow import ENDS, JUMPS, destinations, split_label
from .subroutine_contexts import call_target, context_views


def interference(program, registers, constants, aliases, effects):
    contexts = dict(context_views(program))
    nodes = [(number, i) for number, view in contexts.items() for i in range(len(view.rungs))]
    successors, steps, uses, definitions = {}, {}, {}, {}
    labels = {number: destinations(view) for number, view in contexts.items()}
    # Empty Master is legal in direct IR. There is no continuation to execute.
    master_entry = {(None, 0)} if program.rungs else set()
    returns = {number: set() for number in program.subroutines}

    def following(number, index):
        if index + 1 < len(contexts[number].rungs):
            return {(number, index + 1)}
        return master_entry if number is None else returns[number]

    for index, raw in enumerate(program.rungs):
        target = call_target(raw)
        if target is not None:
            returns[target].update(following(None, index))
    for number, index in nodes:
        _, rung = split_label(contexts[number].rungs[index])
        target = call_target(rung)
        # A terminal SR itself has no explicit virtual reads/writes; its actual
        # effects enter through the callee CFG. Predicate effects stay intact.
        body = rung[:-1] if target is not None else rung
        use, defined, _, acc, instructions = effects(body, registers, constants, aliases)
        early_return = any(line.split(maxsplit=1)[0] in ENDS for line in body[:-1])
        if early_return:
            # A conditional return can bypass later definite writes in this
            # rung. Do not let those writes kill a live caller/next-scan value.
            defined = set()
            use = set().union(*(read for read, _, _ in instructions))
            instructions = [(read, set(), written) for read, _, written in instructions]
        node = number, index
        uses[node], definitions[node], steps[node] = use, defined, instructions
        after = set(following(number, index))
        op, *args = rung[-1].split(maxsplit=1)
        if target is not None:
            entry = {(target, 0)}
            successors[node] = entry if acc is True else after if acc is False else after | entry
        elif op in (*JUMPS, *ENDS):
            take = True if op in ("JMP", "END") else (
                not acc if op in ("JMPCN", "ENDCN") and acc is not None else acc
            )
            destination = {(number, labels[number][args[0]])} if op in JUMPS else (
                master_entry if number is None else returns[number]
            )
            successors[node] = set(destination) if take is True else after if take is False else after | set(destination)
        else:
            successors[node] = after
        if early_return:
            successors[node].update(master_entry if number is None else returns[number])

    predecessors = {node: set() for node in nodes}
    for node, targets in successors.items():
        for target in targets:
            predecessors[target].add(node)
    live = {node: set() for node in nodes}
    pending = deque(reversed(nodes))
    queued = set(nodes)
    while pending:
        node = pending.popleft()
        queued.remove(node)
        out = set().union(*(live[target] for target in successors[node]))
        incoming = uses[node] | (out - definitions[node])
        if incoming != live[node]:
            live[node] = incoming
            for previous in predecessors[node] - queued:
                pending.append(previous)
                queued.add(previous)
    graph = {ref: set() for ref in registers}
    for node in nodes:
        out = set().union(*(live[target] for target in successors[node]))
        for read, defined, written in reversed(steps[node]):
            for target in written:
                for other in out:
                    if other != target and registers[other].bank == registers[target].bank:
                        graph[target].add(other)
                        graph[other].add(target)
            out = (out - defined) | read
    return graph
