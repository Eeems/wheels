#!/usr/bin/env python
import argparse
import json
import os
import shutil
import subprocess
import sys
from contextlib import AbstractContextManager

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

import requests
from build import ProjectBuilder  # noqa: E402
from build.env import (
    DefaultIsolatedEnv,  # noqa: E402
    Installer,  # noqa: E402
)
from pyproject_hooks import (
    default_subprocess_runner,  # noqa: E402
    quiet_subprocess_runner,  # noqa: E402
)
from setuptools import Extension  # noqa: E402
from setuptools.dist import Distribution  # noqa: E402


class BashRunnerWithSharedEnvironment(AbstractContextManager):
    # https://stackoverflow.com/a/68339760
    def __init__(self, env=None):
        if env is None:
            env = dict(os.environ)

        self.env: dict[str, str] = env
        self._fd_read, self._fd_write = os.pipe()

    def run(self, cmd, **opts):
        if self._fd_read is None:
            raise RuntimeError("BashRunner is already closed")

        write_env_pycode = ";".join(
            [
                "import os",
                "import json",
                f"os.write({self._fd_write}, json.dumps(dict(os.environ)).encode())",
            ]
        )
        write_env_shell_cmd = f"{sys.executable} -c '{write_env_pycode}'"
        cmd += "\n" + write_env_shell_cmd
        result = subprocess.run(
            ["bash", "-ce", cmd],
            pass_fds=[self._fd_write],
            env=self.env,
            **opts,
        )
        self.env = json.loads(os.read(self._fd_read, 10000).decode())
        return result

    def __exit__(self, exc_type, exc_value, traceback):
        if self._fd_read:
            os.close(self._fd_read)
            os.close(self._fd_write)
            self._fd_read = None
            self._fd_write = None

    def __del__(self):
        self.__exit__(None, None, None)


def wheel_name(universal=False, **kwargs):
    # create a fake distribution from arguments
    dist = Distribution(attrs=kwargs)
    # finalize bdist_wheel command
    bdist_wheel_cmd = dist.get_command_obj("bdist_wheel")
    bdist_wheel_cmd.ensure_finalized()
    bdist_wheel_cmd.universal = universal
    # assemble wheel file name
    distname = bdist_wheel_cmd.wheel_dist_name
    tag = "-".join(bdist_wheel_cmd.get_tag())
    return f"{distname}-{tag}.whl"


def debug_log(msg: str):
    if os.environ.get("RUNNER_DEBUG", "") == "1":
        print(msg)


def main(name, output_dir):
    print("Checking pypi for latest version")
    response = requests.get(f"https://pypi.org/pypi/{name}/json", timeout=30)
    debug_log(f"  Response code: {response.status_code}")
    if response.status_code != 200:
        raise Exception(
            f"Failed to get https://pypi.org/pypi/{name}/json: {response.status_code}"
        )

    data = response.json()
    version = data["info"]["version"]
    name = data["info"]["name"]  # Use the official name

    print("Getting wheel name")
    universal = os.environ.get("UNIVERSAL", "") == "1"
    wheelname = wheel_name(
        name=name,
        version=version,
        ext_modules=[Extension(name, ["dummy.c"])] if not universal else None,
        universal=universal,
    )
    print(f"Wheel Name: {wheelname}")
    if not os.environ.get("FORCE", ""):
        print("Checking if wheel exists")
        if (
            requests.head(
                f"https://wheels.eeems.codes/{name.lower()}/{wheelname}"
            ).status_code
            == 200
        ):
            print("Already exists")
            return

    srctar = None
    for file in data["releases"][version]:
        if file["packagetype"] == "sdist":
            srctar = file

    assert srctar is not None
    print("Downloading source")
    debug_log(f"  url: {srctar['url']}")
    response = requests.get(srctar["url"], timeout=30, stream=True)
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
    with DefaultIsolatedEnv(installer=Installer) as env:
        builder = ProjectBuilder.from_isolated_env(
            env,
            "src",
            runner=default_subprocess_runner
            if os.environ.get("RUNNER_DEBUG", "") == "1"
            else quiet_subprocess_runner,
        )
        print("Installing build system requirements")
        env.install(builder.build_system_requires)
        setup = os.environ.get("SETUP", "")
        if setup:
            print("Running setup")
            debug_log(f"script:\n{setup}")
            with BashRunnerWithSharedEnvironment() as runner:
                runner.run(setup, stdout=subprocess.PIPE)
                for key, value in runner.env.items():
                    os.environ[key] = value

        print("Installing requirements to build wheel")
        env.install(builder.get_requires_for_build("wheel"))
        print("Building wheel")
        builder.build(
            "wheel",
            output_dir,
            config_settings=json.loads(
                os.environ.get("CONFIG_SETTINGS", "null") or "null"
            ),
        )
        if not os.path.exists(os.path.join(output_dir, wheelname)):
            print("WARNING: Wheel not found, name must not match", file=sys.stderr)

        print("Done")


parser = argparse.ArgumentParser()
_ = parser.add_argument("name")
_ = parser.add_argument("output_dir")
args = parser.parse_args()
main(args.name, args.output_dir)  # pyright: ignore[reportAny]
