"""Normalize SR graphics independently, never converting a local END to MAST END."""

import copy

from .bits import memory_bits_used
from .numeric import memory_words_used
from .subroutine_contexts import context_view, context_views, static_operand_view
from .flow import destinations


def normalize_contexts(program, normalize):
    # Most source-lowered SRs are already exportable. Keep the exact Program
    # on a no-op, and do not copy or rewrite a leaf merely because Master needs
    # normalization. context_view owns its metadata dict and normalize owns any
    # actual changes, so probing a context does not mutate the caller.
    result = program
    resources = static_operand_view(result)
    reserved_bits = memory_bits_used(resources)
    reserved_words = memory_words_used(resources)
    reserved_labels = set().union(*(set(destinations(view)) for _, view in context_views(result)))
    initializers, initializer_origins = [], []
    summaries = {}
    for number in program.subroutines:
        definition = result.subroutines[number]
        view = context_view(result, definition, resources=True)
        normalized = normalize(view, _local_return=True,
            _reserved=(reserved_bits, reserved_words),
            _reserved_labels=reserved_labels, _contexts_done=True)
        if normalized is view:
            continue
        if result is program:
            result = copy.deepcopy(program)
        definition = result.subroutines[number]
        definition.rungs = normalized.rungs
        definition.origins = normalized.metadata.get("rung_origins", definition.origins)
        result.symbols.update(normalized.symbols)
        reserved_bits.update(memory_bits_used(normalized))
        reserved_words.update(memory_words_used(normalized))
        reserved_labels.update(destinations(normalized))
        resets = normalized.metadata.pop("subroutine_run_initializers", [])
        initializers.extend(resets)
        initializer_origins.extend(
            {"generated": "SR%s expression history RUN initialization" % number}
            for _ in resets
        )
        if normalized.metadata.get("native_logic_normalization") != view.metadata.get("native_logic_normalization"):
            summaries[str(number)] = normalized.metadata["native_logic_normalization"]
    if initializers:
        result.rungs = initializers + result.rungs
        result.metadata["rung_origins"] = initializer_origins + result.metadata.get(
            "rung_origins", [{"generated": "master source rung %s" % i}
                             for i in range(len(program.rungs))])
    result = normalize(result, _contexts_done=True)
    if summaries:
        result.metadata["subroutine_logic_normalization"] = summaries
    return result
