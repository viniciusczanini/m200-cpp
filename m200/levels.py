"""Observed editor management tokens are ordinals, not human feature levels.

Machine Expert Basic 1.4 build 484 enum/resources and assembly identities are
recorded in docs/capabilities/EDITOR-INTEROP-FACTS.json. This map establishes
the selected version label, not controller/firmware support for every feature.
"""

from .model import fail

FUNCTIONAL_LEVELS = {
    "FunctLevelMan1_0": (1, 0),
    "FunctLevelMan2_0": (2, 0),
    "FunctLevelMan3_0": (3, 0),
    "FunctLevelMan4_0": (3, 1),
    "FunctLevelMan5_0": (3, 2),
    "FunctLevelMan6_0": (3, 3),
    "FunctLevelMan7_0": (4, 0),
    "FunctLevelMan8_0": (4, 1),
    "FunctLevelMan9_0": (5, 0),
    "FunctLevelMan10_0": (5, 1),
    "FunctLevelMan11_0": (6, 0),
    "FunctLevelMan12_0": (6, 1),
    "FunctLevelMan13_0": (6, 2),
    "FunctLevelMan14_0": (10, 0),
    "FunctLevelMan15_0": (10, 1),
    "FunctLevelMan16_0": (10, 2),
    "FunctLevelMan17_0": (11, 0),
    "FunctLevelMan18_0": (12, 0),
    "FunctLevelMan19_0": (12, 1),
    "FunctLevelMan20_0": (13, 0),
    "FunctLevelMan21_0": (14, 0),
}


def functional_level(token):
    if token not in FUNCTIONAL_LEVELS:
        fail("unverified or invalid management-level token: " + str(token))
    return FUNCTIONAL_LEVELS[token]
