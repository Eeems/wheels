#!/usr/bin/env python
import shutil
import subprocess
import sys
import os
import requests

dirpath = os.path.dirname(os.path.realpath(__file__))
if dirpath in sys.path:
    sys.path.remove(dirpath)

from build import ProjectBuilder
from build.env import DefaultIsolatedEnv
from build.env import Installer

from pathlib import Path
from importlib.metadata import PathDistribution
from setuptools import Extension
from setuptools.dist import Distribution
from pyproject_hooks import quiet_subprocess_runner


def wheel_name(**kwargs):
    # create a fake distribution from arguments
    dist = Distribution(attrs=kwargs)
    # finalize bdist_wheel command
    bdist_wheel_cmd = dist.get_command_obj("bdist_wheel")
    bdist_wheel_cmd.ensure_finalized()
    # assemble wheel file name
    distname = bdist_wheel_cmd.wheel_dist_name
    tag = "-".join(bdist_wheel_cmd.get_tag())
    return f"{distname}-{tag}.whl"


def main(name, output_dir):
    response = requests.get(f"https://pypi.org/pypi/{name}/json", timeout=30)
    if response.status_code != 200:
        raise Exception(
            f"Failed to get https://pypi.org/pypi/{name}/json: {response.status_code}"
        )

    data = response.json()
    version = None
    for file in data["releases"][data["info"]["version"]]:
        if file["packagetype"] == "sdist":
            version = file

    assert version is not None
    response = requests.get(version["url"], timeout=30, stream=True)
    assert response.status_code == 200
    with open("src.tar.gz", "wb") as f:
        response.raw.decode_content = True
        shutil.copyfileobj(response.raw, f)

    if os.path.exists("src"):
        shutil.rmtree("src")

    os.mkdir("src")
    subprocess.check_call(
        ["tar", "-xf", "src.tar.gz", "--strip-components=1", "--directory=src"]
    )
    with DefaultIsolatedEnv(installer=Installer) as env:
        builder = ProjectBuilder.from_isolated_env(
            env,
            "src",
            runner=quiet_subprocess_runner,
        )
        print("Installing build requirements")
        env.install(builder.build_system_requires)
        print("Installing wheel")
        env.install(builder.get_requires_for_build("wheel"))
        if os.path.exists("metadata"):
            shutil.rmtree("metadata")

        print("Getting metadata")
        metadatapath = builder.metadata_path("metadata")
        print("Getting wheel name")
        dist = PathDistribution(Path(metadatapath))
        name = dist.name
        wheelname = wheel_name(
            name=name,
            version=dist.version,
            ext_modules=[
                Extension(name, ["dummy.c"])  # We assume this needs to be compiled
            ],
        )
        print("Checking if wheel exists")
        wheelpath = os.path.join(output_dir, wheelname)
        if (
            requests.head(f"https://wheels.eeems.codes/{name}/{wheelname}").status_code
            == 200
        ):
            print("Downloading wheel")
            resp = requests.get(f"https://wheels.eeems.codes/{name}/{wheelname}")
            with open(wheelpath, "wb") as f:
                f.write(resp.content)

        else:
            print("Building wheel")
            wheelpath = builder.build("wheel", output_dir)

        print(wheelpath)


main(sys.argv[1], sys.argv[2])
