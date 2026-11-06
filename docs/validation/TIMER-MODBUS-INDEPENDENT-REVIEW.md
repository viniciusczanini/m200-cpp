# Independent timer-option and Modbus bit-binding review

Date: 2026-11-06. **No outstanding findings** remain in the frozen implementation.
The review changed no product code, existing tests or fixtures. Two early test
issues were corrected by the timer author before freeze: the source-equals-output
case now preserves the existing refusal, and the hardware negative uses the real
`PtoObject/RefInput` field.

The timer policy admits only TON retention, TOF retention and TON dynamic preset,
each separately at a 1000 ms base and exact `FunctLevelMan21_0`. Import and export
use the actual parsed XML token; forged Program metadata cannot promote or deny
that authority. Other levels, bases, timer kinds and combined options remain
gated. Ordinary false-option behavior, strict bool/property validation, hardware
checks, staged replacement and the `project.BASES` alias are preserved.

Modbus XML adds only `I=1` and `Q=2`: READ I uses FC2, READ Q uses FC1, and WRITE Q
uses FC15. Existing validation retains direction, remote-bit and packed-local-MW
bounds, exact parameter types, unknown/duplicate-field rejection and graph gates.
WRITE I/IW, unproven single-write types, WRITE_READ_VAR and unsupported graph
forms remain rejected. Timer state, SDK and protocol code did not change.

| Verification | Result |
|---|---|
| New regressions reviewed | 15 timer-option tests; 10 Modbus bit-binding tests |
| Independent focused runs | 26 timer/XML/alias tests in 5.572 s; 41 communication tests in 2.467 s |
| Timer policy probes | 600 kind/flag/base/token combinations; 12 actual-template/forged-metadata exports; six sparse TM254 preset endpoints; malformed tokens and same-path preservation |
| Modbus probes | 43 XML/export boundary and malformed-field cases; three literal wire/padding cases |
| Existing export-authority controls | Five actual-level/serial-role cases with forged metadata |
| Root's single combined local run | 496 tests in 202.294 s; exit 0; all 124 input pins unchanged |

The focused groups include the new regressions; their counts are not additional
combined-suite tests. Probe expectations were independent literals rather than
values imported from production policy/packing helpers. Sources and rejected
destinations remained byte-identical. The promoted timer fixture and all three
Modbus fixtures independently matched preserved root/lab originals.

The focused communication group includes an existing TCP test on an ephemeral
localhost port. The new independent probes opened no sockets. No external or
PLC network, port 502, serial device, GUI or Wine operation was performed by this
reviewer. Root coordinated the full run; the reviewer did not repeat it.

This establishes local code/binding/authorization checks. It does not establish
fine timer timing, other option contexts, lifecycle behavior, official Modbus
transactions or physical-controller compatibility. Root's settled official timer
observations remain scoped by their [evidence record](TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.json).
Exact cases, reviewed file hashes, log identities and remaining limits are in the
[machine-readable review](TIMER-MODBUS-INDEPENDENT-REVIEW.json).
