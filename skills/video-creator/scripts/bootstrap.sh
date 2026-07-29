#!/usr/bin/env bash
# Prepare the capsule for video work and report the real operating envelope.
#
# The code capsule ships Python + Pillow + Noto CJK fonts but NOT ffmpeg, so
# this installs it (~25s, ~650 MB) and then prints the numbers every later
# decision depends on: free disk, RAM, cores. Run once per session; re-running
# is cheap (apt is a no-op when already installed).
set -uo pipefail

echo "== installing ffmpeg =="
if command -v ffmpeg >/dev/null 2>&1; then
  echo "  already present"
else
  sudo apt-get update -qq >/dev/null 2>&1
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/tmp/ffmpeg-install.log 2>&1 || {
    echo "  FAILED — see /tmp/ffmpeg-install.log"; tail -20 /tmp/ffmpeg-install.log; exit 1; }
  sudo apt-get clean >/dev/null 2>&1   # reclaim the .deb cache; disk is tight
fi
ffmpeg -version | head -1 | sed 's/^/  /'

echo "== fonts =="
for spec in "Noto Sans CJK SC:weight=200" "Noto Sans CJK SC:weight=80" "DejaVu Sans:weight=200"; do
  printf '  %-32s -> %s\n' "$spec" "$(fc-match -f '%{file}' "$spec")"
done

echo "== budget =="
printf '  cores : %s\n' "$(nproc)"
printf '  ram   : %s MB total, %s MB available\n' \
  "$(free -m | awk '/^Mem:/{print $2}')" "$(free -m | awk '/^Mem:/{print $7}')"
df -h / | tail -1 | awk '{printf "  disk  : %s free of %s (%s used)\n", $4, $2, $5}'

FREE_MB=$(df -m / | tail -1 | awk '{print $4}')
if [ "$FREE_MB" -lt 400 ]; then
  echo "  WARNING: under 400 MB free — delete scenes/ and clips/ intermediates between renders."
fi
echo "== ready =="
