This is a review from an agent with an automatic prompt from the reviewer

> Superseded by the [audited review index](review_fast_check_stack_audit_20261006.md). Use its corrected reviews and branch tips; the fractional-clamp recommendation below is withdrawn. The original index is preserved below.

# fast_check stack: review index and landing plan

All eleven requested PRs have now received a single-reviewer pass: the nine incremental verifier layers and the two independent rocisa/lint changes. The original root review is preserved; this index updates its scope and CI observations. The reviews use public source, descriptions, local experiments and CI status, without consulting GitHub reviews or discussion comments.

There are 17 focused local suggestion commits, including the relocation of an existing stack fix. Each per-PR branch starts at that PR's exact submitted head. The combined branch `review/fast-check-stack-suggestions-20261006` starts at stack tip [`a84d460b8a651810ce9e0ce29f74af1bb4940da3`](https://github.com/ROCm/rocm-libraries/commit/a84d460b8a651810ce9e0ce29f74af1bb4940da3) and ends at [`2d8c81e5c796e145ab049127818b0cc869e5bd26`](https://github.com/newling/rocm-libraries/commit/2d8c81e5c796e145ab049127818b0cc869e5bd26). It integrates the stack suggestions for validation; the independent lint fixes remain on their own branch. Nothing has been pushed or posted, and no PR or CI run was changed.

## Reviews and concrete next actions

Rows for the verifier stack are in dependency order. Each linked review records its exact head, local branch, findings, fix commits and validation limits.

| PR | Reviewed head | Review and next action |
| --- | --- | --- |
| [#12876](https://github.com/ROCm/rocm-libraries/pull/12876) | [`9ea6be093cc8`](https://github.com/ROCm/rocm-libraries/commit/9ea6be093cc8ef21e7b4a6b62431e0d2206c0035) | [Base verifier review](review_pr12876.md): apply the empty-output fix. Its separate numerical-failure item now has the tracked quarantine described in #13022. |
| [#12960](https://github.com/ROCm/rocm-libraries/pull/12960) | [`8351692d684b`](https://github.com/ROCm/rocm-libraries/commit/8351692d684bd9a3ad55b6d0e44a8fae913aedc1) | [4 GiB placement review](review_pr12960.md): use RAII for workspace ownership so placement skips/failures release it. |
| [#13005](https://github.com/ROCm/rocm-libraries/pull/13005) | [`c6ec02e372e5`](https://github.com/ROCm/rocm-libraries/commit/c6ec02e372e5a3452f83c9e8e6d943406bfdc22c) | [Repeated-launch review](review_pr13005.md): move the actual Stream-K selection guard here from #13022, where the coverage requirement first appears. |
| [#13013](https://github.com/ROCm/rocm-libraries/pull/13013) | [`de8179d56d3d`](https://github.com/ROCm/rocm-libraries/commit/de8179d56d3dc8c790668eb505ec74028050a720) | [Patterns and bounds review](review_pr13013.md): guarantee retained sparse values are nonzero and isolate pattern state between test threads. Preserve the independently landing FNUZ fix. |
| [#13015](https://github.com/ROCm/rocm-libraries/pull/13015) | [`396f1c517591`](https://github.com/ROCm/rocm-libraries/commit/396f1c5175913d0ddd19eb48d12e948ad6cad96c) | [Side-output review](review_pr13015.md): bound bias-gradient reductions independently and reject fractional clamp bounds that violate the checker contract. |
| [#13021](https://github.com/ROCm/rocm-libraries/pull/13021) | [`c8d9134aa913`](https://github.com/ROCm/rocm-libraries/commit/c8d9134aa913d7cc2039c272545e463d9c1107d9) | [Size/stress review](review_pr13021.md): no new source defect found. Record executed/skipped counts from a suitable large-memory run; the new tier does not itself schedule a job. |
| [#13022](https://github.com/ROCm/rocm-libraries/pull/13022) | [`97e1481b4512`](https://github.com/ROCm/rocm-libraries/commit/97e1481b451214c125b22a7b5b9274d1d3cb0f7f) | [Edge-configuration review](review_pr13022.md): remove the relocated guard's duplicate and confirm whether ROCM-32277 needs to suppress M=1031 as well as M=4099. No speculative quarantine edit was made. |
| [#13025](https://github.com/ROCm/rocm-libraries/pull/13025) | [`f0d1510b27bc`](https://github.com/ROCm/rocm-libraries/commit/f0d1510b27bc3c7fc158bb628b319c5bf6a80694) | [Hunt-runner review](review_pr13025.md): stop surviving children, validate executable/load arguments, preserve logs across invocations and run the regressions in CPU CI. |
| [#13031](https://github.com/ROCm/rocm-libraries/pull/13031) | [`a84d460b8a65`](https://github.com/ROCm/rocm-libraries/commit/a84d460b8a651810ce9e0ce29f74af1bb4940da3) | [Full MX review](review_pr13031_full_20261006.md): count retained MX host buffers and directly test both FP8 decoding tables. |
| [#13027](https://github.com/ROCm/rocm-libraries/pull/13027) | [`2ac9fca28440`](https://github.com/ROCm/rocm-libraries/commit/2ac9fca28440087070e0e8629b4df818b63620ac) | [Independent rocisa review](review_pr13027.md): no source change requested; resolve or explain the outstanding automated checks. |
| [#13060](https://github.com/ROCm/rocm-libraries/pull/13060) | [`0e3cc4944a99`](https://github.com/ROCm/rocm-libraries/commit/0e3cc4944a998f61b3f1f0934538abf396cbf48f) | [Independent carry-lint review](review_pr13060.md): fix CFG carry ordering, implicit addk inputs, scalar-source handling and objdump label aliases. |

## Local commit handoff

For #12876 the branch is `review/pr12876-suggestions`. Every other per-PR branch is named `review/prNNNN-suggestions-20261006`. The branches for #13021, #13022 and #13027 contain no added commits. Apply a PR's commits in the order shown; later commits on the same branch may depend on earlier ones.

| Layer and item | Per-PR commit | Equivalent on combined branch |
| --- | --- | --- |
| #12876 empty outputs | [`67ca40766d0`](https://github.com/newling/rocm-libraries/commit/67ca40766d0896f69c15361a6f4856c4bd216152) | [`c7a5b39e5f2`](https://github.com/newling/rocm-libraries/commit/c7a5b39e5f280774ee1071f5b431cb1b628347c1) |
| #12960 workspace lifetime | [`81db14636ea`](https://github.com/newling/rocm-libraries/commit/81db14636ea8f61a3291b59e0d0a5cd1d288c591) | [`60316fee474`](https://github.com/newling/rocm-libraries/commit/60316fee4743ac1118090eecf1197956762a1302) |
| #13005 Stream-K guard relocation | [`6503895955f`](https://github.com/newling/rocm-libraries/commit/6503895955f74e3780b395c4ebea5b89a6601f2b) | Already present in submitted #13022; no duplicate applied |
| #13013 nonzero sparse coverage | [`623e6805825`](https://github.com/newling/rocm-libraries/commit/623e680582533f213a6a67713eb5ab56c77af970) | [`0f4335514ef`](https://github.com/newling/rocm-libraries/commit/0f4335514ef0aef3565acee19d49d7b4949956d0) |
| #13013 thread-local pattern state | [`6e3d7b8a7ee`](https://github.com/newling/rocm-libraries/commit/6e3d7b8a7eef6bedc0af5b3bde6f76fabfe3eb1a) | [`1ed15996f55`](https://github.com/newling/rocm-libraries/commit/1ed15996f5518b8b608b225b964681001c34a226) |
| #13015 bias-gradient bounds | [`7cafd4076b0`](https://github.com/newling/rocm-libraries/commit/7cafd4076b0e3e228561546772003e0a7d277827) | [`ff66f7f8f47`](https://github.com/newling/rocm-libraries/commit/ff66f7f8f47edf25bf1e868aa9affa6fdb1cc188) |
| #13015 fractional clamp refusal | [`5f453a7453b`](https://github.com/newling/rocm-libraries/commit/5f453a7453bd0e495460e7b1b93733678f80c100) | [`301193f44d0`](https://github.com/newling/rocm-libraries/commit/301193f44d0a57a6e5b491d2779a6a6884378c83) |
| #13025 descendant cleanup | [`7d157cff873`](https://github.com/newling/rocm-libraries/commit/7d157cff87351b74188b731f6533cf54d587c091) | [`c6b344acc4f`](https://github.com/newling/rocm-libraries/commit/c6b344acc4fff802864b5271766af66ea82fb22c) |
| #13025 argument validation | [`7c584f1d0f7`](https://github.com/newling/rocm-libraries/commit/7c584f1d0f70d359564dabf896b9e4950f9933e8) | [`1d673dbeeff`](https://github.com/newling/rocm-libraries/commit/1d673dbeeffccb1db8faffca4ee4c83fdfee37d7) |
| #13025 log identities | [`b404ad9f4ce`](https://github.com/newling/rocm-libraries/commit/b404ad9f4ced00bd28b845f57ced4f8a9235bf65) | [`428b9dd1d28`](https://github.com/newling/rocm-libraries/commit/428b9dd1d28d820e17fa7c93a2e9c1eade0c4595) |
| #13025 CPU CI and causal wording | [`9ac33a5a429`](https://github.com/newling/rocm-libraries/commit/9ac33a5a429a71472836c33a0266a78671df8c8e) | [`28af2377b83`](https://github.com/newling/rocm-libraries/commit/28af2377b83c8e70adbace36b2d601a2ceef3f3f) |
| #13031 MX host-memory accounting | [`d234c9f8327`](https://github.com/newling/rocm-libraries/commit/d234c9f83277839b64365b84eef99c31ca3bd920) | [`2681d0af9fc`](https://github.com/newling/rocm-libraries/commit/2681d0af9fc1a6ea1362e362be32b53e37042bff) |
| #13031 both FP8 decode tables | [`d52a1e25c3e`](https://github.com/newling/rocm-libraries/commit/d52a1e25c3e9382a95e99617ac7068afab30c9dc) | [`2d8c81e5c79`](https://github.com/newling/rocm-libraries/commit/2d8c81e5c796e145ab049127818b0cc869e5bd26) |
| #13060 reachable carry ordering | [`6be02800f34`](https://github.com/newling/rocm-libraries/commit/6be02800f34a88d488181dc4759209c9e6a5873c) | Independent branch |
| #13060 implicit addk source | [`3838b580396`](https://github.com/newling/rocm-libraries/commit/3838b580396fb183ef2c4771b296ec1275475180) | Independent branch |
| #13060 scalar reads versus carry writes | [`1c8c09fc87a`](https://github.com/newling/rocm-libraries/commit/1c8c09fc87ae1e78c4933b7c623edce2039f13ba) | Independent branch |
| #13060 disassembly label aliases | [`e931587ab08`](https://github.com/newling/rocm-libraries/commit/e931587ab08b0faa2a9efc753b9603a3f3aaca5e) | Independent branch |

The combined port preserves both the fractional-clamp check and #13031's expanded MX preflight documentation. Use the per-layer commits to restack the individual PRs, or the combined equivalents when inspecting the integrated tip; these are alternative applications of the same fixes. The earlier current-tip empty-output branch `review/pr13031-followup-20261006` and its [follow-up review](review_pr13031_stack_followup_20261006.md) are preserved.

## Validation and limits

The combined suggestion branch passes all 55 checker host/device tests with MX enabled on gfx1201/ROCm 7.1 and all six CPU runner tests. Both benchmark and GOOGLE_TEST matmul-header configurations compile; actionlint 1.7.12 and complete suggestion-diff whitespace checks pass. All nine submitted incremental stack diffs also pass whitespace checks. Independently, #13027 passes 117 lowering/assembly tests, and the fixed #13060 lint suite passes 57 tests with two gfx1250 assembler skips.

The numerical and runner regressions were reproduced before their fixes; precise evidence and committed tests are linked from the individual reviews. The workspace and MX-memory changes were validated through ownership/allocation inspection and consumer compilation. They do not have artificial tests of smart-pointer destruction or forced host exhaustion. YAML generation covers all newly added threshold, edge, hunt and MX records.

Local GPU work exercises verifier/device helpers. It does not establish correctness of the large GEMM sweeps, actual gfx90a Stream-K selection, gfx950/gfx1250 MX GEMMs or scale-buffer placement. No contention hunt, XNACK change or driver change was run. The lint remains a bounded heuristic for suspicious sequences rather than a proof of address correctness.

## Landing sequence and current checks

1. Keep [#13119](https://github.com/ROCm/rocm-libraries/pull/13119), the extracted FNUZ negation fix, independent. At the October 6, 19:11 UTC refresh it is still open at [`b23ef99de0447d8ef97fe267fb16c82c37f4a9e6`](https://github.com/ROCm/rocm-libraries/commit/b23ef99de0447d8ef97fe267fb16c82c37f4a9e6), with auto-merge enabled, a newly failed ASAN build job and other checks pending. The [failed job](https://github.com/ROCm/rocm-libraries/actions/runs/37512402596/job/112437054308) stopped in `Fetch sources` after 30 minutes with `Executing the custom container implementation failed`; configuration, compilation and GPU tests were skipped. This is a fetch/container failure, with no compilation or sanitizer result. Its underlying cause remains unconfirmed. After #13119 lands, retain its standalone regressions and reconcile the duplicate helper change in #13013 when restacking.
2. Keep #13027 and #13060 independent of the verifier stack. The former needs no source change from this review; the latter has four concrete fixes. Both still need their failed automated checks resolved or explained.
3. Apply the verifier suggestions at the layer where each behavior begins and restack in the table's order. Retain the Stream-K guard once, starting in #13005. Recheck the resulting PR diffs and affected tests after the restack; the submitted-head CI results do not certify unpublished commits.
4. Keep ROCM-32277 as separate kernel follow-up with its reproducer and removal deadline. The root review's historical request to diagnose the gfx950 failure is now addressed by a tracker, reported independent benchmark reproduction and quarantine, rather than by a kernel fix in this stack. Confirm the quarantine's shape scope before widening claims about coverage.
5. Agree a concrete follow-up boundary for host-numerics: reusable host types, codecs, deterministic generation and exact reference arithmetic belong in shared numerical APIs; device verification, placement and test orchestration remain in hipBLASLt. Preserve compact host storage and device-side output checking in the adapter. Completion of the entire host-numerics migration need not become an indefinite prerequisite for this verifier work.

All eleven reviewed heads remained unchanged at the final refresh. Math CI passes for all eleven. After distinguishing current replacement checks from historical failures/cancellations, the outstanding results are:

| PRs | Remaining failed or action-required results |
| --- | --- |
| #12876 | gfx1250 FFM/hardware and hipBLASLt project coverage |
| #12960, #13005, #13013, #13015, #13021 | hipBLASLt project coverage |
| #13022, #13025 | hipBLASLt and TensileLite-CPP project coverage |
| #13031 | Both project-coverage checks and an earlier PR-bot failure; its log reports `pre-commit=cancelled`, while replacement pre-commit, clang-tidy, multi-architecture and ASAN checks pass |
| #13027, #13060 | gfx1250 FFM/hardware, project coverage and rocSOLVER jobs/multi-architecture summary |

Coverage and the independent PRs' hardware/rocSOLVER failures have not been attributed to these source changes. Cancelled ASAN entries with unexpanded matrix names remain in some rollups alongside successful replacement build/test jobs. These distinctions help direct the remaining CI work; they do not make all PRs ready to merge. All feedback and fixes in this handoff remain local.
