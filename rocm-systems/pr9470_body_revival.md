Scalar-memory loads do not write their SGPR or TTMP destinations immediately. They create pending results that become visible later, after the corresponding wait counter permits them to complete. Before this change, the race detector tracked those pending destinations when an instruction read them, but it did not check writes to the same registers. A later instruction could therefore write a value that an older scalar load was still allowed to overwrite without producing a diagnostic.

For example, this sequence does not establish a final value for `s4` because the load may complete after the move:

```asm
s_load_dword s4, s[0:1], 0
s_mov_b32 s4, 7
```

The ordered form waits for the load before replacing its destination:

```asm
s_load_dword s4, s[0:1], 0
s_waitcnt lgkmcnt(0)
s_mov_b32 s4, 7
```

Two scalar loads targeting the same register have the same problem because scalar-memory results may complete out of issue order. The detector must check the second load as a write before adding it to the pending-event set.

This change extends the existing scalar-access check to reads and writes over typed `RegisterRef` ranges. It handles ordinary SGPRs and TTMPs separately, ignores unsupported or invalid ranges, and reports each pending event once when a wide access overlaps more than one dword. Distinct pending loads remain distinct findings. `registerScalarLoad` performs the write check before registering the new event, which covers load-over-load hazards as well as instruction writes over pending loads.

The race plugin consumes the typed scalar-write callback already provided by the wave-owned register-access layer. Raw writes used for memory completion and runtime initialization remain unobserved, so completing the original load is not interpreted as another architectural write. Existing typed wait handling is unchanged; once the relevant zero wait retires an event, a later write to that destination is accepted.

The original version of this PR also carried register ownership, generated ISA, plugin ABI, and wait-counter changes. Those foundations have since landed in `develop` through #10030, so this revision contains only the SGPR/TTMP WAW policy, its documentation, and its tests. Counter-capacity modeling remains separate in #10925.

The race-detector unit tests, scalar plugin-path tests, and gfx950 end-to-end race suite pass. The gfx950 cases use the shared structured expectation helpers and include waited and missing-wait variants for both load-to-move and load-to-load sequences. Inspection of the generated code confirms that the waits occur only in the safe variants.

Related: #7950
