# Releases und Paketquellen (apt/dnf)

Ein Tag `vX.Y.Z` startet `.github/workflows/release.yml`. Der baut auf GitHubs
Läufern alle Programme, legt sie unter **Releases** ab und veröffentlicht ein
signiertes APT-/DNF-Repository auf **GitHub Pages**:

    https://da6ic.github.io/qsl-card-generator/

Die Startseite dort ([index.html](index.html)) erklärt den Anwendern die
Installation.

| Datei | für |
|---|---|
| `…-windows-x64.zip` | Windows 10/11, 64 Bit (Ordner mit `.exe`) |
| `…-macos-arm64.dmg` / `.zip` | macOS 11+ auf Apple Silicon |
| `…-x86_64.AppImage` | jedes Linux (x86_64, glibc ≥ 2.35) ohne Installation |
| `qsl-karten-generator_…_amd64.deb` | Debian 12+, Ubuntu 22.04+ (auch über apt) |
| `qsl-karten-generator-…x86_64.rpm` | Fedora (auch über dnf) |
| `…-linux-x86_64.tar.gz` | Linux-Ordner mit `install.sh` (wie bisher) |

Überall steckt Tcl/Tk 9 mit drin. Linux wird mit einem Python aus
python-build-standalone (über `uv`) auf Ubuntu 22.04 gebaut: Tk und X11 sind
darin enthalten, vom System braucht das Programm nur die glibc. Geprüft in
nackten Containern: Debian 12 und 13, Fedora 42 und 45 (Installation aus dem
Repository, Start, Fenster).

## Einmal einrichten

1. **Signierschlüssel anlegen** (auf dem eigenen Rechner, nicht in der Cloud):

       gpg --quick-gen-key "QSL-Karten-Generator Pakete <361695662+da6ic@users.noreply.github.com>" rsa4096 sign never

   Eine Passphrase ist erlaubt (dann Schritt 2b). Fingerabdruck anzeigen:
   `gpg --list-secret-keys --keyid-format long`.

2. **Secrets hinterlegen** — Repository ▸ Settings ▸ Secrets and variables ▸
   Actions ▸ *New repository secret*:

   a. `REPO_GPG_PRIVATE_KEY` = Ausgabe von
      `gpg --armor --export-secret-keys <FINGERABDRUCK>`
   b. `REPO_GPG_PASSPHRASE` = die Passphrase (nur wenn eine gesetzt ist)

   Den privaten Schlüssel zusätzlich sicher aufheben (z. B. USB-Stick). Geht er
   verloren, braucht es einen neuen, und jeder Anwender muss den neuen
   öffentlichen Schlüssel einmal neu holen.

3. **Pages einschalten** — Settings ▸ Pages ▸ *Build and deployment* ▸ Source:
   **GitHub Actions**. (Bei einem privaten Repository geht Pages nur mit einem
   bezahlten GitHub-Plan.)

## Eine Version ausliefern

    python scripts/release.py 0.4.0     # Version, Tests, Commit, Tag (lokal)
    git push origin main v0.4.0         # Tag hochladen -> Workflow startet

Der Workflow bricht ab, wenn der Tag nicht zur Version in
`qslcards/__init__.py` passt. Von Hand gestartet (Actions ▸ release ▸ *Run
workflow*) baut er nur und hängt die Dateien an den Lauf — zum Ausprobieren,
ohne Release und ohne Repository-Update.

Das Repository enthält immer nur die **neueste** Fassung; ältere bleiben unter
Releases.

## Was bewusst nicht dabei ist

* **Launchpad-PPA / Fedora-Copr**: beide bauen aus Quellpaketen auf eigenen
  Servern ohne Netz — für ein PyInstaller-Bündel mit Tk 9 passt das nicht, und
  Tk 9 fehlt Debian (8.6) ohnehin. Ein eigenes Repository auf Pages ist hier
  einfacher und braucht keinen fremden Dienst.
* **Notarisierung (macOS) und Code-Signatur (Windows)**: kosten ein
  Entwicklerkonto bzw. ein Zertifikat. Ohne sie fragt das System beim ersten
  Start nach (siehe `packaging/macos/LIESMICH.txt`, `packaging/windows/LIESMICH.txt`).
* **Intel-Macs, Windows-ARM, Linux-ARM**: nicht gebaut.
