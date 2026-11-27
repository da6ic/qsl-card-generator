#!/usr/bin/env bash
# Tauscht im fertigen PyInstaller-Bündel die Tk-Bibliothek gegen eine mit Xft.
#
#   packaging/linux/tk_xft.sh <bündelordner>
#
# Beispiel (nach `scripts/build_app.py --clean`):
#
#   packaging/linux/tk_xft.sh dist/QSL-Karten-Generator
#
# Warum: Das Python von python-build-standalone (über uv) bringt zwar Tcl/Tk 9
# mit, sein Tk ist aber **ohne Xft** gebaut (Kennung `no-xft` in der Bibliothek).
# Ohne Xft kennt Tk unter X11 nur die alten Kern-Schriften: keine Kantenglättung,
# keine Systemschriften (DejaVu & Co.) — die Oberfläche sieht nach Pixelschrift
# aus. Windows und macOS betrifft das nicht, die zeichnen ihre Schrift selbst.
#
# Gebaut wird genau die Tk-Version, die im Bündel steckt — abgelesen aus
# `_tk_data/tk.tcl`, damit Bibliothek und Tk-Skripte zusammenpassen. Tcl selbst
# bleibt unverändert: Tk bindet sich über die Stubs an Tcl und braucht dessen
# Bibliothek nicht. `--disable-zipfs`: die Tk-Skripte
# liegen im Bündel ohnehin als Ordner (`_tk_data`).
#
# Benötigt: C-Compiler, make, curl und die Header von X11, Xft und Fontconfig
# (Debian/Ubuntu: `libx11-dev libxft-dev libfontconfig-dev`). Zur Laufzeit
# braucht das Bündel danach libXft und libfontconfig vom System — sie stehen
# deshalb als Abhängigkeit im .deb und im .rpm (siehe build_packages.sh).

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Aufruf: $0 <bündelordner>" >&2
    exit 2
fi

BUNDLE="$(cd "$1" && pwd)"
INTERNAL="$BUNDLE/_internal"
TK_VERSION="$(sed -n 's/^package require -exact tk *\([0-9.]*\).*/\1/p' "$INTERNAL/_tk_data/tk.tcl")"
if [ -z "$TK_VERSION" ]; then
    echo "Fehler: Tk-Version in $INTERNAL/_tk_data/tk.tcl nicht gefunden" >&2
    exit 1
fi

shopt -s nullglob
libs=("$INTERNAL"/libtcl9tk*.so)
shopt -u nullglob
if [ ${#libs[@]} -ne 1 ]; then
    echo "Fehler: genau eine libtcl9tk*.so in $INTERNAL erwartet, gefunden: ${#libs[@]}" >&2
    exit 1
fi
TARGET="${libs[0]}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fetch() {
    local name="$1"
    curl -fsSL --retry 3 -o "$WORK/$name.tar.gz" \
        "https://prdownloads.sourceforge.net/tcl/${name}${TK_VERSION}-src.tar.gz"
    tar -xzf "$WORK/$name.tar.gz" -C "$WORK"
}

echo "Tcl/Tk $TK_VERSION herunterladen …"
fetch tcl
fetch tk

jobs="$(nproc 2>/dev/null || echo 2)"

# Tcl nur bauen (nicht ins Bündel): Tk braucht tclConfig.sh und die Header.
echo "Tcl bauen …"
(
    cd "$WORK/tcl$TK_VERSION/unix"
    # Die mitgebauten Tcl-Pakete rufen das frische tclsh auf; es muss seine
    # libtcl finden, ohne dass sie installiert ist.
    export LD_LIBRARY_PATH="$PWD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    ./configure --prefix="$WORK/inst" --enable-shared >/dev/null
    make -j"$jobs" >/dev/null
    make install >/dev/null
)

echo "Tk mit Xft bauen …"
(
    cd "$WORK/tk$TK_VERSION/unix"
    export LD_LIBRARY_PATH="$WORK/inst/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    ./configure --prefix="$WORK/inst" --with-tcl="$WORK/inst/lib" \
        --enable-xft --disable-xss --disable-zipfs >"$WORK/tk-configure.log"
    if ! grep -q "whether to use xft... yes" "$WORK/tk-configure.log"; then
        echo "Fehler: configure hat Xft nicht gefunden (libxft-dev installiert?)" >&2
        exit 1
    fi
    make -j"$jobs" >/dev/null
)

built="$WORK/tk$TK_VERSION/unix/$(basename "$TARGET")"
if [ ! -f "$built" ]; then
    echo "Fehler: $built wurde nicht gebaut" >&2
    exit 1
fi
if ! ldd "$built" | grep -q 'libXft\.so'; then
    echo "Fehler: $built ist nicht gegen libXft gelinkt" >&2
    exit 1
fi

install -m 0755 "$built" "$TARGET"
echo "Tk mit Xft eingesetzt: $TARGET"
