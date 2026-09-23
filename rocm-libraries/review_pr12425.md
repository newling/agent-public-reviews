> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12425](https://github.com/ROCm/rocm-libraries/pull/12425)

## Tests

`actionlint` 1.7.12, the root trailing-whitespace/end-of-file/YAML pre-commit hooks, `git diff --check`, and the artifact-path contract probe all passed for both the submitted workflow and an artifact-only candidate applied atop current `develop`. The current public end-to-end run is still queued, and it was created before #11396 merged, so it cannot validate installation from the new artifact file.

## Summary

The PR repairs the rocJITsu sidecar after TheRock stopped putting TensileLite dependencies in every test environment. Installing the project-owned requirements after fetching `--blas --tests` is the right boundary for this custom sidecar: it uses TheRock's standard additional-requirements helper while keeping TensileLite's dependency list in rocm-libraries. Now that the artifact-producing change is on `develop`, the durable version of this fix can be smaller and stricter.

## Actionable items

1. **`.github/workflows/therock-rocjitsu-race-check-linux.yml:124-146` — require the artifact-provided requirements file.**

   ROCm/rocm-libraries#11396 has now merged as `bb2dc9a52bb9`. It installs `requirements-test.txt` unconditionally whenever `HIPBLASLT_INSTALL_TENSILELITE_TEST_ARTIFACTS` is enabled, and the pinned TheRock BLAS build enables that option for test artifacts. The virtual merge therefore contains the file at exactly `${ROCM_PATH}/share/hipblaslt/tensilelite/requirements-test.txt`.

   Keeping the TheRock fallback would hide a regression in that packaging contract: the sidecar could remain green after the promised artifact file disappeared. It also preserves two dependency sources that have already diverged. The artifact file uses `pytest>=5.4.1` and leaves PyYAML, packaging, and syrupy unpinned, whereas TheRock's transitional copy pins all four.

   Sync this branch with current `develop`, remove `therock_requirements` and the selection conditional, and pass the artifact path directly to `install_additional_requirements.py` so a missing artifact fails loudly. Then use a newly triggered sidecar run to verify that the install log names the artifact path before either race workload starts. The runs currently attached to this head were created before #11396 merged and can exercise only the fallback.

## Suggestions

None.

## Commentary

TheRock's normal TensileLite component still has its own TODO and transitional requirements copy. Updating that component configuration to use the newly shipped artifact file is now unblocked and should happen separately. It does not replace this PR: the rocJITsu sidecar calls `setup_test_environment` directly and does not consume the component matrix's `additional_requirements_files`, so this explicit post-download install step remains necessary.
