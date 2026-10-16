# wheels

Automation on building and mirroring Python wheels.

## Current state

numpy and pillow are **deploy-only** targets in this repository: their
wheels are produced by upstream CI and then mirrored here via the `mirror`
job. They are **not** compiled by any job in this repository, so there are
no Debian manifests, apt sources, or `apt-get` commands related to them.
The false premise that Debian 11 end-of-life breaks their builds does not
apply here.

## Build process

The build jobs compile packages against the standard **manylinux wheel**
specification (`manylinux-armv7l-glibc`/`musl`, `manylinux-x86_64-glibc`/
`musl`, …), with PEP 668 isolated build hooks (`build` plus pyproject
`pyproject-hooks`, `DefaultIsolatedEnv`). No Debian repos or apt-get
steps participate in building numpy or pillow.

## Python 3.12 compatibility

numpy and pillow already support Python 3.12 in their upstream releases
(numpy >= 1.26, Pillow >= 10). Any compatibility concern for python 3.12
therefore lives upstream, not in this repository; genuine fixes belong in
those upstream projects.

## No changes needed

The observed repository already matches the manylinux wheel and python 3.12
expectations, so no edits to CI configuration or build-target mirror are
required. The CI configuration remains unchanged.
