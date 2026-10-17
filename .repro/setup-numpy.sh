SUDO=''
if [ "$EUID" -ne 0 ]; then
  SUDO=sudo
fi
export DEBIAN_FRONTEND="noninteractive"

# Install binfmt_misc + QEMU before apt-get. The debian-armv7l packages ship
# as arm ELF; without binfmt_misc they are rejected by the host kernel with
# "exec format error" before apt-get below ever runs.
if command -v apt-get >/dev/null; then
  apt-get update
  apt-get install -y --no-wrap binfmt-misc qemu-user-static
fi

# Debian 11 is EOL, so the default deb.debian.org mirrors are gone. Point the
# debian apt sources at archive.debian.org before apt-get update. The list
# sources cover both flat entries and line-continued blocks, so rewrite the
# debian URL wherever it appears, including in sources.list.d.
sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g' /etc/apt/sources.list
sed -i 's|http://deb.debian.org/debian-security|http://archive.debian.org/debian-security|g' /etc/apt/sources.list
sed -i 's|http://deb.debian.org/debian-all|http://archive.debian.org/debian-all|g' /etc/apt/sources.list.d/
sed -i 's|http://deb.debian.org|http://archive.debian.org|g' /etc/apt/sources.list.d/
$SUDO apt-get update --allow-unencrypted
$SUDO apt-get install -y \
  gcc \
  g++ \
  gfortran \
  libopenblas-dev \
  liblapack-dev \
  pkg-config \
  python3-pip \
  python3-dev \
  cmake
