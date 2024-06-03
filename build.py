#!/usr/bin/env python
import shutil
import subprocess
import sys
import os
import json
import requests

dirpath = os.path.dirname(os.path.realpath(__file__))
if dirpath in sys.path:
    sys.path.remove(dirpath)

from build import ProjectBuilder
from build.env import DefaultIsolatedEnv
from build.env import Installer

from pathlib import Path
from setuptools import Extension
from setuptools.dist import Distribution
from importlib.metadata import PathDistribution
from pyproject_hooks import quiet_subprocess_runner
from pyproject_hooks import default_subprocess_runner


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
    debug_log(f"Wheel Name: {wheelname}")
    print(f"Checking if wheel exists")
    wheelpath = os.path.join(output_dir, wheelname)
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
    subprocess.check_call(
        ["tar", "-xf", "src.tar.gz", "--strip-components=1", "--directory=src"]
    )
    with DefaultIsolatedEnv(installer=Installer) as env:
        builder = ProjectBuilder.from_isolated_env(
            env,
            "src",
            runner=default_subprocess_runner
            if os.environ.get("RUNNER_DEBUG", "") == "1"
            else quiet_subprocess_runner,
        )
        print("Installing build requirements")
        env.install(builder.build_system_requires)
        print("Running setup")
        setup = os.environ.get("SETUP", "")
        debug_log(f"script:\n{setup}")
        subprocess.check_call(["bash", "-ec", setup])
        print("Installing wheel requirements")
        env.install(builder.get_requires_for_build("wheel"))
        print("Building wheel")
        builder.build(
            "wheel",
            output_dir,
            config_settings=json.loads(os.environ.get("CONFIG_SETTINGS", "null")),
        )
        print("Done")


main(sys.argv[1], sys.argv[2])
