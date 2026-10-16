# wheels

Automation for building and mirroring Python wheels.

## Current state

numpy and pillow are compiled **natively** in this repository on
`debian-armv7l`. Debian 11 (bullseye) is EOL, so the default
`deb.debian.org` apt repositories no longer resolve, and the two `pillow`
and `numpy` jobs in `.github/workflows/build.yml` rewrite those sources to
`archive.debian.org` before `apt-get update`:

```
sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g' /etc/apt/sources.list
sed -i 's|http://deb.debian.org/debian-security|http://archive.debian.org/debian-security|g' /etc/apt/sources.list
```

These lines live in the `pillow` job (around L271) and the `numpy` job
(around L323) of `build.yml`. The mirror job then deploys the resulting
wheels. So numpy and pillow are **not** deploy-only; their source wheels
are produced by dedicated jobs that compile them on 32-bit Debian.

## Build process

The other build jobs compile against the standard **manylinux wheel**
specification (`manylinux-armv7l-glibc`/`musl`, `manylinux-x86_64-glibc`/
`musl`, `manylinux-riscv64-glibc`/`musl`, …), using PEP 668 isolated build
hooks (`build` plus pyproject `pyproject-hooks`, `DefaultIsolatedEnv`).
numpy and pillow additionally require the native `debian-armv7l` build path
above so their C extensions can be compiled on 32-bit Debian.

## Python 3.12 compatibility

numpy and pillow already support Python 3.12 in their upstream releases
(numpy >= 1.26, Pillow >= 10). Any remaining compatibility concern
therefore lives upstream, not in this repository.

## No code changes needed

The repository already contains the archive.debian.org apt-get workaround
needed to build numpy and pillow on EOL Debian 11, and `build.yml` is
byte-identical to commit `9ef2b25`. The manylinux build and Python 3.12
support are intact, so no further edits to the CI configuration are
required.
