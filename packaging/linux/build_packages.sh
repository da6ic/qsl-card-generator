#!/usr/bin/env bash
# Macht aus dem fertigen PyInstaller-Bündel die drei Linux-Pakete:
#
#   .deb       für Debian/Ubuntu   (apt)
#   .rpm       für Fedora & Co.    (dnf)
#   .AppImage  für alles andere    (eine Datei, ohne Installation)
#
#   packaging/linux/build_packages.sh <bündelordner> <version> <ausgabeordner>
#
# Beispiel (nach `scripts/build_app.py --clean`):
#
#   packaging/linux/build_packages.sh dist/QSL-Karten-Generator 0.4.0 dist/pakete
#
# Benötigt: dpkg-deb, rpmbuild (Paket `rpm`), für das AppImage zusätzlich
# `appimagetool` im PATH oder in $APPIMAGETOOL. Fehlt es, wird das AppImage
# übersprungen (mit Hinweis), die anderen beiden entstehen trotzdem.
#
# Signieren (optional): Ist $GPG_KEY_ID gesetzt und der Schlüssel im gpg-Agent,
# wird das .rpm signiert. Das .deb wird bewusst **nicht** einzeln signiert —
# apt prüft die Signatur des Repositorys (Release-Datei), nicht die des Pakets.
#
# Alle drei Pakete enthalten dasselbe Bündel unverändert. Installiert wird nach
# /opt/qsl-karten-generator (ein PyInstaller-Ordner gehört nicht nach /usr/lib:
# er bringt eigene Bibliotheken mit). Config, Cache und Protokoll landen wie
# gewohnt in ~/.config/qsl-karten-generator (siehe qslcards/paths.py) — der
# Programmordner selbst wird nie beschrieben.

set -euo pipefail

if [ $# -ne 3 ]; then
    echo "Aufruf: $0 <bündelordner> <version> <ausgabeordner>" >&2
    exit 2
fi

BUNDLE="$(cd "$1" && pwd)"
VERSION="$2"
mkdir -p "$3"
OUT="$(cd "$3" && pwd)"

APP_NAME="QSL-Karten-Generator"
APP_ID="qsl-karten-generator"
SUMMARY="Erzeugt aus einem Logbuch (ADIF/Cabrillo) QSL-Karten als PDF"
HOMEPAGE="https://github.com/da6ic/qsl-card-generator"
MAINTAINER="DA6IC <361695662+da6ic@users.noreply.github.com>"
# PyInstaller bündelt keine glibc: das Programm braucht mindestens die glibc des
# Baurechners. Der Release-Workflow baut auf Ubuntu 22.04 (glibc 2.35) — damit
# laufen Debian 12+, Ubuntu 22.04+ und jedes unterstützte Fedora.
MIN_GLIBC="${MIN_GLIBC:-2.35}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
ICONS="$ROOT/qslcards/assets/icons"
ICON_SIZES=(16 32 48 64 128 256 512)

if [ ! -x "$BUNDLE/$APP_NAME" ]; then
    echo "Fehler: $BUNDLE/$APP_NAME fehlt — erst scripts/build_app.py laufen lassen." >&2
    exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- Gemeinsamer Dateibaum für .deb und .rpm --------------------------------
STAGE="$WORK/root"
mkdir -p "$STAGE/opt/$APP_ID" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/doc/$APP_ID"
cp -a "$BUNDLE/." "$STAGE/opt/$APP_ID/"
ln -s "/opt/$APP_ID/$APP_NAME" "$STAGE/usr/bin/$APP_ID"
sed "s|^Exec=.*|Exec=$APP_ID|; /^# Exec wird/d" "$HERE/$APP_ID.desktop" \
    > "$STAGE/usr/share/applications/$APP_ID.desktop"
for size in "${ICON_SIZES[@]}"; do
    install -Dm644 "$ICONS/app_icon_${size}.png" \
        "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps/$APP_ID.png"
done
install -Dm644 "$ICONS/app_icon.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m644 "$ROOT/LICENSE" "$STAGE/usr/share/doc/$APP_ID/copyright"
# Verzeichnisse 755, Dateien behalten ihre Rechte (ausführbare bleiben es).
find "$STAGE" -type d -exec chmod 755 {} +
chmod -R u+rwX,go+rX,go-w "$STAGE"

# --- .deb ---------------------------------------------------------------------
build_deb() {
    local deb_root="$WORK/deb"
    cp -a "$STAGE" "$deb_root"
    mkdir -p "$deb_root/DEBIAN"
    local size_kb
    size_kb="$(du -sk "$deb_root" | cut -f1)"
    cat > "$deb_root/DEBIAN/control" <<EOF
Package: $APP_ID
Version: $VERSION
Architecture: amd64
Maintainer: $MAINTAINER
Installed-Size: $size_kb
Depends: libc6 (>= $MIN_GLIBC), libx11-6, libxft2, libfontconfig1
Recommends: xdg-utils
Section: hamradio
Priority: optional
Homepage: $HOMEPAGE
Description: $SUMMARY
 Liest ein Logbuch (ADIF oder Cabrillo) oder holt die QSOs aus Wavelog,
 schlägt die Zustellwege bei QRZ/HamQTH nach und erzeugt druckfertige
 QSL-Karten (A6, DARC-Layout) als PDF. Bringt Python und Tcl/Tk 9 mit.
EOF
    local target="$OUT/${APP_ID}_${VERSION}_amd64.deb"
    dpkg-deb --root-owner-group -Zxz --build "$deb_root" "$target" >/dev/null
    echo "deb:      $target"
}

# --- .rpm ---------------------------------------------------------------------
build_rpm() {
    local top="$WORK/rpmbuild"
    mkdir -p "$top"/{BUILD,RPMS,SPECS,SRPMS,SOURCES}
    # RPM-Versionen dürfen keinen Bindestrich enthalten.
    local rpm_version="${VERSION//-/_}"
    cat > "$top/SPECS/$APP_ID.spec" <<EOF
Name:           $APP_ID
Version:        $rpm_version
Release:        1
Summary:        $SUMMARY
License:        GPL-3.0-or-later
URL:            $HOMEPAGE
BuildArch:      x86_64
# Das Bündel bringt seine Bibliotheken selbst mit. Ohne diese Zeile würde rpm
# jede davon als Abhängigkeit (und als Angebot!) ins Paket schreiben.
AutoReqProv:    no
Requires:       glibc >= $MIN_GLIBC
# Tk ist mit Xft gebaut (packaging/linux/tk_xft.sh) und nimmt diese vom System.
Requires:       libX11, libXft, fontconfig
Recommends:     xdg-utils

# Fertiges Bündel: nichts strippen, keine debuginfo, keine build-id-Links.
%global debug_package %{nil}
%global __strip /bin/true
%global __brp_strip %{nil}
%global __brp_strip_static_archive %{nil}
%global __brp_strip_comment_note %{nil}
%global __brp_mangle_shebangs %{nil}
%global __brp_python_bytecompile %{nil}
%global _build_id_links none

%description
Liest ein Logbuch (ADIF oder Cabrillo) oder holt die QSOs aus Wavelog,
schlägt die Zustellwege bei QRZ/HamQTH nach und erzeugt druckfertige
QSL-Karten (A6, DARC-Layout) als PDF. Bringt Python und Tcl/Tk 9 mit.

%install
cp -a "$STAGE/." %{buildroot}/

%files
/opt/$APP_ID
/usr/bin/$APP_ID
/usr/share/applications/$APP_ID.desktop
/usr/share/icons/hicolor/*/apps/$APP_ID.*
%license /usr/share/doc/$APP_ID/copyright
EOF
    rpmbuild --quiet -bb --define "_topdir $top" "$top/SPECS/$APP_ID.spec" >/dev/null
    local built
    built="$(find "$top/RPMS" -name '*.rpm' | head -n1)"
    local target="$OUT/$APP_ID-$rpm_version-1.x86_64.rpm"
    mv "$built" "$target"
    if [ -n "${GPG_KEY_ID:-}" ]; then
        rpmsign --addsign --define "_gpg_name $GPG_KEY_ID" "$target" >/dev/null
        echo "rpm:      $target (signiert)"
    else
        echo "rpm:      $target"
    fi
}

# --- AppImage -------------------------------------------------------------------
build_appimage() {
    local tool="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
    if [ -z "$tool" ]; then
        echo "AppImage: übersprungen (appimagetool nicht gefunden)"
        return
    fi
    local appdir="$WORK/$APP_NAME.AppDir"
    mkdir -p "$appdir/usr/lib"
    cp -a "$BUNDLE" "$appdir/usr/lib/$APP_ID"
    cat > "$appdir/AppRun" <<EOF
#!/bin/sh
# Startet das Bündel aus dem eingehängten AppImage.
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/lib/$APP_ID/$APP_NAME" "\$@"
EOF
    chmod 755 "$appdir/AppRun"
    cp "$STAGE/usr/share/applications/$APP_ID.desktop" "$appdir/$APP_ID.desktop"
    cp "$ICONS/app_icon_256.png" "$appdir/$APP_ID.png"
    cp "$ICONS/app_icon_256.png" "$appdir/.DirIcon"
    mkdir -p "$appdir/usr/share/icons/hicolor/256x256/apps"
    cp "$ICONS/app_icon_256.png" "$appdir/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
    local target="$OUT/$APP_NAME-$VERSION-x86_64.AppImage"
    # APPIMAGE_EXTRACT_AND_RUN: appimagetool ist selbst ein AppImage und
    # bräuchte sonst FUSE — das gibt es in Containern und CI-Läufern nicht.
    ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$tool" --no-appstream "$appdir" "$target" >/dev/null
    chmod 755 "$target"
    echo "AppImage: $target"
}

build_deb
build_rpm
build_appimage
