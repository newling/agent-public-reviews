"""Run the cell review probes, optionally including the pinned corpus cell cases."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path, help="emulation/rocjitsu source directory")
parser.add_argument("build", type=Path)
parser.add_argument("binary", type=Path)
parser.add_argument("output", type=Path, help="new evidence directory outside the source tree")
parser.add_argument("--corpus-source", type=Path, help="also run cell_* tests from this HIP source")
args = parser.parse_args()
source, build, binary, output = (
    p.resolve() for p in (args.source, args.build, args.binary, args.output)
)
base = json.loads((source / "configs/gfx1250_mi455x.json").read_text())
cases = []
if args.corpus_source:
    cases.extend(
        "Gfx1250RaceTest." + name
        for name in re.findall(
            r"^TEST_F\(Gfx1250RaceTest, (cell_[^)]+)\)", args.corpus_source.read_text(), re.M
        )
    )
for form in ("Returning", "Async"):
    for order in ("Forward", "Reversed"):
        for poll in ("NoPoll", "OtherCellPolled", "SameCellPolled"):
            cases.append(
                "BothFormsAndLaneOrders/BarrierCellReviewHipTest."
                "AcquiringOneCellMustNotAcquireASiblingArrival/" + form + order + poll
            )
output.mkdir()
results = []
for case in cases:
    directory = output / case.rsplit("/", 1)[-1].removeprefix("Gfx1250RaceTest.")
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
        "timeout", "--kill-after=5s", "50s",
        str(build / "tools/rocjitsu/rocjitsu"),
        "--cpu-thread-budget", "2", "--config", str(directory / "config.json"),
        "--", str(binary), "--gtest_filter=" + case,
        "--gtest_output=xml:" + str(directory / "gtest.xml"),
    ]
    start = time.monotonic()
    with (directory / "run.log").open("w") as log:
        process = subprocess.run(
            command, cwd=directory,
            env={**os.environ, "RJ_SINK_DIR": str(directory / "plugins"),
                 "ROCJITSU_RUNTIME_DIR": "runtime"},
            stdout=log, stderr=subprocess.STDOUT,
        )
    xml = directory / "gtest.xml"
    root = ET.parse(xml).getroot() if xml.exists() else None
    summary = root.attrib if root is not None else {}
    report = directory / "plugins/race.log"
    reports = (
        sum(line.startswith("RACE ") for line in report.read_text().splitlines())
        if report.exists() else None
    )
    record = {
        "case": case, "command": command, "exit_code": process.returncode,
        "seconds": time.monotonic() - start, "gtest": summary, "reports": reports,
        "passed": process.returncode == 0 and summary.get("tests") == "1"
        and summary.get("failures") == "0" and summary.get("disabled") == "0"
        and summary.get("errors") == "0" and reports is not None
        and root is not None and not root.findall(".//skipped"),
    }
    results.append(record)
    print(case, "exit", process.returncode, "reports", reports, "passed", record["passed"], flush=True)
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
print(sum(record["passed"] for record in results), "/", len(results), "passed")
raise SystemExit(not all(record["passed"] for record in results))
