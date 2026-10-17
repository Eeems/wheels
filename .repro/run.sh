#!/bin/sh
# Reproduce a debian-armv7l build exactly as build/action.py does, with
# RUNNER_DEBUG=1 so the PEP 517 backend stderr is not swallowed by
# quiet_subprocess_runner.
set -eu

WORKTREE=${WORKTREE:-/var/home/pi/.local/state/sheepdog/Eeems/wheels/15/worktree}
PYVER=${PYVER:-3.12}
PKG=${PKG:-numpy}
SETUP_FILE=${SETUP_FILE:-}

if [ -z "$SETUP_FILE" ]; then
  echo "SETUP_FILE must point at a file holding the build.yml setup script" >&2
  exit 2
fi

SETUP=$(cat "$SETUP_FILE")

# Install binfmt_misc + QEMU before the arm build. The debian-armv7l packages
# ship as arm ELF; without binfmt_misc the host kernel rejects them with
# "exec format error" before the setup script runs.
docker run --privileged --rm \
  -v /var/lib/binfmt:/var/lib/binfmt \
  -e tonistiigi/binfmt --install all \
  "tonistiigi/binfmt-install:latest" >/dev/null

exec docker run --rm --platform linux/arm/v7 \
  --volume="$WORKTREE/dist:/workspace" \
  --volume="$WORKTREE/build:/action" \
  --env=RUNNER_DEBUG=1 \
  --env=SETUP="$SETUP" \
  --env=PYTHONUNBUFFERED=1 \
  "eeems/nuitka-arm-builder:bullseye-$PYVER" \
  sh -ec 'cd /tmp
. /opt/lib/nuitka/bin/activate
python -u /action/build.py "'"$PKG"'" /workspace'
