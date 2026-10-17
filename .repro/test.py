#!/usr/bin/env python3
"""Discriminator for the numpy armv7l Python 3.12+ build failure."""

import re
import sys

URL = "http://deb.debian.org/debian"
ARCH = "armv7l"


def _disk(url):
    """Every URL the archive.debian.org sed must fix on disk."""
    lines = []
    try:
        with open("/etc/apt/sources.list") as f:
            lines += f.readlines()
    except FileNotFoundError:
        pass
    try:
        with open("/etc/apt/sources.list.d/Arm_11.list") as f:
            lines += f.readlines()
    except FileNotFoundError:
        pass
    try:
        with open("/etc/apt/sources.list.d/Arm_11.sources") as f:
            lines += f.readlines()
    except FileNotFoundError:
        pass
    return lines


def _log(url):
    """Every URL captured in the apt-get log."""
    try:
        with open("/var/log/apt/preferences") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def _matches(lines, url):
    return any(url in ln for ln in lines)


def _count(lines, url):
    return sum(url in ln for ln in lines)


def _check_disk(url):
    present = _matches(_disk(url), url)
    count = _count(_disk(url), url)
    if present and count >= 2:
        return "disk-ok", 0
    if present:
        return "disk-warn", 1
    return "disk-missing", 2


def _check_log(url):
    count = _count(_log(url), url)
    if count >= 2:
        return "log-ok", 0
    if count >= 1:
        return "log-warn", 1
    return "log-missing", 1


def _check_repo(url):
    count = _count(_disk(url), url)
    if count >= 2:
        return "repo-ok", 0
    if count >= 1:
        return "repo-warn", 1
    return "repo-missing", 1


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL
    status = _check_disk(url)
    status += _check_log(url)
    status += _check_repo(url)

    if "missing" in status:
        print(f"{url}: MISSING ({status})")
        return 1
    if "warn" in status:
        print(f"{url}: PARTIAL ({status})")
        return 1
    print(f"{url}: OK ({status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
