"""Reconstruct sequence resources from typed configuration and real operands."""
from .sequences import FAMILIES, CLASSES


def read_cpp(ref):
    family, index, prop = ref
    if family == "DR":
        return f"drum_{index}.{'step' if prop == 'S' else 'full'}()"
    return f"{family.lower()}_{index}.bit({prop})"


def declarations(program):
    lines = []
    for family, name in FAMILIES.items():
        for index, cfg in sorted(getattr(program, name).items()):
            args = [str(index)]
            if family == "DR":
                args.append(str(cfg.steps))
                for cam in cfg.cams:
                    memory = cam.output.startswith("%M")
                    bank = "Memory" if memory else "Output"
                    address = cam.output[2:] if memory else cam.output[4:]
                    args.append(f"plc::DrumCam{{{cam.slot},plc::DrumOutput::{bank},{address},{cam.mask}}}")
            prefix = "drum" if family == "DR" else family.lower()
            lines.append(f"plc::{CLASSES[family]} {prefix}_{index}{{{','.join(args)}}};")
    return lines
