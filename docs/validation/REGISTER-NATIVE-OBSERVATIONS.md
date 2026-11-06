# Native FIFO/LIFO editor and simulator observations

2026-11-06. Root personally opened, converted to Ladder, saved and freshly
reopened both exact TM200CE40T native Register diagnostics with **No error**.
Root then ran their separately saved watch derivatives in the official local
simulator and completed the bounded cases below. Both simulator sessions were
stopped through official Commissioning, with their panels and specific host
processes absent afterward.

These are **hand-built disposable native IL diagnostics**, not compiler-generated
products or implemented Register C++/IR/SDK/execution support. The editor is
Machine Expert Basic 1.4 build 484 in the local Mac Wine lab, at actual
`FunctLevelMan21_0`. No physical controller was operated. The
[result manifest](REGISTER-NATIVE-OBSERVATIONS.json) preserves full artifact,
input-record and exact PNG-copy identities.

## Exact native saves and watch derivatives

The source is the authentic memory baseline
`df5a293169d062d54b9d1f37909f15476cb7841d300c9b01a39c23ccd2924fbf`.
The original candidates change only the Registers collection and first POU's
rungs. Hardware is unchanged. Both candidate/save pairs retain six rungs and
twenty lexical IL instructions; editor spacing changes do not change their
tokens. Native conversion produced selected-Ladder rungs with entity counts
**10 / 10 / 10 / 10 / 11 / 11**. No graph was invented by this preparation.

| Mode | Original candidate SHA-256 prefix | Native editor-save prefix | Saved bytes | Native save / fresh reopen |
|---|---|---|---:|---|
| FIFO | `d3b49518e94a245c` | `85219725709cbe90` | 106,489 | [View](editor-evidence/register-native/fifo-save.png) / [Reopen](editor-evidence/register-native/fifo-reopen.png) |
| LIFO | `6a2fc9bd4be0ef27` | `8d04a2bc22bc2466` | 106,627 | [View](editor-evidence/register-native/lifo-save.png) / [Reopen](editor-evidence/register-native/lifo-reopen.png) |

Root saved writable P: copies through the editor, copied completed saved bytes
through the filesystem, opened the other mode and freshly reopened the exact
saved-byte clones. The FIFO save omits its used default R0 configuration as an
empty `Registers` collection; LIFO retains Address `%R0`, Index 0, Type `Lifo`.
Installed constructor/default-predicate/property metadata independently identifies
**Fifo=1** as the omitted configuration default, while Lifo=0 is a different mode.
These configuration facts do not establish runtime reset semantics.

The runtime derivatives add four animation rows `%R0.I`, `%R0.O`, `%R0.E`,
`%R0.F` to the actual native saves. Before their own editor save, WatchLists is
their only typed XML change. The actual runtime saves retain native raw IL,
hardware and Register mode configuration:

| Mode | Watch candidate SHA-256 prefix | Exact editor-saved runtime SHA-256 | Bytes |
|---|---|---|---:|
| FIFO | `0945b46d4842757f` | `2cb137138e7163ec69363017d11c40ec5f0f8e558cb60ad052c6c365a71c1963` | 107,500 |
| LIFO | `7e0452f621d6ff19` | `d330f04acc04925c19c43553f607cf9483c543614cababa4ae2292a710dd5ba4` | 107,638 |

The basic native saves' fresh reopens and the runtime watch saves are separate
stages; a fresh-reopen claim is not added for the watch derivatives. Their
`.smbp` lab files remain unpromoted, with hashes and source paths recorded in the
manifest. Existing candidate comments that say acceptance is pending retain the
historical preparation text.

## Controls and bounded outcomes

| Simulated input | Native program effect |
|---|---|
| `%I0.0` | Exclusive reset for these cases |
| `%I0.1` / `%I0.2` | Store / retrieve |
| `%I0.3` | Select input 22 when true, 11 otherwise, before the Register call |
| `%I0.4` | Write output-word sentinel 42 before the Register call |
| `%I0.5` | Drive both store and retrieve conditions in the same Register call |

`%Q0.0` and `%Q0.1` display Empty and Full. The four watch rows display input
word I, output word O, Empty E and Full F, in that order. There is no native
public depth operand in this diagnostic and no MW-backed software queue was
introduced. Individual store/retrieve controls were released between pulses.
The shared input creates simultaneous new I/O requests without relying on two
sequential GUI clicks.

| Case | Personally observed FIFO | Personally observed LIFO |
|---|---|---|
| Empty retrieval after O=42 | O remains 42, E=1/F=0. [Before](editor-evidence/register-native/fifo-output-sentinel.png), [after](editor-evidence/register-native/fifo-empty-pop-retains-sentinel.png) | O remains 42, E=1/F=0. [Before](editor-evidence/register-native/lifo-output-sentinel.png), [after](editor-evidence/register-native/lifo-empty-pop-retains-sentinel.png) |
| Store 11, hold Store while I becomes 22, release and freshly store 22 | Later drain returns 11 then 22; held data change did not add another item. [Data-change result](editor-evidence/register-native/fifo-held-store-data-change.png), [first](editor-evidence/register-native/fifo-pop11.png), [second/empty](editor-evidence/register-native/fifo-pop22-empty.png) | Later drain returns 22 then 11. [Data-change result](editor-evidence/register-native/lifo-after-held-store-data-change-and-release.png), [first](editor-evidence/register-native/lifo-pop22.png), [second/empty](editor-evidence/register-native/lifo-pop11-empty.png) |
| Shared fresh store/retrieve request with two items | Order/count retained before the above drain. [After shared request](editor-evidence/register-native/fifo-after-shared-both-edges.png) | Order/count retained before the above drain. [After shared request](editor-evidence/register-native/lifo-after-shared-both-edges.png) |
| Extra empty retrieval | O remains 22, E=1. [View](editor-evidence/register-native/fifo-extra-empty-pop.png) | O remains 11, E=1. [View](editor-evidence/register-native/lifo-extra-empty-pop.png) |
| Capacity fill with sixteen fresh stores of 22 | F=0 after 15; F=1 after 16. [15](editor-evidence/register-native/fifo-capacity15.png), [16](editor-evidence/register-native/fifo-capacity16-full.png) | F=0 after 15; F=1 after 16. [15](editor-evidence/register-native/lifo-capacity15.png), [16](editor-evidence/register-native/lifo-capacity16-full.png) |
| Attempted seventeenth store of 11, then shared I/O request while full | Full retained; subsequent sixteen retrievals return 22, E=0 after 15 and E=1 after 16; an extra retrieval retains O22. [Overflow](editor-evidence/register-native/fifo-seventeenth11-ignored-full.png), [shared release](editor-evidence/register-native/fifo-capacity-shared-release-still-full.png), [pop15](editor-evidence/register-native/fifo-capacity-pop15.png), [pop16](editor-evidence/register-native/fifo-capacity-pop16-empty.png), [extra](editor-evidence/register-native/fifo-capacity-pop17-retains22.png) | Subsequent sixteen retrievals return 22, E=0 after 15 and E=1 after 16; an extra retrieval retains O22. [Overflow](editor-evidence/register-native/lifo-seventeenth11-ignored-full.png), [pop15](editor-evidence/register-native/lifo-capacity-pop15.png), [pop16](editor-evidence/register-native/lifo-capacity-pop16-empty.png), [extra](editor-evidence/register-native/lifo-capacity-pop17-retains22.png) |

Capacity used sixteen identical 22 values and an ignored seventeenth 11. FIFO/LIFO
ordering is established separately by the two-item 11/22 cases; full-capacity
alternating-value order is not claimed. The earlier 89-position documentary
oracle per mode was not executed as an exact trace and is not copied into the
native-observation count.

A later root audit covers all **34 post-release retrieval captures** across the
two capacity runs. Each hash matches an already personally viewed state:
I11/O22/E0/F0 through retrieval 15, then I11/O22/E1/F0 at 16 and 17. This supports
the complete released-retrieval sequence without adding observations or unique
scans. The audit lists 68 on/off journal rows; pressed-input captures are not
audited for values. Its SHA-256 is
`d1bc5e5a6e6591a8c17d0ec5996680a3903adf6a46d5c1ba5c97623cc7fd05f4`.
The manifest pins that audit; the 31 observation records and copied PNG count are
unchanged.

## Corrected FIFO reading and cleanup

An initial reduced-image reading transcribed the FIFO full shared-request
release as I11/O0/E1/F0. Root and the reviewer reread the exact original-resolution
PNG and confirmed **I11/O0/E0/F1**. That release PNG is byte-identical to the
earlier overflow image, SHA-256
`f68223a8ab09cb0f9aebe053a3a92f9a010f133eb72311cfb2e3964c187ce7bf`.
The subsequent drain is consistent with the retained full queue. The JSON keeps
the initial transcription as historical and marks it resolved; no native or
monitor defect was observed from this case.

Root used official Stop simulator and personally viewed the
[LIFO cleanup](editor-evidence/register-native/lifo-simulator-stopped.png) and
[FIFO cleanup](editor-evidence/register-native/fifo-simulator-stopped.png).
The records confirm both panels absent, the respective simulator host PIDs
69384 and 96992 absent, and no local TCP 502 listener after each cleanup.
These after-cleanup checks do not claim a network transaction or absence of a
listener during RUN. No external client or memory forcing was used.

## Evidence limits and product boundary

The manifest records **31 personally viewed runtime checkpoints**, 21 unique
runtime PNG hashes and 186 journal actions: 92 LIFO and 94 FIFO, including the
FIFO stop sequence. Repeated images and release actions are not unique
controller scans. The GUI refresh interval is five seconds; fine timing,
same-scan coherence and transient behavior are not established. Thirty-seven
exact PNG copies, including native save/reopens and cleanup, total 14,574,278
bytes. All copied bytes/hashes are verified against their source images.

The observed domain is R0 with values 11/22 and sentinel 42. Reset/store/retrieve
collisions, ignored-edge history under held controls, first-call TRUE,
skipped/repeated calls and cold/warm/STOP lifecycle remain pending. Displayed
initial/reset O=0 in particular samples is not generalized into an unconditional
reset-output rule. Physical controller/firmware/load behavior remains unverified.

The [isolated configuration codec](REGISTER-CONFIG-FOUNDATION-RESULTS.md) is a
separate foundation. Whole-project Register compilation, C++, IR, SDK, graphics
generation and execution remain unsupported. This GUI stage ran no full suite,
CI or GitHub Actions; historical regression results remain unchanged. The
captured Wine lab views retain their existing **Untrusted DLL detected** banner;
no validation or integrity check was bypassed for this report. Earlier
preparation/typed-readback pending strings are preserved, with the later completed
cases and explicit cleanup records supplying this stage's final status.
