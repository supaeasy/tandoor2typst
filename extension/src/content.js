// Injected (dynamically registered, see options.js) on the configured Tandoor
// instance. Tandoor is a single-page app, so the top toolbar is the one
// element that's always present and never re-rendered from scratch across
// client-side navigation - we anchor there and just show/hide the button
// depending on whether the current URL is a recipe page.

(function () {
  if (window.__tandoor2typstInitialized) return;
  window.__tandoor2typstInitialized = true;

  const ICON_CLASS = "fa-solid fa-file-pdf v-icon notranslate v-theme--dark v-icon--size-default fa-fw";
  const SPINNER_CLASS = "fa-solid fa-spinner fa-spin v-icon notranslate v-theme--dark v-icon--size-default fa-fw";

  function currentRecipeId() {
    const match = window.location.pathname.match(/\/recipe\/(\d+)/);
    return match ? match[1] : null;
  }

  function buildButton() {
    const button = document.createElement("button");
    button.id = "tandoor2typst-button";
    button.type = "button";
    button.title = "Aktuelles Rezept als PDF herunterladen (Typst)";
    button.className =
      "v-btn v-btn--icon v-theme--dark v-btn--density-default v-btn--size-default v-btn--variant-text d-print-none";
    button.style.marginRight = "4px";

    const icon = document.createElement("i");
    icon.className = ICON_CLASS;
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);

    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const recipeId = currentRecipeId();
      if (!recipeId || button.disabled) return;

      button.disabled = true;
      icon.className = SPINNER_CLASS;
      try {
        const settings = await getSettings();
        if (!settings.tandoorHost || !settings.tandoorToken || !settings.backendUrl) {
          throw new Error("Bitte zuerst die Einstellungen der Erweiterung ausfüllen.");
        }
        const blob = await requestRecipePdf(
          settings.backendUrl,
          settings.tandoorHost,
          settings.tandoorToken,
          recipeId
        );
        const title = document.title.replace(/\s*[|·-]\s*Tandoor.*$/i, "").trim() || `rezept-${recipeId}`;
        triggerBlobDownload(blob, `${title}.pdf`);
      } catch (err) {
        console.error("tandoor2typst:", err);
        alert(`PDF-Erzeugung fehlgeschlagen: ${err.message}`);
      } finally {
        icon.className = ICON_CLASS;
        button.disabled = false;
      }
    });

    return button;
  }

  function ensureButtonInToolbar() {
    if (document.getElementById("tandoor2typst-button")) return true;

    const toolbar = document.querySelector(".v-toolbar__content");
    if (!toolbar) return false;

    const searchButton = Array.from(toolbar.querySelectorAll("button")).find((b) =>
      b.textContent.includes("Suchen")
    );

    const button = buildButton();
    if (searchButton && searchButton.parentNode) {
      searchButton.parentNode.insertBefore(button, searchButton);
    } else {
      toolbar.appendChild(button);
    }
    return true;
  }

  function tick() {
    if (!ensureButtonInToolbar()) return;
    const button = document.getElementById("tandoor2typst-button");
    button.style.display = currentRecipeId() ? "" : "none";
  }

  setInterval(tick, 500);
  tick();
})();
