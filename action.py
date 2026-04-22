import argparse
import os
import subprocess
import sys


def chronic(*args: str) -> None:
    proc = subprocess.run(args, check=False, capture_output=True, text=True)
    if proc.returncode:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(
            proc.returncode,
            proc.args,  # pyright: ignore[reportAny]
            proc.stdout,
            proc.stderr,
        )


def main():
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("name", help="Package name")
    _ = parser.add_argument("--force", help="Force build", action="store_true")
    _ = parser.add_argument(
        "--workspace",
        help="Path to workspace",
        default=".",
        required=False,
    )
    _ = parser.add_argument(
        "--build_on",
        help="What target to build on",
        default="",
        required=False,
    )
    _ = parser.add_argument(
        "--python",
        help="Python version to use",
        default="3.11",
        required=False,
    )

    args = parser.parse_args()

    image: str | None = None
    platform: str | None = None
    manylinux: str = ""
    script: list[str] = []
    assert isinstance(args.build_on, str)  # pyright: ignore[reportAny]
    assert isinstance(args.python, str)  # pyright: ignore[reportAny]
    system = args.build_on.split("-", 1)[0]
    match system:
        case "ubuntu":
            if args.build_on.split("-", 1)[1] != "amd64":
                raise NotImplementedError(args.build_on)

        case "":
            pass

        case "debian":
            if args.build_on.split("-", 1)[1] != "armv7l":
                raise NotImplementedError(args.build_on)

            image = f"eeems/nuitka-arm-builder:bullseye-{args.python}"
            platform = "linux/arm/v7"
            script.append("source /opt/lib/nuitka/bin/activate")

        case "manylinux":
            parts = args.build_on.split("-", 2)
            if len(parts) < 3:
                raise NotImplementedError(args.build_on)

            arch, libc = parts[1:]
            if libc == "musl":
                image = f"musllinux_1_2_{arch}"

            elif arch == "armv7l":
                image = f"manylinux_2_35_{arch}"

            elif arch == "riscv64":
                image = f"manylinux_2_39_{arch}"

            else:
                image = f"manylinux_2_34_{arch}"

            manylinux = image
            image = f"quay.io/pypa/{image}:latest"

            chronic(
                "docker",
                "run",
                "--privileged",
                "--rm",
                "tonistiigi/binfmt",
                "--install",
                "all",
            )
            python = args.python.replace(".", "")
            python_interpreter = f"cp{python}-cp{python}"
            script.extend(
                [
                    f'manylinux-interpreters ensure "{python_interpreter}"',
                    f'PATH="/opt/python/{python_interpreter}/bin:$PATH"',
                ]
            )

        case _:
            raise NotImplementedError(args.build_on)

    assert isinstance(args.name, str)  # pyright: ignore[reportAny]
    assert isinstance(args.workspace, str)  # pyright: ignore[reportAny]
    assert isinstance(args.force, bool)  # pyright: ignore[reportAny]
    if image is None:
        if [sys.version_info.major, sys.version_info.minor] != [
            int(x) for x in args.python.split(".")
        ]:
            raise NotImplementedError(f"Not running {args.python}")

        venv = os.path.join(args.workspace, ".wheel-venv")
        chronic(sys.executable, "-m", "venv", venv)
        venv_python = os.path.join(venv, "bin", "python")
        chronic(venv_python, "-m", "ensurepip")
        chronic(venv_python, "-m", "pip", "install", "--upgrade", "pip")
        env = os.environ.copy()
        if args.force:
            env["FORCE"] = "1"

        env["PYTHONUNBUFFERED"] = "1"
        _ = subprocess.run(
            [
                venv_python,
                "-u",
                os.path.join(os.path.dirname(__file__), "build.py"),
                args.name,
                args.workspace,
            ],
            env=env,
            check=True,
        )
        return

    _ = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            *([] if platform is None else [f"--platform={platform}"]),
            f"--volume={args.workspace}:/workspace",
            f"--volume={os.path.dirname(__file__)}:/action",
            f"--env=RUNNER_DEBUG={os.environ.get('RUNNER_DEBUG', '')}",
            f"--env=UNIVERSAL={os.environ.get('UNIVERSAL', '')}",
            f"--env=CONFIG_SETTINGS={os.environ.get('CONFIG_SETTINGS', '')}",
            f"--env=SETUP={os.environ.get('SETUP', '')}",
            f"--env=MANYLINUX={manylinux}",
            *(["--env=FORCE=1"] if args.force else []),
            "--env=PYTHONUNBUFFERED=1",
            image,
            "sh",
            "-ec",
            "\n".join(
                [
                    "cat > ~/.pypirc << EOF",
                    "[distutils]",
                    "index-servers =",
                    "    pypi",
                    "    eeems",
                    "[pypi]",
                    "[eeems]",
                    "repository = https://wheels.eeems.codes/",
                    "EOF",
                    "cd /tmp",
                    *script,
                    f'python -u /action/build.py "{args.name}" /workspace',
                ]
            ),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
