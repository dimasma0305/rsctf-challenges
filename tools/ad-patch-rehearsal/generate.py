"""Generate a private five-service A&D rehearsal and the corresponding team patches."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[1]


@dataclass(frozen=True)
class Exercise:
    name: str
    task: str
    starter: str
    repaired: str
    sample: object
    expected: object
    edge: object
    edge_result: object
    null_result: object


EXERCISES = (
    Exercise("order-total", "Return a total of zero for an empty order.",
             "sum(value) if value else None", "sum(value)", [8, 13], 21, [], 0, 0),
    Exercise("guest-list", "Keep guest names in arrival order when removing duplicates.",
             "sorted(set(value))", "list(dict.fromkeys(value))",
             ["Ada", "Ada", "Bo"], ["Ada", "Bo"], ["Bo", "Ada", "Bo"], ["Bo", "Ada"], []),
    Exercise("label-printer", "Trim tabs as well as spaces around a label.",
             'value.strip(" ")', "value.strip()", " West ", "West", "\tEast\t", "East", ""),
    Exercise("page-counter", "Return zero pages when the list is empty. A page holds four entries.",
             "max(1, (len(value) + 3) // 4)", "(len(value) + 3) // 4", [1, 2, 3, 4, 5], 2, [], 0, 0),
    Exercise("peak-sensor", "Report the highest reading even when every temperature is negative.",
             "max([0, *value])", "max(value, default=0)", [1, 9, 4], 9, [-8, -2, -5], -2, 0),
)


def exercise_source(expression):
    return f"def evaluate(value):\n    return {expression}\n"


def archive(path, files):
    with zipfile.ZipFile(path, "w") as out:
        for name, contents in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            out.writestr(entry, contents, compress_type=zipfile.ZIP_DEFLATED)


def generate(output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("choose a new output directory")
    # Build outside the destination so an interrupted run can be retried.
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work = Path(temporary) / "rehearsal"
        repo = work / "repository"
        repo.mkdir(parents=True)
        (repo / ".gzevent").write_text(
            'title: "Hosted patch rehearsal"\nhidden: true\nacceptWithoutReview: false\n'
            'teamMemberCountLimit: 4\nad:\n  tickSeconds: 120\n  warmupSeconds: 300\n  flagLifetimeTicks: 5\n'
        )
        dockerfile = (HERE / "Dockerfile").read_text()
        offline = "FROM rsctf-starter\n" + dockerfile.split("\n", 1)[1]
        for case in EXERCISES:
            pkg = repo / "challenges" / "AD" / "Web" / case.name
            src, checks, solution = (pkg / name for name in ("src", "checker", "solution"))
            for directory in (src, checks, solution):
                directory.mkdir(parents=True)
            (pkg / "challenge.yaml").write_text(
                f"name: {json.dumps(case.name)}\ndescription: {json.dumps(case.task)}\n"
                'author: "rsctf documentation team"\ntype: AttackDefense\ncategory: Web\n'
                'container:\n  exposePort: 8080\n  memoryLimit: 64\n  cpuCount: 1\n'
                'ad:\n  selfHosted: false\n  allowSelfReset: true\n  allowEgress: false\n'
            )
            shutil.copyfile(HERE / "server.py", src / "server.py")
            (src / "exercise.py").write_text(exercise_source(case.starter))
            (src / "Dockerfile").write_text(dockerfile)
            shutil.copyfile(HERE / "checker.py", checks / "run.py")
            shutil.copyfile(EXAMPLES / "challenges/AD/Pwn/attack-defense-service/checker/lib.py", checks / "lib.py")
            (checks / "case_data.py").write_text(f"INPUT = {case.sample!r}\nEXPECTED = {case.expected!r}\n")
            (solution / "README.md").write_text(
                f"# {case.name}\n\n{case.task}\n\nRun `python3 solution/solve.py` from the package "
                "directory to check the repaired local function. The starter fails this assertion.\n"
            )
            (solution / "solve.py").write_text(
                'from pathlib import Path\nimport runpy\n\n'
                'evaluate = runpy.run_path(str(Path(__file__).resolve().parents[1] / "src/exercise.py"))["evaluate"]\n'
                f"assert evaluate({case.edge!r}) == {case.edge_result!r}\n"
            )
            zips = work / "patches" / case.name
            zips.mkdir(parents=True)
            files = {"server.py": (src / "server.py").read_bytes(), "Dockerfile": offline,
                     ".rsctf-data-dir": b"/var/lib/rehearsal\n",
                     "exercise.py": exercise_source(case.starter),
                     ".rsctf-ssh.json": json.dumps([{
                         "sourcePath": "exercise.py",
                         "containerPath": "/app/exercise.py",
                         "retainContent": True,
                         "shareAfterClose": True,
                     }]).encode()}
            archive(zips / "starter.zip", files)
            archive(zips / "patched.zip", {**files, "exercise.py": exercise_source(case.repaired)})
            second_repair = f"{case.null_result!r} if value is None else {case.repaired}"
            archive(zips / "patched-v2.zip", {**files, "exercise.py": exercise_source(second_repair)})
            archive(zips / "failed-build.zip", {**files, "Dockerfile": offline + "\nCOPY missing-file /demo\n"})
        work.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new directory outside the challenge repository")
    output = parser.parse_args().output
    if output.resolve().is_relative_to(EXAMPLES):
        parser.error("generate the rehearsal outside the example repository")
    generate(output)
