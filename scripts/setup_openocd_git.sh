#!/usr/bin/env bash
set -euo pipefail

echo "== EmbedForge OpenOCD Git setup =="

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
  --prefix=/opt/openocd-git \
  --enable-cmsis-dap \
  --enable-stlink \
  --enable-jlink \
  --enable-ftdi \
  --enable-ti-icdi \
  --enable-xds110 \
  --enable-dummy \
  --enable-linuxgpiod

make -j"$(nproc)"

echo "== Installing to /opt/openocd-git =="
sudo make install

sudo tee /opt/openocd-git/EMBEDFORGE_BUILD_INFO >/dev/null <<EOF
source=git
remote=https://github.com/openocd-org/openocd.git
branch=master
commit=$OPENOCD_COMMIT
date=$OPENOCD_DATE
built_at=$(date -Is)
prefix=/opt/openocd-git
EOF

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/openocd-git" <<'EOF'
#!/usr/bin/env bash
exec /opt/openocd-git/bin/openocd "$@"
EOF

chmod +x "$HOME/.local/bin/openocd-git"

if [[ -f "$HOME/tools/openocd-git/contrib/60-openocd.rules" ]]; then
  sudo cp "$HOME/tools/openocd-git/contrib/60-openocd.rules" /etc/udev/rules.d/
  sudo groupadd -f plugdev
  sudo usermod -aG plugdev "$USER"
  sudo udevadm control --reload-rules
  sudo udevadm trigger
fi

echo "[INFO] Please unplug/replug your debug probe."
echo "[INFO] You may need to log out and log in again for plugdev group changes."

/opt/openocd-git/bin/openocd --version
"$HOME/.local/bin/openocd-git" --version

if [[ -f /opt/openocd-git/EMBEDFORGE_BUILD_INFO ]]; then
  cat /opt/openocd-git/EMBEDFORGE_BUILD_INFO
fi
