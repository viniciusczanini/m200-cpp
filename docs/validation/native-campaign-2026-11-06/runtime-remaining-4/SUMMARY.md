# Remaining four native runtime profiles

One finite pass was completed on each official local simulator project. **40 output checks passed, with no observed mismatch.** All 65 recorded panel observations are retained, including observations without a predeclared oracle. This is limited runtime evidence, not full native parity or a successful Modbus exchange.

| Profile | Result and observed outputs | Limit |
|---|---|---|
| DR clock lights | PASS minimum controls. Eight enabled samples: 74,74,106,106,105,76,108,74. Three cams and both Q5 phases observed; inhibit80, disabled64. | No period or PLC-scan measurement; MW10/MW11 not watched. |
| RTC clock lights | PASS minimum controls. RTC06Nov2026 21:40. Samples13,14,14,13,14,13,13,13; inhibit24, disabled8. | No RTC adjustment or period claim. |
| Schedule reservation | PASS Q controls: {}→0, {0,1}→3, {4,7}→8, {5}→4. RTC21:42. | M0/M1 were reserved in properties, but live values were not visible: PENDING. Q arithmetic alone does not prove schedule activation. |
| Modbus READ without peer | Native READ error path observed: Q0→4held→0. Existing online Ladder rungs showed COMMERROR=6 and OPERERROR=0. | Numeric expected=null; cause UNKNOWN. Not classified as timeout or transaction success. No external client/peer or physical PLC. |

Inputs in braces are high; all others are low. Modbus I3/I4 and Abort remained low. Inactive writer/exchange diagnostics were directly observed as0 in the same existing Ladder view. No buffer-retention, Busy transient or Abort-history claim is made.

The four Q4 glyph refusals remain in the records. The threshold was unchanged; manual readings were used for inhibit80/24, with identical-hash counterparts documented. PNG bytes are original and deduplicated by SHA256; timestamps and original capture names remain in the journals. Relative image paths resolve from this bundle root. Command-only host roots use the documented @repo/@lab/@shared-projects/@control aliases.

Official Stop simulator completed after every profile. All four cleanup records show no simulator window/process or TCP502 listener, and all four official project hashes were unchanged. Final editor: No error / Not Connected. No project save, source/SDK/helper change or RTC write occurred. GUI control was returned to the coordinator. Earlier timebox history and the three excluded unknown probes remain unchanged.

Evidence: [structured summary](summary.json), [screenshot index](screenshot-index.json), [commands](logs/commands.jsonl), [input pins](input-pins.json), and [full-editor review list](full-editor-review.json). Per-profile events and cleanup records are under logs/.
