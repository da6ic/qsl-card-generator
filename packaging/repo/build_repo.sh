#!/usr/bin/env bash
# Baut aus einem .deb und einem .rpm ein signiertes APT- und DNF-Repository als
# statische Webseite — gedacht für GitHub Pages (siehe .github/workflows/release.yml).
#
#   GPG_KEY_ID=<schlüssel> BASE_URL=https://da6ic.github.io/qsl-card-generator \
#       packaging/repo/build_repo.sh <paketordner> <zielordner>
#
# Der private Schlüssel muss im gpg-Agent liegen; signiert wird
#   * APT: dists/stable/InRelease + Release.gpg (apt prüft darüber jede Paketliste)
#   * DNF: repodata/repomd.xml.asc (repo_gpgcheck) — das .rpm selbst signiert
#          schon build_packages.sh (gpgcheck).
#
# Das Repository enthält bewusst nur die **neueste** Fassung: Pages ersetzt bei
# jeder Veröffentlichung die ganze Seite, und ein Programm wie dieses braucht
# keine alten Stände zum Zurückrollen per apt — die liegen weiter als Dateien
# unter „Releases" auf GitHub.
#
# Benötigt: gpg, apt-ftparchive (Paket apt-utils), createrepo_c (createrepo-c).

set -euo pipefail

if [ $# -ne 2 ] || [ -z "${GPG_KEY_ID:-}" ] || [ -z "${BASE_URL:-}" ]; then
    echo "Aufruf: GPG_KEY_ID=… BASE_URL=… $0 <paketordner> <zielordner>" >&2
    exit 2
fi

PKGS="$(cd "$1" && pwd)"
mkdir -p "$2"
SITE="$(cd "$2" && pwd)"
BASE_URL="${BASE_URL%/}"
APP_ID="qsl-karten-generator"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

shopt -s nullglob
debs=("$PKGS"/*.deb)
rpms=("$PKGS"/*.rpm)
if [ ${#debs[@]} -eq 0 ] || [ ${#rpms[@]} -eq 0 ]; then
    echo "Fehler: in $PKGS fehlt ein .deb oder ein .rpm." >&2
    exit 1
fi

# --- Öffentlicher Schlüssel ---------------------------------------------------
# .asc (Text) für dnf und zum Ansehen, .gpg (binär) als apt-Schlüsselbund.
gpg --batch --yes --armor --export "$GPG_KEY_ID" > "$SITE/$APP_ID.asc"
gpg --batch --yes --export "$GPG_KEY_ID" > "$SITE/$APP_ID.gpg"

# --- APT ------------------------------------------------------------------------
APT="$SITE/apt"
mkdir -p "$APT/pool/main" "$APT/dists/stable/main/binary-amd64"
cp "${debs[@]}" "$APT/pool/main/"
(
    cd "$APT"
    apt-ftparchive packages pool > dists/stable/main/binary-amd64/Packages
    gzip -9kf dists/stable/main/binary-amd64/Packages
    apt-ftparchive \
        -o APT::FTPArchive::Release::Origin="$APP_ID" \
        -o APT::FTPArchive::Release::Label="QSL-Karten-Generator" \
        -o APT::FTPArchive::Release::Suite=stable \
        -o APT::FTPArchive::Release::Codename=stable \
        -o APT::FTPArchive::Release::Architectures=amd64 \
        -o APT::FTPArchive::Release::Components=main \
        -o APT::FTPArchive::Release::Description="QSL-Karten-Generator für Debian/Ubuntu" \
        release dists/stable > dists/stable/Release
    gpg --batch --yes --local-user "$GPG_KEY_ID" --clearsign \
        -o dists/stable/InRelease dists/stable/Release
    gpg --batch --yes --local-user "$GPG_KEY_ID" --armor --detach-sign \
        -o dists/stable/Release.gpg dists/stable/Release
)

# --- DNF ------------------------------------------------------------------------
RPM="$SITE/rpm"
mkdir -p "$RPM"
cp "${rpms[@]}" "$RPM/"
createrepo_c --quiet "$RPM"
gpg --batch --yes --local-user "$GPG_KEY_ID" --armor --detach-sign \
    -o "$RPM/repodata/repomd.xml.asc" "$RPM/repodata/repomd.xml"

cat > "$SITE/$APP_ID.repo" <<EOF
[$APP_ID]
name=QSL-Karten-Generator
baseurl=$BASE_URL/rpm
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=$BASE_URL/$APP_ID.asc
EOF

# --- Startseite mit Anleitung -----------------------------------------------------
sed "s|@BASE_URL@|$BASE_URL|g" "$HERE/index.html" > "$SITE/index.html"
# Pages soll die Ordner nicht durch Jekyll schicken.
touch "$SITE/.nojekyll"

echo "Repository: $SITE"
