import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from . import render
from .compiler import compile_typ
from .tandoor_client import TandoorClient

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tandoor2typst")

app = FastAPI(title="Tandoor2typst-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sanitize_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", "-", name).strip()
    return name or "recipe"


def _content_disposition(filename: str) -> str:
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "recipe.pdf"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


DEFAULT_STEPS_FONT_SIZE = 11
MIN_STEPS_FONT_SIZE = 8
# Recipes are fetched and test-compiled concurrently in the collected-book job
# (each is independent I/O + a typst subprocess) - keep this modest so a
# small NAS isn't overwhelmed with parallel typst processes.
RECIPE_WORKERS = int(os.environ.get("RECIPE_WORKERS", "4"))

TOC_MAX_FONT_SIZE = 11
TOC_MIN_FONT_SIZE = 7
TOC_FONT_STEP = 0.5


def _fit_steps_font_size(work_dir: str, recipe_files: render.RecipeFiles, test_id) -> int:
    """The preparation-steps column now defaults to a larger font than
    before, but a longer recipe can then overflow onto an otherwise near-empty
    extra page. Test-compile the recipe standalone, shrinking the steps text
    1pt at a time until it fits on one page or MIN_STEPS_FONT_SIZE is reached -
    the same approach the old xcookybooky/LaTeX backend used."""
    test_typ = f"sizetest_{test_id}.typ"
    test_pdf = f"sizetest_{test_id}.pdf"
    for size in range(DEFAULT_STEPS_FONT_SIZE, MIN_STEPS_FONT_SIZE - 1, -1):
        render.write_main(work_dir, [recipe_files.call(steps_font_size_pt=size)], filename=test_typ)
        pages = compile_typ(work_dir, test_typ, test_pdf, timeout=60)
        logger.info("Recipe %s: steps_font_size=%dpt -> %d page(s)", test_id, size, pages)
        if pages <= 1:
            return size
    return MIN_STEPS_FONT_SIZE


def _fit_toc_font_size(work_dir: str, titles: list[str]) -> float:
    """Finds the largest entries_font_size_pt for the table of contents that
    still results in the fewest possible pages - so instead of always using
    one fixed size (leaving the last page mostly empty for some collections),
    it shrinks only as much as actually needed to fill pages evenly. Uses
    bare stub headings (see render.write_toc_test) rather than compiling
    every recipe's full content just to count the TOC's own pages."""
    test_typ = "toctest.typ"
    test_pdf = "toctest.pdf"

    size = TOC_MAX_FONT_SIZE
    render.write_toc_test(work_dir, titles, size, test_typ)
    best_size = size
    best_pages = compile_typ(work_dir, test_typ, test_pdf, timeout=120)
    logger.info("TOC: entries_font_size=%.1fpt -> %d page(s)", size, best_pages)

    size -= TOC_FONT_STEP
    while size >= TOC_MIN_FONT_SIZE:
        render.write_toc_test(work_dir, titles, size, test_typ)
        pages = compile_typ(work_dir, test_typ, test_pdf, timeout=120)
        logger.info("TOC: entries_font_size=%.1fpt -> %d page(s)", size, pages)
        if pages < best_pages:
            best_size = size
            best_pages = pages
            size -= TOC_FONT_STEP
        else:
            break
    return best_size


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/recipe/{recipe_id}")
def get_recipe_pdf(recipe_id: int, payload: dict = Body(...)):
    host = payload.get("host")
    token = payload.get("token")
    if not host or not token:
        raise HTTPException(status_code=400, detail="host and token are required.")

    logger.info("Recipe %s: fetching from %s", recipe_id, host)
    client = TandoorClient(host, token)
    recipe = client.fetch_recipe(recipe_id)
    recipe_name = recipe.get("name") or f"Recipe {recipe_id}"
    image = client.download_image(recipe)

    work_dir = tempfile.mkdtemp(prefix="tandoor_pdf_")
    recipe_files = render.write_recipe_files(work_dir, recipe, "single", image)
    font_size = _fit_steps_font_size(work_dir, recipe_files, "single")
    render.write_main(work_dir, [recipe_files.call(steps_font_size_pt=font_size)])

    logger.info("Recipe %s (%s): compiling PDF", recipe_id, recipe_name)
    compile_typ(work_dir, "main.typ", "main.pdf")
    logger.info("Recipe %s (%s): done, sending PDF", recipe_id, recipe_name)
    download_name = f"{_sanitize_filename(recipe_name)}.pdf"

    return FileResponse(
        os.path.join(work_dir, "main.pdf"),
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(download_name)},
        background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
    )


# In-memory job tracking for the (potentially long-running) collected PDF
# build, so the extension can poll for progress instead of just waiting on
# one blocking request. Fine for a single-container, personal-use service.
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _set_job(job_id: str, **fields) -> None:
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {}).update(fields)


def _process_recipe(work_dir: str, client: TandoorClient, index: int, recipe_id: int, print_mode: bool) -> tuple[str, str]:
    """Fetches one recipe + its image and finds its fitting font size. Runs in
    a worker thread - safe because TandoorClient is stateless per-call and
    every file this writes (recipe_{index}.json, image_{index}.*,
    sizetest_{index}.*) is uniquely named per recipe index. Returns the
    recipe's Typst call plus its plain title (needed for the TOC font-size
    fit, see _fit_toc_font_size)."""
    recipe = client.fetch_recipe(recipe_id)
    image = client.download_image(recipe)
    recipe_files = render.write_recipe_files(work_dir, recipe, index, image)
    font_size = _fit_steps_font_size(work_dir, recipe_files, index)
    entry = recipe_files.call(steps_font_size_pt=font_size, print_mode=print_mode)
    title = recipe.get("name") or f"Recipe {recipe_id}"
    return entry, title


def _run_all_recipes_job(job_id: str, host: str, token: str, print_mode: bool = False) -> None:
    try:
        _set_job(job_id, status="fetching_list", current=0, total=0)
        logger.info("Job %s: fetching recipe list from %s", job_id, host)
        client = TandoorClient(host, token)
        recipe_ids = client.fetch_all_recipe_ids()
        if not recipe_ids:
            _set_job(job_id, status="error", detail="No recipes found on this Tandoor instance.")
            return
        logger.info("Job %s: %d recipes found", job_id, len(recipe_ids))
        _set_job(job_id, status="fetching", total=len(recipe_ids))

        work_dir = tempfile.mkdtemp(prefix="tandoor_book_")
        entries: list[str | None] = [None] * len(recipe_ids)
        titles: list[str | None] = [None] * len(recipe_ids)
        completed = 0
        with ThreadPoolExecutor(max_workers=RECIPE_WORKERS) as executor:
            futures = {
                executor.submit(_process_recipe, work_dir, client, index, recipe_id, print_mode): index
                for index, recipe_id in enumerate(recipe_ids)
            }
            for future in as_completed(futures):
                index = futures[future]
                entries[index], titles[index] = future.result()
                completed += 1
                logger.info("Job %s: recipe %d/%d done (id=%s)", job_id, completed, len(recipe_ids), recipe_ids[index])
                _set_job(job_id, current=completed)

        logger.info("Job %s: fitting table of contents font size", job_id)
        _set_job(job_id, status="compiling")
        toc_font_size = _fit_toc_font_size(work_dir, titles)
        render.write_main(work_dir, entries, include_toc=True, print_mode=print_mode, toc_font_size_pt=toc_font_size)

        logger.info("Job %s: compiling %d recipes", job_id, len(recipe_ids))
        _set_job(job_id, status="compiling")
        compile_typ(work_dir, "main.typ", "main.pdf", timeout=600)
        logger.info("Job %s: done", job_id)
        _set_job(job_id, status="done", pdf_path=os.path.join(work_dir, "main.pdf"), work_dir=work_dir)
    except HTTPException as exc:
        logger.error("Job %s failed: %s", job_id, exc.detail)
        _set_job(job_id, status="error", detail=str(exc.detail))
    except Exception as exc:  # noqa: BLE001 - report any failure back to the client
        logger.exception("Job %s failed", job_id)
        _set_job(job_id, status="error", detail=str(exc))


@app.post("/api/recipes/all/start")
def start_all_recipes_job(payload: dict = Body(...)):
    host = payload.get("host")
    token = payload.get("token")
    print_mode = bool(payload.get("print_mode", False))
    if not host or not token:
        raise HTTPException(status_code=400, detail="host and token are required.")

    job_id = uuid.uuid4().hex
    _set_job(job_id, status="queued", current=0, total=0)
    thread = threading.Thread(target=_run_all_recipes_job, args=(job_id, host, token, print_mode), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Unknown job id.")
        return {k: v for k, v in job.items() if k not in ("pdf_path", "work_dir")}


@app.get("/api/jobs/{job_id}/download")
def download_job_pdf(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job or job.get("status") != "done":
            raise HTTPException(status_code=409, detail="Job is not finished yet.")
        pdf_path = job["pdf_path"]
        work_dir = job["work_dir"]

    def cleanup():
        shutil.rmtree(work_dir, ignore_errors=True)
        with JOBS_LOCK:
            JOBS.pop(job_id, None)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition("Rezeptsammlung.pdf")},
        background=BackgroundTask(cleanup),
    )
