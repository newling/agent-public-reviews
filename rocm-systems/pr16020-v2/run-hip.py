"""Run the review's HIP cases against a matched rocjitsu build."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path, help="emulation/rocjitsu source directory")
parser.add_argument("build", type=Path, help="rocjitsu build directory")
parser.add_argument("binary", type=Path, help="compiled barrier_probe.hip executable")
parser.add_argument("output", type=Path, help="new output directory")
args = parser.parse_args()
source, build, binary, output = (
    path.resolve() for path in (args.source, args.build, args.binary, args.output)
)
base = json.loads((source / "configs/gfx1250_mi455x.json").read_text())
output.mkdir()
expected = [1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0]
results = []
for case in range(12):
    directory = output / str(case)
    directory.mkdir()
    (directory / "plugins").mkdir()
    config = {
        **base,
        "require_all_plugins": True,
        "plugins": {"race": {}},
        "sinks": {"types": ["file"], "dir": str(directory / "plugins")},
    }
    (directory / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    command = [
        str(build / "tools/rocjitsu/rocjitsu"),
        "--cpu-thread-budget", "2",
        "--config", str(directory / "config.json"),
        "--", str(binary), str(case),
    ]
    start = time.monotonic()
    with (directory / "run.log").open("w") as log:
        try:
            process = subprocess.run(
                command, cwd=directory,
                env={**os.environ, "ROCJITSU_RUNTIME_DIR": "runtime"},
                stdout=log, stderr=subprocess.STDOUT, timeout=45,
            )
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = 124
    report = directory / "plugins/race.log"
    lines = report.read_text().splitlines() if report.exists() else []
    findings = [line for line in lines if line.startswith("RACE ")]
    result = {
        "case": case, "exit_code": code, "reports": len(findings),
        "seconds": time.monotonic() - start,
        "matches_observed_result": code == 0 and report.exists()
        and len(findings) == expected[case]
        and all(" type=LDS " in line for line in findings),
    }
    results.append(result)
    print(result, flush=True)
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
raise SystemExit(not all(result["matches_observed_result"] for result in results))
