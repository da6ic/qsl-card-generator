#!/usr/bin/env bash
# Lädt den Signierschlüssel aus den Secrets in gpg (nur im Release-Workflow).
#
#   GPG_PRIVATE_KEY   privater Schlüssel, ASCII-armored (Secret REPO_GPG_PRIVATE_KEY)
#   GPG_PASSPHRASE    optional (Secret REPO_GPG_PASSPHRASE)
#   REQUIRE_KEY=1     fehlender Schlüssel ist ein Fehler (Repository-Job);
#                     sonst nur ein Hinweis und das .rpm bleibt unsigniert.
#
# Schreibt GPG_KEY_ID (Fingerabdruck) nach $GITHUB_ENV, damit die folgenden
# Schritte (build_packages.sh, build_repo.sh) ihn finden.

set -euo pipefail

if [ -z "${GPG_PRIVATE_KEY:-}" ]; then
    if [ "${REQUIRE_KEY:-}" = "1" ]; then
        echo "::error::Secret REPO_GPG_PRIVATE_KEY fehlt — ohne Schlüssel kein signiertes Repository (siehe packaging/repo/README.md)."
        exit 1
    fi
    echo "::notice::Kein Signierschlüssel hinterlegt — das .rpm bleibt unsigniert."
    exit 0
fi

export GNUPGHOME="${GNUPGHOME:-$HOME/.gnupg}"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

printf '%s\n' "$GPG_PRIVATE_KEY" | gpg --batch --import 2>&1 | grep -v "^gpg: key .*: secret key imported" || true

if [ -n "${GPG_PASSPHRASE:-}" ]; then
    # rpmsign und apt-ftparchive rufen gpg ohne Terminal auf: Passphrase über
    # eine Datei im (flüchtigen) Läufer statt über pinentry.
    printf '%s' "$GPG_PASSPHRASE" > "$GNUPGHOME/passphrase"
    chmod 600 "$GNUPGHOME/passphrase"
    {
        echo "pinentry-mode loopback"
        echo "passphrase-file $GNUPGHOME/passphrase"
    } >> "$GNUPGHOME/gpg.conf"
    echo "allow-loopback-pinentry" >> "$GNUPGHOME/gpg-agent.conf"
    gpgconf --kill gpg-agent || true
fi

fingerprint="$(gpg --batch --list-secret-keys --with-colons | awk -F: '/^fpr/ {print $10; exit}')"
if [ -z "$fingerprint" ]; then
    echo "::error::Der Schlüssel aus REPO_GPG_PRIVATE_KEY ließ sich nicht importieren."
    exit 1
fi
echo "Signierschlüssel: $fingerprint"
echo "GPG_KEY_ID=$fingerprint" >> "${GITHUB_ENV:-/dev/null}"
