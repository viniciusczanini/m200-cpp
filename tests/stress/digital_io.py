#!/usr/bin/env python3
"""All 24 embedded inputs x 16 outputs, polarities and output-image state."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from expression_edges import verify
from m200.frontend import compile_source

SEED = 20020261115


def main():
    rng = random.Random(SEED)
    values = (
        [0, (1 << 24) - 1]
        + [1 << i for i in range(24)]
        + [((1 << 24) - 1) ^ (1 << i) for i in range(24)]
    )
    values += [rng.randrange(1 << 24) for _ in range(256 - len(values))]
    frames = [{"inputs": {i: bool(v & (1 << i)) for i in range(24)}} for v in values]
    results = []
    bindings = set()
    with tempfile.TemporaryDirectory(prefix="m200-digital-io-") as directory:
        work = Path(directory)
        for inverted in (False, True):
            for offset in range(24):
                name = f"route_{offset}_inverted_{int(inverted)}"
                source = work / (name + ".cpp")
                source.write_text(
                    "#include <plc.hpp>\nvoid scan(){"
                    + "".join(
                        f"plc::output({q},{'!' if inverted else ''}plc::input({(offset + q) % 24}));"
                        for q in range(16)
                    )
                    + "}"
                )
                expected = [
                    [
                        bool(value & (1 << ((offset + q) % 24))) != inverted
                        for q in range(16)
                    ]
                    for value in values
                ]
                verify(compile_source(source), frames, expected, work, name, source)
                bindings.update(((offset + q) % 24, q, inverted) for q in range(16))
                results.append(dict(case=name, scans=len(frames), status="pass"))
                print(f"PASS: {name} / {len(frames)} scans", flush=True)
        source = work / "conditional_image.cpp"
        source.write_text(
            "#include <plc.hpp>\nvoid scan(){"
            + "".join(
                f"if(plc::input(0)){{plc::output({q},plc::input({q + 1}));}}"
                f"if(plc::input(17)){{plc::output({q},!plc::output_state({q}));}}"
                f"if(plc::input(18)){{plc::output({q},false);}}"
                for q in range(16)
            )
            + """
if(plc::input(19)){plc::write_output_bits_i16(0,8,plc::read_input_bits_i16(0,8));}
if(plc::input(20)){plc::write_output_bits_i16(8,8,plc::read_output_bits_i16(0,8));}
}"""
        )
        state = [False] * 16
        expected = []
        state_frames = frames + frames
        for value in values + values:
            if value & 1:
                state = [bool(value & (1 << (q + 1))) for q in range(16)]
            if value & (1 << 17):
                state = [not bit for bit in state]
            if value & (1 << 18):
                state = [False] * 16
            if value & (1 << 19):
                state[:8] = [bool(value & (1 << q)) for q in range(8)]
            if value & (1 << 20):
                state[8:] = state[:8]
            expected.append(list(state))
        verify(
            compile_source(source),
            state_frames,
            expected,
            work,
            "conditional_image",
            source,
        )
        results.append(
            dict(case="conditional_image", scans=len(state_frames), status="pass")
        )
    if len(bindings) != 24 * 16 * 2:
        raise AssertionError("incomplete I/O matrix")
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "tests/stress/expression_edges.py",
        ROOT / "tests/fixtures/synthetic.smbp",
    ]
    report = dict(
        seed=SEED,
        target="TM200CE40T",
        cases=results,
        scans=sum(r["scans"] for r in results),
        input_indices=list(range(24)),
        output_indices=list(range(16)),
        distinct_input_output_polarity_bindings=len(bindings),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        official_editor="pending",
        physical_plc="pending",
        electrical_io="not-tested-locally",
        exported_roundtrip="actual exported IL -> C++ -> compile -> new XML -> load and execute",
    )
    (ROOT / "docs/validation/DIGITAL-IO-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans / {len(bindings)} I/O/polarity bindings; C++, IL, reverse, JSON, normalization, XML and actual exported C++ recompilation"
    )


if __name__ == "__main__":
    main()
