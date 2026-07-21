// Shared helpers for reading/writing extension settings and talking to the
// backend PDF service. Loaded both by content scripts (as a classic script,
// see options.js registration) and by extension pages via <script>.

const SETTINGS_KEY = "tandoor2typst_settings";

function normalizeOrigin(url) {
  try {
    const u = new URL(url);
    return u.origin;
  } catch {
    return null;
  }
}

async function getSettings() {
  const data = await chrome.storage.local.get(SETTINGS_KEY);
  return (
    data[SETTINGS_KEY] || {
      tandoorHost: "",
      tandoorToken: "",
      backendUrl: "",
    }
  );
}

async function saveSettings(settings) {
  await chrome.storage.local.set({ [SETTINGS_KEY]: settings });
}

async function requestRecipePdf(backendUrl, host, token, recipeId) {
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/recipe/${recipeId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, token }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Server-Fehler (${response.status}): ${detail.slice(-2000)}`);
  }
  return await response.blob();
}

async function startAllRecipesJob(backendUrl, host, token, printMode) {
  const base = backendUrl.replace(/\/$/, "");
  const response = await fetch(`${base}/api/recipes/all/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, token, print_mode: !!printMode }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Server-Fehler (${response.status}): ${detail.slice(-2000)}`);
  }
  const { job_id: jobId } = await response.json();
  return jobId;
}

async function previewToc(backendUrl, host, token) {
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/toc/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, token }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Server-Fehler (${response.status}): ${detail.slice(-2000)}`);
  }
  return await response.blob();
}

async function getJobStatus(backendUrl, jobId) {
  const base = backendUrl.replace(/\/$/, "");
  const response = await fetch(`${base}/api/jobs/${jobId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Server-Fehler (${response.status}): ${detail.slice(-2000)}`);
  }
  return await response.json();
}

async function downloadJobPdf(backendUrl, jobId) {
  const base = backendUrl.replace(/\/$/, "");
  const response = await fetch(`${base}/api/jobs/${jobId}/download`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Server-Fehler (${response.status}): ${detail.slice(-2000)}`);
  }
  return await response.blob();
}

function describeJobStatus(job) {
  switch (job.status) {
    case "queued":
      return "In Warteschlange …";
    case "fetching_list":
      return "Lade Rezeptliste …";
    case "fetching":
      return `Lade Rezept ${job.current}/${job.total} …`;
    case "compiling":
      return `Kompiliere PDF (${job.total} Rezepte) …`;
    case "done":
      return "Fertig, lade PDF herunter …";
    case "error":
      return `Fehler: ${job.detail}`;
    default:
      return job.status;
  }
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
