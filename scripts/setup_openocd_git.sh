#!/usr/bin/env bash
set -euo pipefail

echo "== EmbedForge OpenOCD Git setup =="

PREFIX="${EMBEDFORGE_OPENOCD_PREFIX:-$HOME/.local/openocd-git}"
USE_SYSTEM_PREFIX=0
if [[ "${1:-}" == "--system" ]]; then
  PREFIX="/opt/openocd-git"
  USE_SYSTEM_PREFIX=1
fi

echo "== Installing build dependencies =="
sudo apt update
sudo apt install -y \
  git build-essential pkg-config \
  autoconf automake libtool texinfo \
  libusb-1.0-0-dev libhidapi-dev libftdi1-dev \
  libcapstone-dev libgpiod-dev tcl-dev

sudo apt install -y libjaylink-dev || echo "[WARN] libjaylink-dev not available, continue without it"

echo "== Fetching latest OpenOCD master from Git =="
mkdir -p "$HOME/tools"
cd "$HOME/tools"

if [[ ! -d openocd-git ]]; then
  git clone https://github.com/openocd-org/openocd.git openocd-git
  cd openocd-git
else
  cd openocd-git
  git remote -v
  git fetch origin
  git checkout master
  git pull --ff-only origin master
fi

git submodule update --init --recursive
OPENOCD_COMMIT="$(git rev-parse HEAD)"
OPENOCD_DATE="$(git log -1 --format=%ci)"
echo "OpenOCD commit: $OPENOCD_COMMIT"
echo "OpenOCD date: $OPENOCD_DATE"

echo "== Building OpenOCD =="
./bootstrap

./configure \
  --prefix="$PREFIX" \
  --enable-cmsis-dap \
  --enable-stlink \
  --enable-jlink \
  --enable-ftdi \
  --enable-ti-icdi \
  --enable-xds110 \
  --enable-dummy \
  --enable-linuxgpiod

make -j"$(nproc)"

echo "== Installing to $PREFIX =="
if [[ "$USE_SYSTEM_PREFIX" -eq 1 ]]; then
  sudo make install
else
  make install
fi

BUILD_INFO="$PREFIX/EMBEDFORGE_BUILD_INFO"
if [[ "$USE_SYSTEM_PREFIX" -eq 1 ]]; then
  sudo tee "$BUILD_INFO" >/dev/null <<EOF
source=git
remote=https://github.com/openocd-org/openocd.git
branch=master
commit=$OPENOCD_COMMIT
date=$OPENOCD_DATE
built_at=$(date -Is)
prefix=$PREFIX
EOF
else
  cat > "$BUILD_INFO" <<EOF
source=git
remote=https://github.com/openocd-org/openocd.git
branch=master
commit=$OPENOCD_COMMIT
date=$OPENOCD_DATE
built_at=$(date -Is)
prefix=$PREFIX
EOF
fi

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/openocd-git" <<EOF
#!/usr/bin/env bash
exec "$PREFIX/bin/openocd" "\$@"
EOF

chmod +x "$HOME/.local/bin/openocd-git"

if [[ -f "$HOME/tools/openocd-git/contrib/60-openocd.rules" ]]; then
  echo "[INFO] OpenOCD udev rules are available but were not installed automatically."
  echo "[INFO] To configure probe permissions manually, run:"
  echo "  sudo cp \"$HOME/tools/openocd-git/contrib/60-openocd.rules\" /etc/udev/rules.d/"
  echo "  sudo groupadd -f plugdev"
  echo "  sudo usermod -aG plugdev \"$USER\""
  echo "  sudo udevadm control --reload-rules"
  echo "  sudo udevadm trigger"
fi

echo "[INFO] Please unplug/replug your debug probe."
echo "[INFO] You may need to log out and log in again for plugdev group changes."

"$PREFIX/bin/openocd" --version
"$HOME/.local/bin/openocd-git" --version

if [[ -f "$BUILD_INFO" ]]; then
  cat "$BUILD_INFO"
fi
