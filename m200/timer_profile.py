"""Observed Basic timer XML bindings and narrowly established option contexts.

TenMilliSeconds is backed by the exact TM200CE40T editor-saved and freshly
reopened fixture in tests/fixtures/official_tm200ce40t_timer_10ms.provenance.json.
The three option contexts below have separate official simulator observations
and flags-off controls; they establish neither other contexts nor physical timing.
"""

from .levels import functional_level
from .model import fail

BASES = {
    1: "OneMilliSeconds",
    10: "TenMilliSeconds",
    100: "OneHundredMilliSeconds",
    1000: "OneSecond",
}

# Exact context admission, not a minimum-level claim. See the saved fixture's
# provenance and TIMER-OPTIONS-OFFICIAL-OBSERVATIONS for the evidence limits.
OPTION_CONTEXTS = frozenset(
    {
        ("TON", True, False, 1000, "FunctLevelMan21_0"),
        ("TOF", True, False, 1000, "FunctLevelMan21_0"),
        ("TON", False, True, 1000, "FunctLevelMan21_0"),
    }
)


def validate_options(program, level_token=None):
    """Check already validated timers against the actual XML management token.

    Ordinary timers keep their existing level policy. A true option requires
    an exact observed context; Program metadata is never an authority here.
    """
    options = []
    for timer in program.timers.values():
        if type(timer.retentive) is not bool or type(timer.dynamic_preset) is not bool:
            fail("timer mode fields must be bool")
        if timer.retentive or timer.dynamic_preset:
            options.append(timer)
    if not options:
        return
    message = "timer-mode functional-level mapping is unverified for SMBP"
    if type(level_token) is not str:
        fail(message + ": actual management-level token is required")
    functional_level(level_token)
    if any(
        (
            timer.kind,
            timer.retentive,
            timer.dynamic_preset,
            timer.base_ms,
            level_token,
        )
        not in OPTION_CONTEXTS
        for timer in options
    ):
        fail(message)
