// Injected (dynamically registered, see options.js) on the configured Tandoor
// instance. Tandoor is a single-page app, so the top toolbar is the one
// element that's always present and never re-rendered from scratch across
// client-side navigation - we anchor there and just show/hide the buttons
// depending on whether the current URL is a recipe page.

(function () {
  if (window.__tandoor2typstInitialized) return;
  window.__tandoor2typstInitialized = true;

  const SPINNER_CLASS = "fa-solid fa-spinner fa-spin v-icon notranslate v-theme--dark v-icon--size-default fa-fw";
  const iconClass = (name) => `fa-solid ${name} v-icon notranslate v-theme--dark v-icon--size-default fa-fw`;

  // Order here is the left-to-right order in the toolbar.
  const BUTTONS = [
    {
      id: "tandoor2typst-button",
      icon: iconClass("fa-file-pdf"),
      title: "Aktuelles Rezept als PDF herunterladen (Typst)",
      printMode: false,
      suffix: "",
    },
    {
      id: "tandoor2typst-print-button",
      icon: iconClass("fa-print"),
      title: "Aktuelles Rezept als PDF herunterladen - Druckversion ohne Hintergrundfarbe",
      printMode: true,
      suffix: "-Druck",
    },
  ];

  function currentRecipeId() {
    const match = window.location.pathname.match(/\/recipe\/(\d+)/);
    return match ? match[1] : null;
  }

  function buildButton(spec) {
    const button = document.createElement("button");
    button.id = spec.id;
    button.type = "button";
    button.title = spec.title;
    button.className =
      "v-btn v-btn--icon v-theme--dark v-btn--density-default v-btn--size-default v-btn--variant-text d-print-none";
    button.style.marginRight = "4px";

    const icon = document.createElement("i");
    icon.className = spec.icon;
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
          recipeId,
          spec.printMode
        );
        const title = document.title.replace(/\s*[|·-]\s*Tandoor.*$/i, "").trim() || `rezept-${recipeId}`;
        triggerBlobDownload(blob, `${title}${spec.suffix}.pdf`);
      } catch (err) {
        console.error("tandoor2typst:", err);
        alert(`PDF-Erzeugung fehlgeschlagen: ${err.message}`);
      } finally {
        icon.className = spec.icon;
        button.disabled = false;
      }
    });

    return button;
  }

  // Each button is ensured independently, so a page that still has the old
  // single button from before this one existed (e.g. extension updated while
  // the tab stayed open) gets the missing one added instead of nothing.
  function ensureButtonsInToolbar() {
    const missing = BUTTONS.filter((spec) => !document.getElementById(spec.id));
    if (missing.length === 0) return true;

    const toolbar = document.querySelector(".v-toolbar__content");
    if (!toolbar) return false;

    const searchButton = Array.from(toolbar.querySelectorAll("button")).find((b) =>
      b.textContent.includes("Suchen")
    );

    for (const spec of missing) {
      const button = buildButton(spec);
      if (searchButton && searchButton.parentNode) {
        searchButton.parentNode.insertBefore(button, searchButton);
      } else {
        toolbar.appendChild(button);
      }
    }
    return true;
  }

  function tick() {
    if (!ensureButtonsInToolbar()) return;
    const display = currentRecipeId() ? "" : "none";
    for (const spec of BUTTONS) {
      const button = document.getElementById(spec.id);
      if (button) button.style.display = display;
    }
  }

  setInterval(tick, 500);
  tick();
})();
