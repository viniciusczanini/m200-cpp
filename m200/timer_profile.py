"""Established Basic timer XML base names; minute base remains omitted.

TenMilliSeconds is backed by the exact TM200CE40T editor-saved and freshly
reopened fixture in tests/fixtures/official_tm200ce40t_timer_10ms.provenance.json.
This mapping does not relax retentive/dynamic gates or establish physical timing.
"""

BASES = {
    1: "OneMilliSeconds",
    10: "TenMilliSeconds",
    100: "OneHundredMilliSeconds",
    1000: "OneSecond",
}
