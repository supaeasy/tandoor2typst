const STATE_KEY = "tandoor2typst_job_state";
const IDLE_STATUSES = new Set(["idle", "finished", "error", undefined]);

function renderState(state) {
  const button = document.getElementById("downloadAll");
  const status = document.getElementById("status");
  status.textContent = state?.text || "";
  status.className = state?.status === "error" ? "error" : state?.status === "finished" ? "success" : "";
  button.disabled = !IDLE_STATUSES.has(state?.status);
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

  document.getElementById("downloadAll").addEventListener("click", async () => {
    renderState({ status: "starting", text: "Starte …" });
    const response = await chrome.runtime.sendMessage({ type: "start-all-recipes", settings });
    if (!response?.started) {
      renderState({ status: "error", text: "Es läuft bereits ein Sammel-PDF-Job." });
    }
  });
}

init();
