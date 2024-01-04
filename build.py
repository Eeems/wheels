#!/usr/bin/env python
import shutil
import subprocess
import sys
import os
import requests


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
    subprocess.check_call(["python", "-m", "build", "--wheel"], cwd="src")
    shutil.copytree("src/dist/", output_dir, dirs_exist_ok=True)


main(sys.argv[1], sys.argv[2])
