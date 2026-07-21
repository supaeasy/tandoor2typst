import logging
import os
import random
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
from .compiler import compile_typ, truncate_pdf
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

TOC_DEFAULT_FONT_SIZE = 11
TOC_FONT_STEP = 0.5
TOC_MAX_GROWTH = 10  # generous - the page-count guard below is what actually bounds this


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


def _fit_toc_font_size(
    work_dir: str, titles: list[str], test_typ: str = "toctest.typ", test_pdf: str = "toctest.pdf"
) -> tuple[float, int]:
    """Starts at TOC_DEFAULT_FONT_SIZE and measures how many pages that needs,
    then grows the size (and, via the template, paragraph spacing) in generous
    steps as long as that doesn't push the table of contents onto an
    additional page - so the default page count is filled as fully as
    possible instead of shrinking to search for fewer pages (which doesn't
    help when the default already leaves the last page half-empty). Uses bare
    stub headings (see render.write_toc_test) rather than compiling every
    recipe's full content just to count the TOC's own pages - their own page
    count is measured once (render.write_stub_only) and subtracted back out,
    since it's otherwise baked into every measurement here. Returns
    (font_size_pt, toc_page_count_at_that_size); the file left behind at
    test_typ/test_pdf is re-rendered at the winning size before returning, so
    it always matches what's reported (earlier versions left whatever size
    was tested last - typically the rejected, oversized one - on disk)."""
    render.write_stub_only(work_dir, titles, "stubonly.typ")
    stub_pages = compile_typ(work_dir, "stubonly.typ", "stubonly.pdf", timeout=120)
    logger.info("TOC: %d titles -> stub headings alone need %d page(s)", len(titles), stub_pages)

    def toc_pages_at(size: float) -> int:
        render.write_toc_test(work_dir, titles, size, test_typ)
        total_pages = compile_typ(work_dir, test_typ, test_pdf, timeout=120)
        pages = total_pages - stub_pages
        logger.info("TOC: entries_font_size=%.1fpt -> %d page(s)", size, pages)
        return pages

    default_pages = toc_pages_at(TOC_DEFAULT_FONT_SIZE)
    best_size = TOC_DEFAULT_FONT_SIZE
    best_pages = default_pages
    size = TOC_DEFAULT_FONT_SIZE
    max_size = TOC_DEFAULT_FONT_SIZE + TOC_MAX_GROWTH
    while size + TOC_FONT_STEP <= max_size:
        size += TOC_FONT_STEP
        pages = toc_pages_at(size)
        if pages > default_pages:
            break
        best_size = size
        best_pages = pages

    # Re-render at the winning size so the file on disk actually matches it -
    # the loop's last iteration is often the rejected, oversized attempt.
    render.write_toc_test(work_dir, titles, best_size, test_typ)
    compile_typ(work_dir, test_typ, test_pdf, timeout=120)
    return best_size, best_pages


_SIM_PREFIXES = [
    "Klassische", "Schnelle", "Cremige", "Herzhafte", "Bunte", "Würzige", "Feine",
    "Rustikale", "Sommerliche", "Winterliche", "Knusprige", "Hausgemachte", "",
    "", "", "",  # weighted towards no prefix, like real recipe names usually are
]
_SIM_INGREDIENTS = [
    "Kartoffel", "Tomaten", "Pilz", "Poulet", "Rind", "Lachs", "Kürbis", "Spinat",
    "Linsen", "Käse", "Schoko", "Zitronen", "Ingwer", "Randen", "Zucchetti", "Peperoni",
    "Randensalat", "Quark", "Schafkäse", "Sellerie", "Lauch", "Karotten", "Aprikosen",
]
_SIM_DISHES = [
    "Suppe", "Auflauf", "Salat", "Pfanne", "Braten", "Gratin", "Eintopf", "Kuchen",
    "Torte", "Ragout", "Risotto", "Curry", "Wähe", "Nudeln", "Geschnetzeltes",
    "Röllchen", "Plätzchen", "Muffins", "Strudel", "Bowl",
]


def _simulate_titles(count: int, seed: int = 42) -> list[str]:
    """Generates plausible, length-varied recipe titles (short like "Pancakes"
    up to longer combos like real ones such as "Nudelsalat á la Omi
    Preissler") for testing the TOC auto-fit without needing a real Tandoor
    instance - lets the fit be validated across different collection sizes
    on demand. A fixed seed keeps repeated tests at the same count
    comparable."""
    rng = random.Random(seed)
    titles = []
    for i in range(count):
        parts = []
        prefix = rng.choice(_SIM_PREFIXES)
        if prefix:
            parts.append(prefix)
        parts.append(rng.choice(_SIM_INGREDIENTS))
        if rng.random() < 0.35:
            parts.append("mit " + rng.choice(_SIM_INGREDIENTS))
        parts.append(rng.choice(_SIM_DISHES))
        titles.append(f"{' '.join(parts)} {i + 1}")
    return titles


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/toc/preview")
def preview_toc(payload: dict = Body(...)):
    """Fast, synchronous endpoint for testing the table-of-contents layout
    alone (no recipe images/steps, no font-fit-per-recipe). By default fetches
    real recipe titles (needs host+token); pass "simulate_count" instead to
    generate that many plausible fake titles and skip Tandoor entirely - lets
    the auto-fit be validated across arbitrary collection sizes without
    needing real data for each one. Also by default runs the same auto-fit as
    the real collected-book job; pass "font_size_pt" to render at an exact
    size instead (skips the fit loop - useful for quickly hand-testing what
    size/page-count you actually want). Returns only the real cover+TOC pages
    - the bare heading stand-ins #outline() needs to find titles are compiled
    but trimmed off before returning."""
    manual_size = payload.get("font_size_pt")
    simulate_count = payload.get("simulate_count")

    if simulate_count:
        titles = _simulate_titles(int(simulate_count))
        logger.info("TOC preview: simulating %d titles", len(titles))
    else:
        host = payload.get("host")
        token = payload.get("token")
        if not host or not token:
            raise HTTPException(status_code=400, detail="host and token are required.")
        logger.info("TOC preview: fetching recipe titles from %s", host)
        client = TandoorClient(host, token)
        titles = client.fetch_all_recipe_titles()
        if not titles:
            raise HTTPException(status_code=502, detail="No recipes found on this Tandoor instance.")

    work_dir = tempfile.mkdtemp(prefix="tandoor_toc_")
    if manual_size is not None:
        toc_font_size = float(manual_size)
        render.write_stub_only(work_dir, titles, "stubonly.typ")
        stub_pages = compile_typ(work_dir, "stubonly.typ", "stubonly.pdf", timeout=120)
        render.write_toc_test(work_dir, titles, toc_font_size, "preview.typ")
        toc_pages = compile_typ(work_dir, "preview.typ", "preview.pdf", timeout=120) - stub_pages
        logger.info("TOC preview: manual entries_font_size=%.1fpt for %d titles -> %d page(s)", toc_font_size, len(titles), toc_pages)
    else:
        toc_font_size, toc_pages = _fit_toc_font_size(work_dir, titles, test_typ="preview.typ", test_pdf="preview.pdf")
        logger.info("TOC preview: auto-fit entries_font_size=%.1fpt for %d titles -> %d page(s)", toc_font_size, len(titles), toc_pages)

    truncate_pdf(work_dir, "preview.pdf", toc_pages)

    return FileResponse(
        os.path.join(work_dir, "preview.pdf"),
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition("Inhaltsverzeichnis-Test.pdf")},
        background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
    )


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
        toc_font_size, _toc_pages = _fit_toc_font_size(work_dir, titles)
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
