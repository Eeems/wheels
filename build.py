#!/usr/bin/env python
import argparse
import json
import os
import shutil
import subprocess
import sys
from contextlib import AbstractContextManager
from glob import iglob

dirpath = os.path.dirname(os.path.realpath(__file__))
if dirpath in sys.path:
    sys.path.remove(dirpath)


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


chronic(sys.executable, "-um", "ensurepip")
chronic(
    sys.executable,
    "-um",
    "pip",
    "install",
    "--upgrade",
    "pip",
    "wheel",
    "build",
    "requests",
    "setuptools",
)

import requests  # noqa: E402
from build import ProjectBuilder  # noqa: E402
from build.env import DefaultIsolatedEnv  # noqa: E402
from pyproject_hooks import (  # noqa: E402
    default_subprocess_runner,
    quiet_subprocess_runner,
)
from setuptools import Extension  # noqa: E402
from setuptools.dist import Distribution  # noqa: E402


class BashRunnerWithSharedEnvironment(AbstractContextManager):  # pyright: ignore[reportMissingTypeArgument]
    # https://stackoverflow.com/a/68339760
    def __init__(self, env=None):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]  # noqa: ANN204
        if env is None:
            env = dict(os.environ)

        self.env: dict[str, str] = env
        self._fd_read, self._fd_write = os.pipe()  # pyright: ignore[reportUnannotatedClassAttribute]

    def run(self, cmd, **opts):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]  # noqa: ANN201
        if self._fd_read is None:
            raise RuntimeError("BashRunner is already closed")

        write_env_pycode = ";".join(
            [
                "import os",
                "import json",
                f"os.write({self._fd_write}, json.dumps(dict(os.environ)).encode())",
            ]
        )
        result = subprocess.run(  # noqa: PLW1510  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
            [
                "bash",
                "-ce",
                f"trap \"{sys.executable} -c '{write_env_pycode}'\" EXIT\n{cmd}",
            ],
            pass_fds=[self._fd_write],  # pyright: ignore[reportArgumentType]
            env=self.env,
            **opts,
        )
        self.env = json.loads(os.read(self._fd_read, 10000).decode())
        return result  # pyright: ignore[reportUnknownVariableType]

    def __exit__(self, exc_type, exc_value, traceback):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType, reportImplicitOverride]  # noqa: ANN204
        if self._fd_read:
            os.close(self._fd_read)
            os.close(self._fd_write)  # pyright: ignore[reportArgumentType]
            self._fd_read = None
            self._fd_write = None

    def __del__(self):  # noqa: ANN204
        self.__exit__(None, None, None)  # pyright: ignore[reportUnknownMemberType]


def wheel_name(universal: bool = False, manylinux: str | None = None, **kwargs):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]  # noqa: ANN201
    # create a fake distribution from arguments
    dist = Distribution(attrs=kwargs)  # pyright: ignore[reportUnknownArgumentType]
    # finalize bdist_wheel command
    bdist_wheel_cmd = dist.get_command_obj("bdist_wheel")
    bdist_wheel_cmd.ensure_finalized()
    bdist_wheel_cmd.universal = universal
    # assemble wheel file name
    distname = bdist_wheel_cmd.wheel_dist_name
    tag = "-".join(bdist_wheel_cmd.get_tag())
    name = f"{distname}-{tag}.whl"
    if manylinux is not None:
        return f"{name.split('-linux_', 1)[0]}-{manylinux}.whl"

    return name


def debug_log(msg: str):
    if os.environ.get("RUNNER_DEBUG", "") != "":
        print(msg)


def install(env: DefaultIsolatedEnv, requirements: set[str]):
    debug_log(f"{requirements}")
    try:
        env.install(requirements)

    except subprocess.CalledProcessError as e:
        print(e.stdout.decode())  # pyright: ignore[reportAny]
        print(e.stderr.decode(), file=sys.stderr)  # pyright: ignore[reportAny]
        raise


def main(name: str, output_dir: str):
    print("Checking pypi for latest version")
    response = requests.get(f"https://pypi.org/pypi/{name}/json", timeout=30)
    debug_log(f"  Response code: {response.status_code}")
    if response.status_code != 200:
        raise Exception(
            f"Failed to get https://pypi.org/pypi/{name}/json: {response.status_code}"
        )

    data = response.json()  # pyright: ignore[reportAny]
    version = data["info"]["version"]  # pyright: ignore[reportAny]
    name = data["info"]["name"]  # Use the official name  # pyright: ignore[reportAny]

    print("Getting wheel name")
    universal = os.environ.get("UNIVERSAL", "") == "1"
    wheelname = wheel_name(
        name=name,
        version=version,  # pyright: ignore[reportAny]
        ext_modules=[Extension(name, ["dummy.c"])] if not universal else None,
        universal=universal,
        manylinux=os.environ.get("MANYLINUX", None),
    )
    print(f"Wheel Name: {wheelname}")
    if not os.environ.get("FORCE", ""):
        print("Checking if wheel exists")
        if (
            requests.head(
                f"https://wheels.eeems.codes/{name.lower()}/{wheelname}",
                timeout=20,
            ).status_code
            == 200
        ):
            print("Already exists")
            return

    srctar = None
    for file in data["releases"][version]:  # pyright: ignore[reportAny]
        if file["packagetype"] == "sdist":
            srctar = file  # pyright: ignore[reportAny]

    assert srctar is not None
    print("Downloading source")
    debug_log(f"  url: {srctar['url']}")
    response = requests.get(srctar["url"], timeout=30, stream=True)  # pyright: ignore[reportAny]
    debug_log(f"Response code: {response.status_code}")
    assert response.status_code == 200
    with open("src.tar.gz", "wb") as f:
        response.raw.decode_content = True
        shutil.copyfileobj(response.raw, f)

    if os.path.exists("src"):
        shutil.rmtree("src")

    os.mkdir("src")
    print("Extracting source")
    chronic("tar", "-xf", "src.tar.gz", "--strip-components=1", "--directory=src")
    with DefaultIsolatedEnv(installer="pip") as env:
        builder = ProjectBuilder.from_isolated_env(
            env,
            "src",
            runner=(
                default_subprocess_runner
                # if os.environ.get("RUNNER_DEBUG", "") == "1"
                # else quiet_subprocess_runner
            ),
        )
        setup = os.environ.get("SETUP", "")
        if setup:
            print("Running setup")
            debug_log(f"script:\n{setup}")
            with BashRunnerWithSharedEnvironment() as runner:  # pyright: ignore[reportUnknownVariableType]
                runner.run(setup, stdout=subprocess.PIPE)  # pyright: ignore[reportUnknownMemberType]
                for key, value in runner.env.items():  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                    os.environ[key] = value

        print("Installing build system requirements")
        install(env, builder.build_system_requires)
        print("Installing requirements to build wheel")
        requirements = builder.get_requires_for_build("wheel")
        install(env, requirements)
        print("Building wheel")
        native_wheel_path = builder.build(
            "wheel",
            output_dir,
            config_settings=json.loads(  # pyright: ignore[reportAny]
                os.environ.get("CONFIG_SETTINGS", "null") or "null"
            ),
        )
        if os.environ.get("MANYLINUX", ""):
            print("Repairing wheel(s)")
            chronic("auditwheel", "repair", native_wheel_path)
            os.unlink(native_wheel_path)
            for wheel in iglob("wheelhouse/*.whl"):
                _ = shutil.move(wheel, output_dir)
                shutil.rmtree("wheelhouse")

        if not os.path.exists(os.path.join(output_dir, wheelname)):
            print("WARNING: Wheel not found, name must not match", file=sys.stderr)

        print("Done")


parser = argparse.ArgumentParser()
_ = parser.add_argument("name")
_ = parser.add_argument("output_dir")
args = parser.parse_args()
main(args.name, args.output_dir)  # pyright: ignore[reportAny]
