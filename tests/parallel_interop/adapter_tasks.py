"""G18 public config boundaries; no host timing is represented as PLC timing."""

from dataclasses import asdict
import json
from pathlib import Path

from harness import PendingContract, equal, refused, require


def run_case(request, context):
    scenario = request["scenario"]
    if scenario["mode"].startswith("cpp_") or scenario["mode"] == "native_project":
        from adapter_cpp import run_case as cpp_case

        return cpp_case(request, context)
    try:
        from m200.task_config import TaskConfig, EventTask
    except ImportError as error:
        raise PendingContract("G18 task configuration API not integrated") from error
    from m200.model import CompileError

    def config(values):
        values = dict(values)
        if "events" in values:
            values["events"] = tuple(EventTask(**entry) for entry in values["events"])
        if "functional_level" in values:
            values["functional_level"] = tuple(values["functional_level"])
        return TaskConfig(**values)

    if scenario["mode"] == "task_constraints":
        observations = [asdict(config(values)) for values in scenario["valid"]]
        for values in scenario["invalid"]:
            refused(lambda values=values: config(values), (CompileError, ValueError), str(values))
        result = {"accepted": len(observations), "refused": len(scenario["invalid"])}
    else:
        raise PendingContract("G18 scheduler/lifecycle adapter awaits final integrated Machine contract: " + scenario["mode"])
    path = Path(context["work"]) / "task-configuration-observations.json"
    path.write_text(json.dumps({"actual_configs": observations, "observed": result}, indent=2, sort_keys=True) + "\n")
    return {"observed": result, "evidence": {"configuration": str(path)}}
