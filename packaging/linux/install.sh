#!/usr/bin/env bash
# Installiert den QSL-Karten-Generator für den angemeldeten Benutzer.
#
#   ./install.sh              # installieren
#   ./install.sh --uninstall  # wieder entfernen
#
# Bewusst **ohne sudo**: nach /usr/bin oder /opt zu installieren hieße, dass das
# Programm seinen eigenen Ordner nicht beschreiben kann — und dass für ein
# Update jedes Mal ein Passwort fällig wird. Alles landet unter ~/.local, wo es
# nach der XDG-Spezifikation hingehört und wo GNOME es von selbst findet.
#
# Das Skript liegt im entpackten Programmordner und arbeitet relativ zu sich
# selbst; es braucht das Repository nicht.

set -euo pipefail

APP_NAME="QSL-Karten-Generator"
APP_ID="qsl-karten-generator"

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$HOME/.local/opt/$APP_ID"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$PREFIX/applications"
ICON_ROOT="$PREFIX/icons/hicolor"

ICON_SIZES=(16 32 48 64 128 256 512)

uninstall() {
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/$APP_ID"
    rm -f "$DESKTOP_DIR/$APP_ID.desktop"
    for size in "${ICON_SIZES[@]}"; do
        rm -f "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
    done
    refresh_caches
    echo "$APP_NAME entfernt."
}

refresh_caches() {
    # Beide Aufrufe sind Kür: fehlt das Werkzeug, taucht der Eintrag nur etwas
    # später auf (spätestens nach der nächsten Anmeldung).
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 &&
        gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
}

check_runtime_deps() {
    # Beides gehört zu einer Fedora-Workstation, fehlt aber in einer minimalen
    # Installation. Ohne sie stirbt nichts, es fehlt nur eine Funktion —
    # deshalb Hinweis statt Abbruch.
    command -v xdg-open >/dev/null 2>&1 ||
        echo "Hinweis: 'xdg-open' fehlt (Paket xdg-utils) — 'PDF öffnen' und" \
             "'Ordner anzeigen' bleiben wirkungslos."
    command -v gsettings >/dev/null 2>&1 ||
        echo "Hinweis: 'gsettings' fehlt (Paket glib2) — das Farbthema folgt" \
             "dann nicht automatisch dem System."
}

install_app() {
    if [ ! -x "$SOURCE_DIR/$APP_NAME" ]; then
        echo "Fehler: '$SOURCE_DIR/$APP_NAME' nicht gefunden." >&2
        echo "Das Skript gehört in den entpackten Programmordner." >&2
        exit 1
    fi

    echo "Installiere nach $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    # Punktdateien mitkopieren, aber nicht das Skript selbst wieder in sich hinein.
    (cd "$SOURCE_DIR" && tar --exclude=./install.sh -cf - .) | (cd "$INSTALL_DIR" && tar -xf -)

    mkdir -p "$BIN_DIR"
    ln -sf "$INSTALL_DIR/$APP_NAME" "$BIN_DIR/$APP_ID"

    echo "Installiere Symbole"
    for size in "${ICON_SIZES[@]}"; do
        icon="$INSTALL_DIR/_internal/qslcards/assets/icons/app_icon_${size}.png"
        [ -f "$icon" ] || icon="$INSTALL_DIR/qslcards/assets/icons/app_icon_${size}.png"
        if [ -f "$icon" ]; then
            mkdir -p "$ICON_ROOT/${size}x${size}/apps"
            cp "$icon" "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
        fi
    done

    echo "Installiere Menüeintrag"
    mkdir -p "$DESKTOP_DIR"
    sed "s|^Exec=.*|Exec=$INSTALL_DIR/$APP_NAME|" \
        "$SOURCE_DIR/$APP_ID.desktop" > "$DESKTOP_DIR/$APP_ID.desktop"
    chmod 644 "$DESKTOP_DIR/$APP_ID.desktop"

    refresh_caches
    check_runtime_deps

    echo
    echo "$APP_NAME ist installiert."
    echo "  Start über das Anwendungsmenü oder: $BIN_DIR/$APP_ID"
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) echo "  ($BIN_DIR liegt nicht im PATH — für den Aufruf ohne Pfad ergänzen.)" ;;
    esac
    echo "  Config und Cache: ${XDG_CONFIG_HOME:-$HOME/.config}/$APP_ID/"
}

case "${1:-}" in
    --uninstall|-u) uninstall ;;
    "")             install_app ;;
    *)              echo "Aufruf: $0 [--uninstall]" >&2; exit 2 ;;
esac
