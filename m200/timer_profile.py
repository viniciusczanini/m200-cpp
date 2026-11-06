"""Documented timer profile and separately scoped observed native evidence.

Admission is based on the feature/profile contract, not on a whitelist of GUI
experiments. Permitted unobserved combinations remain unverified candidates.
"""

from .levels import functional_level
from .model import fail

BASES = {
    1: "OneMilliSeconds",
    10: "TenMilliSeconds",
    100: "OneHundredMilliSeconds",
    1000: "OneSecond",
}
# The omitted Base field is the documented/native minute default. Do not invent
# a serialized enum spelling for that default.
MINUTE_BASE_MS = 60000

# Historical observations ONLY; never an admission list or a claim that new
# modes/base/level combinations have been exercised. Preserve their identity.
OPTION_CONTEXTS = frozenset(
    {
        ("TON", True, False, 1000, "FunctLevelMan21_0"),
        ("TOF", True, False, 1000, "FunctLevelMan21_0"),
        ("TON", False, True, 1000, "FunctLevelMan21_0"),
    }
)


def validate_options(program, level_token=None):
    """Admit documented options using the actual project management token.

    Generic Functions p108 says retention >=3.3; Operating Guide and installed
    availability metadata say >=4.0. The disputed 3.3 boundary remains explicit;
    a stored true flag below that boundary is not proof of runtime support.
    """
    enabled = []
    for timer in program.timers.values():
        if type(timer.retentive) is not bool or type(timer.dynamic_preset) is not bool:
            fail("timer mode fields must be bool")
        if timer.kind == "TP" and timer.retentive:
            fail("retentive TP is unsupported in the Basic timer profile")
        if timer.retentive or timer.dynamic_preset:
            enabled.append(timer)
    if not enabled:
        return
    if type(level_token) is not str:
        fail("timer options require the actual management-level token")
    level = functional_level(level_token)
    for timer in enabled:
        if timer.retentive and level < (4, 0):
            fail(
                "timer retention requires functional level >=4.0 in the conservative "
                "profile; native 3.3/4.0 boundary remains unverified"
            )
        if timer.dynamic_preset and level < (12, 0):
            fail("timer dynamic preset requires functional level >=12.0")


def evidence_context(timer, level_token):
    """A classification for reporting, never a mutation of program evidence."""
    context = (timer.kind, timer.retentive, timer.dynamic_preset, timer.base_ms, level_token)
    return "observed_subset" if context in OPTION_CONTEXTS else "unverified_combination"
