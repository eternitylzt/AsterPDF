#!/bin/bash
set -euo pipefail
if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y /packages/*.deb xvfb xauth
else
  dnf install -y /packages/*.rpm xorg-x11-server-Xvfb xorg-x11-xauth
fi
test -x /usr/bin/asterpdf
test -f /usr/share/applications/asterpdf.desktop
export QT_QPA_PLATFORM=xcb
export XDG_RUNTIME_DIR=/tmp/asterpdf-runtime
mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 1280x900x24 &
export DISPLAY=:99
sleep 2
timeout 45 asterpdf --smoke-test --data-dir /tmp/asterpdf-qa /opt/asterpdf/examples/AsterPDF-demo.pdf
timeout 45 asterpdf --smoke-test --data-dir /tmp/asterpdf-md /opt/asterpdf/examples/Markdown-math.md
timeout 90 asterpdf --verify-desktop /tmp/asterpdf-check --data-dir /tmp/asterpdf-check-settings /opt/asterpdf/examples/AsterPDF-media.pdf /opt/asterpdf/examples/Markdown-math.md
cat /tmp/asterpdf-check/desktop-report.json
if command -v apt-get >/dev/null; then apt-get remove -y asterpdf; else dnf remove -y asterpdf; fi
test ! -e /usr/bin/asterpdf
test ! -e /opt/asterpdf/AsterPDF
echo 'Package installation, X11 startup, PDF/Markdown launch and removal passed.'
