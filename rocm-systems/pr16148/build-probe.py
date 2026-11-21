"""Link the native probe against an existing Ninja rocjitsu_tests build."""

import argparse
import json
from pathlib import Path
import shlex
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("build", type=Path)
parser.add_argument("probe", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
build, probe, output = (p.resolve() for p in (args.build, args.probe, args.output))

database = json.loads((build / "compile_commands.json").read_text())
entry = next(
    item for item in database
    if item["file"].endswith("/tests/execution_plugin_race_test.cpp")
)
compile_command = list(entry.get("arguments") or shlex.split(entry["command"]))
original_object = compile_command[compile_command.index("-o") + 1]
probe_object = output.with_suffix(".o")
compile_command[compile_command.index("-o") + 1] = str(probe_object)
compile_command[compile_command.index("-c") + 1] = str(probe)
if "-MF" in compile_command:
    compile_command[compile_command.index("-MF") + 1] = str(output.with_suffix(".d"))

ninja_commands = subprocess.check_output(
    ["ninja", "-t", "commands", "tests/rocjitsu_tests"], cwd=build, text=True
)
link_command = None
for line in ninja_commands.splitlines():
    segment = []
    for token in [*shlex.split(line), "&&"]:
        if token != "&&":
            segment.append(token)
            continue
        if "-o" in segment and segment[segment.index("-o") + 1] == "tests/rocjitsu_tests":
            link_command = segment
        segment = []
if link_command is None or original_object not in link_command:
    raise SystemExit("Cannot identify the native test link command and fixture object")
link_command = [str(probe_object) if token == original_object else token for token in link_command]
link_command[link_command.index("-o") + 1] = str(output)
link_command = [
    "--dependency-file=" + str(output.with_suffix(".link.d"))
    if token.startswith("--dependency-file=") else token
    for token in link_command
]
output.with_suffix(".commands.json").write_text(
    json.dumps({"compile": compile_command, "link": link_command}, indent=2) + "\n"
)
subprocess.run(compile_command, cwd=entry["directory"], check=True)
subprocess.run(link_command, cwd=build, check=True)
