const STATE_KEY = "tandoor2typst_job_state";
const IDLE_STATUSES = new Set(["idle", "finished", "error", undefined]);

function renderState(state) {
  const status = document.getElementById("status");
  status.textContent = state?.text || "";
  status.className = state?.status === "error" ? "error" : state?.status === "finished" ? "success" : "";
  const disabled = !IDLE_STATUSES.has(state?.status);
  document.getElementById("downloadAll").disabled = disabled;
  document.getElementById("downloadAllPrint").disabled = disabled;
}

async function init() {
  const settings = await getSettings();
  const configured = settings.tandoorHost && settings.tandoorToken && settings.backendUrl;
  document.getElementById("configured").style.display = configured ? "block" : "none";
  document.getElementById("unconfigured").style.display = configured ? "none" : "block";

  for (const id of ["openOptions", "openOptions2"]) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", () => chrome.runtime.openOptionsPage());
  }

  if (!configured) return;

  const initialState = await chrome.runtime.sendMessage({ type: "get-job-state" });
  renderState(initialState);

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "session" && changes[STATE_KEY]) {
      renderState(changes[STATE_KEY].newValue);
    }
  });

  async function startJob(printMode) {
    renderState({ status: "starting", text: "Starte …" });
    const response = await chrome.runtime.sendMessage({ type: "start-all-recipes", settings, printMode });
    if (!response?.started) {
      renderState({ status: "error", text: "Es läuft bereits ein Sammel-PDF-Job." });
    }
  }

  document.getElementById("downloadAll").addEventListener("click", () => startJob(false));
  document.getElementById("downloadAllPrint").addEventListener("click", () => startJob(true));

  const previewButton = document.getElementById("previewToc");
  const tocStatus = document.getElementById("tocStatus");
  previewButton.addEventListener("click", async () => {
    previewButton.disabled = true;
    tocStatus.className = "";
    tocStatus.textContent = "Lade Rezeptliste und teste Inhaltsverzeichnis …";
    try {
      const blob = await previewToc(settings.backendUrl, settings.tandoorHost, settings.tandoorToken);
      triggerBlobDownload(blob, "Inhaltsverzeichnis-Test.pdf");
      tocStatus.className = "success";
      tocStatus.textContent = "Fertig, PDF wurde heruntergeladen.";
    } catch (err) {
      console.error("tandoor2typst:", err);
      tocStatus.className = "error";
      tocStatus.textContent = `Fehler: ${err.message}`;
    } finally {
      previewButton.disabled = false;
    }
  });
}

init();
