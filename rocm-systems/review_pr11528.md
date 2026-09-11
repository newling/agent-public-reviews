This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11528](https://github.com/ROCm/rocm-systems/pull/11528)

## Tests

Not run locally: the review environment does not have `cargo`. The PR's Clippy, pre-commit, and rocjitsu test CI jobs are currently failing; the failure causes below are visible in their logs.

## Summary

This changes rocjitsu from two overlapping launchers into one Rust CLI: the existing Rust Mirage tree is moved under `emulation/rocjitsu/cli`, the older C++ launcher is removed, and CMake, packaging, tests, and CI are taught to use the Rust binary. Keeping the Rust implementation as the single supported entry point is a sensible direction, and placing its build under the existing rocjitsu build makes its dependencies explicit.

The PR has 8,276 additions and 7,141 deletions, for a net increase of 1,135 lines. The move itself is mostly recognized as a rename, but it is not a pure merge of two identical implementations: 1,244 lines of the C++ launcher are removed and the C++ test area shrinks by a net 457 lines, while 2,641 lines of new Rust/CMake integration and 1,003 net lines of modifications to the moved Rust CLI are added. Much of the added code is the replacement behavior and build/test plumbing needed for the Rust CLI to become the project launcher, rather than duplicated functionality. The new integration currently cannot pass its own validation, so the net increase is not yet accompanied by a working replacement.

## Actionable items

### Preserve the required SDMA queue count in builtin agents

`emulation/rocjitsu/cli/builtin/src/agents.rs:88`, `:138`, and `:187` give each generated builtin a nonzero `num_sdma_engines`, but `KfdDeviceInfo` has no `num_sdma_queues_per_engine` member (`emulation/rocjitsu/cli/core/src/agent.rs:201`). The serialized agent therefore supplies a zero queue count. The rocjitsu configuration validator rejects exactly that combination, which prevents the migrated CLI from starting a daemon for its built-in profiles and accounts for the failing daemon and rocgdb CI tests. Add the schema field to `KfdDeviceInfo`, populate it from the corresponding shipped preset (8 for MI300X and MI350X, 2 for MI450X), and add a direct test that each emitted builtin validates against the rocjitsu configuration loader.

### Include the presets in the standalone Clippy checkout

`.github/workflows/rocjitsu-formatting.yml:74` sparsely checks out only `emulation/rocjitsu/cli`, but `emulation/rocjitsu/cli/builtin/build.rs:55` deliberately reads the presets from `emulation/rocjitsu/configs`. Consequently `cargo clippy` fails before linting because the three JSON files are not present. Include `emulation/rocjitsu/configs` in this job's sparse checkout (or check out all of `emulation/rocjitsu`) so the new build-time dependency is available.

### Remove or format the moved empty Rust module

`emulation/rocjitsu/cli/core/src/metric.rs:1` contains only a blank line. The pre-commit and `cargo fmt --check` jobs both report that they modify this file, so the PR cannot pass its required formatting checks. Remove the empty module if it is unused, or leave it as a properly formatted empty file, then rerun the formatter before updating the PR.

## Suggestions

None.

## Commentary

The line-count expectation is reasonable for a strict consolidation, but it is not a rule for a replacement migration. The useful measure here is whether the old C++ capability has been deleted without adding new, independent behavior. This diff does remove the old launcher, but it also adds the CMake cargo wrapper, test-launch integration, configuration handoff, compatibility symlink, lint workflow, and substantial Rust changes. Those are genuine additions, and the two configuration-related failures show why they need the same review attention as the code being removed.
