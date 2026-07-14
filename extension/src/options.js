const CONTENT_SCRIPT_ID = "tandoor2typst-recipe-button";

async function load() {
  const settings = await getSettings();
  document.getElementById("tandoorHost").value = settings.tandoorHost || "";
  document.getElementById("tandoorToken").value = settings.tandoorToken || "";
  document.getElementById("backendUrl").value = settings.backendUrl || "";
}

async function registerRecipeContentScript(tandoorHost) {
  const origin = normalizeOrigin(tandoorHost);
  if (!origin) throw new Error("Ungültige Tandoor-URL.");

  const existing = await chrome.scripting.getRegisteredContentScripts({ ids: [CONTENT_SCRIPT_ID] });
  if (existing.length) {
    await chrome.scripting.unregisterContentScripts({ ids: [CONTENT_SCRIPT_ID] });
  }

  await chrome.scripting.registerContentScripts([
    {
      id: CONTENT_SCRIPT_ID,
      matches: [`${origin}/recipe/*`],
      js: ["src/settings.js", "src/content.js"],
      runAt: "document_idle",
    },
  ]);
}

function setStatus(text, kind) {
  const status = document.getElementById("status");
  status.textContent = text;
  status.className = kind || "";
}

async function save() {
  const tandoorHost = document.getElementById("tandoorHost").value.trim().replace(/\/$/, "");
  const tandoorToken = document.getElementById("tandoorToken").value.trim();
  const backendUrl = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");

  if (!tandoorHost || !tandoorToken || !backendUrl) {
    setStatus("Bitte alle Felder ausfüllen.", "error");
    return;
  }

  const tandoorOrigin = normalizeOrigin(tandoorHost);
  const backendOrigin = normalizeOrigin(backendUrl);
  if (!tandoorOrigin || !backendOrigin) {
    setStatus("Bitte gültige URLs eingeben (inkl. http:// oder https://).", "error");
    return;
  }

  setStatus("Berechtigungen werden angefragt …");
  const granted = await chrome.permissions.request({
    origins: [`${tandoorOrigin}/*`, `${backendOrigin}/*`],
  });
  if (!granted) {
    setStatus("Berechtigung wurde nicht erteilt – Einstellungen nicht gespeichert.", "error");
    return;
  }

  await saveSettings({ tandoorHost, tandoorToken, backendUrl });
  await registerRecipeContentScript(tandoorHost);

  setStatus("Gespeichert! Lade die Rezeptseite neu, damit der Button erscheint.", "success");
}

document.getElementById("save").addEventListener("click", save);
load();
