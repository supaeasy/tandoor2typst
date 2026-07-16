// MV3 service worker. Owns the "download all recipes" job so it keeps
// running (polling the backend, then triggering the download) even if the
// popup gets closed - popup UIs are torn down on blur, but this script isn't.
importScripts("settings.js");

const STATE_KEY = "tandoor2typst_job_state";
const IDLE_STATUSES = new Set(["idle", "finished", "error"]);

async function setState(state) {
  await chrome.storage.session.set({ [STATE_KEY]: state });
}

async function getState() {
  const data = await chrome.storage.session.get(STATE_KEY);
  return data[STATE_KEY] || { status: "idle" };
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

async function runAllRecipesJob(settings, printMode) {
  await setState({ status: "starting", text: "Starte …" });
  try {
    const jobId = await startAllRecipesJob(
      settings.backendUrl,
      settings.tandoorHost,
      settings.tandoorToken,
      printMode
    );
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const job = await getJobStatus(settings.backendUrl, jobId);
      await setState({ ...job, text: describeJobStatus(job) });

      if (job.status === "done") {
        const blob = await downloadJobPdf(settings.backendUrl, jobId);
        const dataUrl = await blobToDataUrl(blob);
        const filename = printMode ? "Rezeptsammlung-Druck.pdf" : "Rezeptsammlung.pdf";
        await chrome.downloads.download({ url: dataUrl, filename, saveAs: false });
        await setState({ status: "finished", text: "Fertig! PDF wurde heruntergeladen." });
        return;
      }
      if (job.status === "error") {
        await setState({ status: "error", text: `Fehler: ${job.detail}` });
        return;
      }
    }
  } catch (err) {
    console.error("tandoor2typst:", err);
    await setState({ status: "error", text: `Fehler: ${err.message}` });
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "start-all-recipes") {
    getState().then((state) => {
      if (!IDLE_STATUSES.has(state.status)) {
        sendResponse({ started: false, reason: "already-running" });
        return;
      }
      runAllRecipesJob(message.settings, !!message.printMode);
      sendResponse({ started: true });
    });
    return true;
  }
  if (message?.type === "get-job-state") {
    getState().then((state) => sendResponse(state));
    return true;
  }
  return false;
});
