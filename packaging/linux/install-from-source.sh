#!/usr/bin/env bash
# Installiert den QSL-Karten-Generator AUS DER QUELLE für den angemeldeten
# Benutzer (Debian/Ubuntu und alles andere ohne gebautes Bündel).
#
#   packaging/linux/install-from-source.sh              # installieren/aktualisieren
#   packaging/linux/install-from-source.sh --uninstall  # Programm entfernen
#   INSTALL_DIR=/anderer/ordner packaging/linux/install-from-source.sh
#
# Anders als install.sh (für das PyInstaller-Bündel) kopiert dieses Skript den
# Quellstand nach ~/.local/opt/qsl-karten-generator, legt dort eine eigene venv
# an und richtet Starter, Menüeintrag und Symbole ein. Entwicklungsordner und
# installierte Fassung sind damit getrennt; ein erneuter Aufruf aktualisiert.
#
# Voraussetzung (einmal, mit sudo): python3-tk python3-venv
#
# Daten: Aus der Quelle gestartet liegen config.yaml, Lookup-Cache,
# wavelog_sent.json usw. im Programmordner (paths.data_dir). Ein Update lässt
# sie dort stehen; --uninstall fragt, bevor es sie löscht.

set -euo pipefail

APP_NAME="QSL-Karten-Generator"
APP_ID="qsl-karten-generator"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/opt/$APP_ID}"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$PREFIX/applications"
ICON_ROOT="$PREFIX/icons/hicolor"
ICON_SIZES=(16 32 48 64 128 256 512)
PYTHON="${PYTHON:-python3}"

# Benutzerdaten im Programmordner: nie überschreiben, nie beim Update löschen.
DATA_FILES=(config.yaml config.yaml.bak lookup_cache.json mostwanted.json
            wavelog_sent.json cty.dat qslcards.log)

refresh_caches() {
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 &&
        gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
}

uninstall() {
    rm -f "$BIN_DIR/$APP_ID" "$DESKTOP_DIR/$APP_ID.desktop"
    for size in "${ICON_SIZES[@]}"; do
        rm -f "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
    done
    refresh_caches
    if [ -d "$INSTALL_DIR" ]; then
        read -r -p "Auch Einstellungen und Cache in $INSTALL_DIR löschen? [j/N] " answer
        if [ "${answer,,}" = "j" ]; then
            rm -rf "$INSTALL_DIR"
        else
            rm -rf "$INSTALL_DIR/app/qslcards" "$INSTALL_DIR/venv"
            echo "Daten bleiben in $INSTALL_DIR/app."
        fi
    fi
    echo "$APP_NAME entfernt."
}

install_app() {
    "$PYTHON" -c "import tkinter, venv" 2>/dev/null || {
        echo "Fehler: Python ohne tkinter/venv. Bitte einmal:" >&2
        echo "  sudo apt install python3-tk python3-venv" >&2
        exit 1
    }

    echo "Kopiere Programm nach $INSTALL_DIR/app"
    mkdir -p "$INSTALL_DIR/app"
    excludes=(--exclude=.git --exclude=.venv --exclude=.venv-build --exclude=__pycache__
              --exclude='*.egg-info' --exclude=build --exclude=dist --exclude=tests
              --exclude=.idea --exclude='*.pdf' --exclude='*.adi' --exclude=beispiel-logs
              --exclude=wavelog_check_bericht.json)
    for f in "${DATA_FILES[@]}"; do excludes+=(--exclude="/$f"); done
    rsync -a --delete "${excludes[@]}" "$REPO_DIR/" "$INSTALL_DIR/app/"

    echo "Richte Python-Umgebung ein (dauert beim ersten Mal etwas)"
    [ -x "$INSTALL_DIR/venv/bin/python" ] || "$PYTHON" -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/python" -m pip install -q --upgrade pip
    # Editierbar in den KOPIERTEN Ordner: paths.py findet Handbuch, Assets und
    # config.yaml dann dort und nicht in site-packages.
    "$INSTALL_DIR/venv/bin/python" -m pip install -q -e "$INSTALL_DIR/app"

    echo "Lege Starter an"
    mkdir -p "$BIN_DIR"
    # -P: nie den aktuellen Ordner vor das installierte Paket stellen (aus einem
    # Quellordner gestartet liefe sonst dessen Fassung mit dessen config.yaml).
    cat > "$BIN_DIR/$APP_ID" <<EOF
#!/bin/sh
exec "$INSTALL_DIR/venv/bin/python" -P -m qslcards "\$@"
EOF
    chmod 755 "$BIN_DIR/$APP_ID"

    echo "Installiere Symbole und Menüeintrag"
    for size in "${ICON_SIZES[@]}"; do
        icon="$INSTALL_DIR/app/qslcards/assets/icons/app_icon_${size}.png"
        if [ -f "$icon" ]; then
            mkdir -p "$ICON_ROOT/${size}x${size}/apps"
            cp "$icon" "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
        fi
    done
    mkdir -p "$DESKTOP_DIR"
    sed "s|^Exec=.*|Exec=$BIN_DIR/$APP_ID|" \
        "$REPO_DIR/packaging/linux/$APP_ID.desktop" > "$DESKTOP_DIR/$APP_ID.desktop"
    chmod 644 "$DESKTOP_DIR/$APP_ID.desktop"
    refresh_caches

    version="$("$INSTALL_DIR/venv/bin/python" -c 'import qslcards; print(qslcards.__version__)')"
    tk="$("$INSTALL_DIR/venv/bin/python" -c 'import tkinter; print(tkinter.TkVersion)')"
    echo
    echo "$APP_NAME $version ist installiert (Tk $tk)."
    echo "  Start über das Anwendungsmenü oder: $BIN_DIR/$APP_ID"
    echo "  Einstellungen und Cache: $INSTALL_DIR/app/"
    [ "$tk" = "8.6" ] && echo "  Hinweis: Tk 8.6 — die Stift-/Schaltersymbole der Vorschau fehlen."
    true
}

case "${1:-}" in
    --uninstall|-u) uninstall ;;
    "")             install_app ;;
    *)              echo "Aufruf: $0 [--uninstall]" >&2; exit 2 ;;
esac
