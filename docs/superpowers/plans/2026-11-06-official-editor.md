# Official editor interoperability and public repository

**Goal:** validate exact compiler artifacts in the user's official Machine Expert
Basic Wine lab, fix observed interoperability errors, and publish the project
with English documentation and GitHub Actions disabled.

**Scope:** the full TM200CE40T parity goal remains unchanged. Wine editor,
official local simulator, external TCP and physical hardware evidence are separate.
No automatic physical PLC transfer, firmware change or load actuation.

**Execution:** root owns GUI/bridge and publishing; delegated agents own the
closed hardware profile/parser, English docs and skill dialog helpers. All tests
and builds run locally. Preserve user projects, originals and LFS hooks.

## Checks

- [x] Read schneider-basic-mac skill and fresh lab state; preserve original bytes.
- [x] Reopen the authentic TM200CE40T memory baseline and observe No error.
- [x] Reproduce and fix real inactive-profile/section-number import failures.
- [x] Improve blank native dialog capture and guarded file-dialog controls.
- [x] Generate and inspect exact memory and I/O candidates; record I/O failure.
- [x] Save/reopen memory candidate and compare actual saved IL/configuration/C++.
- [x] Exercise official local simulator memory 0/1/0 without hardware endpoints.
- [x] Record byte hashes, screenshots, versions, outcomes and unresolved limits.
- [x] Prepare six combined state/array, timer/counter and numeric candidates;
      compare 276 distinct candidate frames locally, including numeric values.
- [ ] Confirm or reject the culture-only remedy for false I/O resource claims.
- [ ] After basic I/O passes, open/run combined candidates in the official lab.
- [x] Prepare English README, setup and architecture documentation.
- [x] Create personal public repository and disable Actions before first push.
- [ ] Run relevant local checks, review changes and publish verified scope.

Metadata inspection of installed assemblies is authorized for interoperability.
Only factual schema/enum findings and source digests belong in the repository;
vendor binaries, extracted proprietary implementation and Wine prefixes do not.
