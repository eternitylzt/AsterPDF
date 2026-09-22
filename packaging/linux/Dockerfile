FROM almalinux:8
RUN dnf -y install epel-release && dnf -y install python3.11 python3.11-pip python3.11-devel gcc gcc-c++ binutils rpm-build git tar xz mesa-libGL mesa-libEGL libX11 libXext libXrender libXcursor libXi libxcb libxkbcommon-x11 xcb-util-cursor xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm fontconfig freetype dbus-libs alsa-lib dejavu-sans-fonts && dnf clean all
WORKDIR /src
COPY . .
RUN python3.11 -m pip install --upgrade pip && python3.11 -m pip install -e '.[dev]'
ENV QT_QPA_PLATFORM=offscreen
RUN python3.11 -m pytest -q tests/test_release_101.py tests/test_release_11.py tests/test_pdf_workflows.py tests/test_preservation.py tests/test_release_120.py tests/test_release_121.py -k 'not video_selection_layer_and_playback'
RUN python3.11 scripts/collect_licenses.py && python3.11 -m PyInstaller --noconfirm AsterPDF.spec && python3.11 scripts/linux_packages.py
