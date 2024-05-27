import re
import os
import sys

from glob import iglob

_WHEEL_FILENAME_REGEX = re.compile(
    r"(?P<distribution>.+)-(?P<version>.+)"
    r"(-(?P<build_tag>.+))?-(?P<python_tag>.+)"
    r"-(?P<abi_tag>.+)-(?P<platform_tag>.+)\.whl"
)
# _WHEEL_FILENAME_REGEX.match(filename)


def main(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    for path in iglob(os.path.join(input_dir, "*.whl")):
        basename = os.path.basename(path)
        info = _WHEEL_FILENAME_REGEX.match(basename)
        name = info.group("distribution").lower()
        dirpath = os.path.join(output_dir, name)
        if not os.path.exists(dirpath):
            os.mkdir(dirpath)

        filepath = os.path.join(dirpath, basename)
        if not os.path.exists(filepath):
            os.link(path, filepath)


main(sys.argv[1], sys.argv[2])
