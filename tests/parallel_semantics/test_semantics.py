"""Collected only for the coordinator-released local freeze; no implicit skips."""

from pathlib import Path
import tempfile
import unittest

from .adapters import execute
from .catalog import inventory
from .contracts import PendingOracleError


ROOT = Path(__file__).resolve().parents[2]


def semantic_case(case, binding, engine, repo=ROOT):
    # The test class is local so unittest discovery does not try to instantiate
    # a parameterized TestCase before load_tests builds the explicit inventory.
    class SemanticCase(unittest.TestCase):
        def id(self):
            return "parallel_semantics."+case.name+"."+engine

        def shortDescription(self):
            return self.id()

        def runTest(self):
            if case.oracle_status != "prepared" or case.expected is None:
                raise PendingOracleError(case.name+": "+case.oracle_status+"; "+case.basis)
            with tempfile.TemporaryDirectory(prefix="m200-semantic-") as folder:
                actual = execute(binding,engine,case.adapter_input(),Path(repo),Path(folder))
            self.assertEqual(actual,case.expected,case.name+"; "+case.basis)

    return SemanticCase()


def suite(groups=None, engines=("vm","sdk"), repo=ROOT, names=None):
    cases = []
    for case,state,binding in inventory():
        if state == "DEFERRED_VERSION":
            continue
        if groups and not set(case.groups).intersection(groups):
            continue
        if names and case.name not in names:
            continue
        cases.extend(semantic_case(case,binding,engine,repo) for engine in engines)
    if not cases:
        raise ValueError("Selection contains no prepared priority cases; empty selection is not success")
    return unittest.TestSuite(cases)


def load_tests(loader, tests, pattern):
    return suite()
