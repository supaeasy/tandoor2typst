# Tandoor to PDF (Typst)

Browser extension + Docker backend that turns recipes from [Tandoor](https://github.com/TandoorRecipes/recipes)
into nice-looking PDFs using [Typst](https://typst.app/) - one at a time via a button on the recipe page,
or collected into a single cookbook PDF via the extension's menu.

Since browsers can't run the Typst compiler themselves (Chrome's Manifest V3 forbids the
`unsafe-eval` that typst's WASM build currently needs, even inside a background service worker),
a small Docker container (meant to run on your NAS, e.g. via Portainer) fetches recipes through
the Tandoor API and compiles the PDF using the real Typst CLI. The backend holds no credentials -
the Tandoor host and API token are sent by the browser with every request.

## About

This is an unofficial, third-party companion tool for [Tandoor Recipes](https://github.com/TandoorRecipes/recipes),
the excellent self-hosted recipe manager this whole project is built around. It is not affiliated with,
endorsed by, or officially connected to the Tandoor Recipes project in any way - it simply talks to a
running Tandoor instance through its public API to turn your own recipes into printable PDFs.

The recipe layout is adapted from [a Typst template by Adrian Vollmer](https://gist.github.com/AdrianVollmer/07edab2b1fba2747fbf45291ab73d81e).

## 1. Start the backend container (NAS / Portainer)

1. Copy the `backend/` folder to your NAS (or point Portainer directly at this git repo).
2. In Portainer: **Stacks → Add stack**, using `backend/docker-compose.yml` (build context must point
   at the `backend/` folder), then deploy.
   - The image is based on `python:3.12-slim` plus the Typst CLI binary (~tens of MB, not the
     gigabytes a TeX Live image needs) - the first build is quick.
   - Default port in the compose file: `8124` (container-internal `8080`).
3. Once it's up, check `http://<NAS-IP>:8124/healthz` - it should return `{"status":"ok"}`.

## 2. Create a Tandoor API token

In Tandoor: `[Tandoor URL]/api/access-token/` → create a token with `read` scope and note it down.

## 3. Load the extension

1. Open `chrome://extensions` (or `about:debugging` in Firefox) and enable developer mode.
2. "Load unpacked" → select the `extension/` folder.
3. Click the extension icon → "Change settings" (or right-click → Options) and fill in:
   - **Tandoor instance URL**: e.g. `https://tandoor.my-domain.com`
   - **API token**: the token you just created
   - **Backend server URL**: e.g. `http://192.168.1.50:8124`
4. Save → the browser will ask for permission to access these two addresses; confirm.
5. Reload a recipe page in Tandoor → a small PDF icon button appears in the top toolbar next to the
   search button whenever you're viewing a recipe.

## Downloading all recipes as a collected PDF

Click the extension icon → "📚 All recipes as PDF". This builds a single cookbook PDF with page
breaks between recipes. For large recipe collections this can take a while (fetching images, then a
single compile pass); progress is shown live in the popup, and the job keeps running in the
background even if you close the popup - the download starts automatically once it's done.

## Notes

- The backend is intentionally stateless (no stored token) and meant for use on your own LAN (CORS is
  open, `*`). Don't expose it unprotected to the internet.
- Recipe layout (`backend/templates/recipe-template.typ`) can be tuned directly; rebuild the container
  after changes.
- If you reload/re-add the extension and the recipe-page button doesn't reappear, remove and re-add
  the extension rather than just clicking "reload" - dynamically registered content scripts don't
  always pick up cleanly otherwise.

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) - free to use and modify for noncommercial purposes;
commercial use requires the copyright holder's permission.

---

# Tandoor zu PDF (Typst) - Deutsch

Browser-Erweiterung + Docker-Backend, das Rezepte aus [Tandoor](https://github.com/TandoorRecipes/recipes)
mit [Typst](https://typst.app/) als hübsches PDF herunterlädt - einzeln per Button auf der Rezeptseite,
oder gesammelt als ein Kochbuch-PDF über das Erweiterungsmenü.

Da Browser den Typst-Compiler nicht selbst ausführen können (Manifest V3 verbietet das `unsafe-eval`,
das Typsts WASM-Build derzeit auch in einem Background-Service-Worker benötigt), übernimmt ein kleiner
Docker-Container (gedacht zum Betrieb auf deinem NAS, z.B. via Portainer) das Abrufen der Rezepte über
die Tandoor-API und die Kompilierung mit dem echten Typst-CLI. Das Backend enthält keine
Zugangsdaten-Logik - Host und Token werden bei jeder Anfrage vom Browser mitgeschickt.

## Über dieses Projekt

Dies ist ein inoffizielles Zusatz-Tool für [Tandoor Recipes](https://github.com/TandoorRecipes/recipes),
den hervorragenden selbst gehosteten Rezeptmanager, um den dieses gesamte Projekt herum gebaut ist. Es
steht in keiner Verbindung zum offiziellen Tandoor-Recipes-Projekt, wird nicht von ihm unterstützt oder
autorisiert - es kommuniziert lediglich über dessen öffentliche API mit einer laufenden Tandoor-Instanz,
um eigene Rezepte in druckbare PDFs zu verwandeln.

Das Rezept-Layout basiert auf [einer Typst-Vorlage von Adrian Vollmer](https://gist.github.com/AdrianVollmer/07edab2b1fba2747fbf45291ab73d81e).

## 1. Backend-Container starten (NAS / Portainer)

1. Repo-Ordner `backend/` auf dein NAS kopieren (oder Portainer direkt auf dieses Git-Repo zeigen lassen).
2. In Portainer: **Stacks → Add stack**, `backend/docker-compose.yml` verwenden (Build-Kontext
   muss auf den `backend/`-Ordner zeigen), deployen.
   - Das Image basiert auf `python:3.12-slim` plus dem Typst-CLI-Binary (einige Dutzend MB, nicht die
     Gigabytes, die ein TeX-Live-Image braucht) - der erste Build geht entsprechend schnell.
   - Standardport im Compose-File: `8124` (Container intern `8080`).
3. Nach dem Start prüfen: `http://<NAS-IP>:8124/healthz` sollte `{"status":"ok"}` liefern.

## 2. Tandoor-API-Token erstellen

In Tandoor: `[Tandoor-URL]/api/access-token/` → Token mit Scope `read` erstellen und notieren.

## 3. Erweiterung laden

1. `chrome://extensions` (oder `about:debugging` in Firefox) öffnen, Entwicklermodus aktivieren.
2. „Entpackte Erweiterung laden" → Ordner `extension/` auswählen.
3. Auf das Erweiterungssymbol klicken → „Einstellungen ändern" (oder Rechtsklick → Optionen) und ausfüllen:
   - **Tandoor-Instanz-URL**: z.B. `https://tandoor.meine-domain.de`
   - **API-Token**: der eben erstellte Token
   - **Backend-Server-URL**: z.B. `http://192.168.1.50:8124`
4. Speichern → Browser fragt nach Zugriffsrechten für diese beiden Adressen, bestätigen.
5. Eine Rezeptseite in Tandoor neu laden → in der oberen Werkzeugleiste neben dem Suchen-Button
   erscheint ein kleiner PDF-Icon-Button, sobald du ein Rezept ansiehst.

## Alle Rezepte gesammelt herunterladen

Erweiterungssymbol anklicken → „📚 Alle Rezepte als PDF". Erzeugt ein einzelnes PDF-Kochbuch mit
Seitenumbrüchen zwischen den Rezepten. Bei vielen Rezepten kann das eine Weile dauern (Bilder werden
geladen, danach einmalig kompiliert); der Fortschritt wird live im Popup angezeigt, und der Job läuft
im Hintergrund weiter, auch wenn du das Popup schließt - der Download startet automatisch, sobald das
PDF fertig ist.

## Hinweise

- Das Backend ist bewusst zustandslos (kein gespeichertes Token) und für den Betrieb im eigenen LAN
  gedacht (CORS ist offen, `*`). Nicht ungeschützt aus dem Internet erreichbar machen.
- Das Rezept-Layout (`backend/templates/recipe-template.typ`) lässt sich direkt anpassen; danach den
  Container neu bauen.
- Falls nach dem Neuladen/erneuten Hinzufügen der Erweiterung der Button auf der Rezeptseite nicht
  erscheint: die Erweiterung komplett entfernen und neu hinzufügen statt nur "Neu laden" zu klicken -
  dynamisch registrierte Content-Scripts werden dadurch nicht immer sauber zurückgesetzt.

## Lizenz

[PolyForm Noncommercial License 1.0.0](LICENSE) - frei nutzbar und veränderbar für nicht-kommerzielle
Zwecke; kommerzielle Nutzung erfordert die Erlaubnis des Rechteinhabers.
