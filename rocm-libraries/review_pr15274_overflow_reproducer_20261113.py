#!/usr/bin/env python3
"""Check the committed Int8 boundary test with signed-overflow instrumentation.

Usage: python3 check_int8_overflow.py SOURCE_ROOT BUILD_DIR OUTPUT_DIR
Build tensilelite-tests from the suggestion branch first. Only Reference.cpp
is instrumented; this is not a full-library sanitizer run. No source is edited.
"""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

source_root, build, output = (Path(p).resolve() for p in sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
artifact_dir = build / "int8-overflow-review"
artifact_dir.mkdir(exist_ok=True)
reference_path = "projects/hipblaslt/tensilelite/client/src/Reference.cpp"
submitted = "f58bbb3388853e13cdf85bda0917485d590c4ddc"
entries = json.loads((build / "compile_commands.json").read_text())
entry = next(e for e in entries if e["file"].endswith("/client/src/Reference.cpp"))
link_line = subprocess.check_output(
    ["ninja", "-t", "commands", "tensilelite-tests"], cwd=build, text=True
).splitlines()[-1]
link_args = shlex.split(link_line)
if link_args[0] == ":":
    start = link_args.index("&&") + 1
    link_args = link_args[start : link_args.index("&&", start)]
# Keep the normal build's dependency file intact.
for i in range(len(link_args) - 1, 0, -1):
    if link_args[i].startswith("--dependency-file="):
        assert link_args[i - 1] == "-Xlinker"
        del link_args[i - 1 : i + 1]
environment = dict(os.environ, OMP_THREAD_LIMIT="8", OMP_NUM_THREADS="4", KMP_BLOCKTIME="0")
sanitizer_flags = [
    "-fsanitize=signed-integer-overflow",
    "-fno-sanitize-recover=signed-integer-overflow",
]
receipts = {}

for label in ("submitted", "suggested"):
    src = output / (label + "-Reference.cpp")
    if label == "submitted":
        src.write_bytes(subprocess.check_output(
            ["git", "show", submitted + ":" + reference_path], cwd=source_root
        ))
    else:
        src.write_bytes((source_root / reference_path).read_bytes())
    obj = artifact_dir / (label + ".o")
    exe = artifact_dir / (label + "-tests")
    args = shlex.split(entry["command"])
    args[args.index(entry["file"])] = str(src)
    args[args.index("-o") + 1] = str(obj)
    args += ["-O1", "-gline-tables-only", "--cuda-host-only", *sanitizer_flags]
    start = time.monotonic()
    with (output / (label + "-sanitize-build.log")).open("w") as log:
        subprocess.run(["nice", "-n", "10", *args], cwd=entry["directory"],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        link = link_args.copy()
        link[link.index("-o") + 1] = str(exe)
        # The explicit object satisfies Reference.cpp symbols before the static
        # client archive is scanned, so its uninstrumented object is not loaded.
        link[1:1] = [str(obj), *sanitizer_flags]
        subprocess.run(["nice", "-n", "10", *link], cwd=build,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    cmd = [str(exe), "--gtest_filter=ReferenceFastPath.Int8DotProductWrapsAtInt32Boundary"]
    result = subprocess.run(cmd, cwd=build, env=environment, capture_output=True, text=True)
    log_text = result.stdout + result.stderr
    (output / (label + "-sanitize-test.log")).write_text(log_text)
    receipts[label] = {"compile": args, "link": link, "test": cmd,
                       "exit_code": result.returncode, "seconds": time.monotonic() - start}
    (output / "sanitizer-results.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(label, "exit", result.returncode, flush=True)
    print(log_text, flush=True)
    if label == "submitted":
        assert result.returncode != 0 and "signed integer overflow" in log_text
    else:
        assert result.returncode == 0 and "[  PASSED  ] 1 test." in log_text
