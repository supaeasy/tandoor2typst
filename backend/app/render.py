import json
import os
import shutil
import threading
from fractions import Fraction

TEMPLATE_SRC = os.path.join(os.path.dirname(__file__), "..", "templates", "recipe-template.typ")


def _typst_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def ensure_template_copied(work_dir: str) -> None:
    """Idempotent and safe to call from several threads sharing the same
    work_dir at once (the collected-book job processes recipes concurrently,
    and each one calls this via write_main/write_toc_test): skips the copy if
    the file is already there, and even when several threads race past that
    check simultaneously, writes to a temp file first and atomically renames
    it into place - so a reader can never see a half-written template.typ
    (which surfaced as "unresolved import" errors under concurrency)."""
    dest = os.path.join(work_dir, "template.typ")
    if os.path.exists(dest):
        return
    tmp = dest + f".tmp-{os.getpid()}-{threading.get_ident()}"
    shutil.copyfile(TEMPLATE_SRC, tmp)
    os.replace(tmp, dest)


def _amount_to_fraction_parts(value) -> dict:
    """Splits a decimal amount into whole/numerator/denominator parts so the
    Typst template can render it as a nicefrac-style small fraction (e.g.
    0.25 -> whole=0, num=1, den=4) instead of a raw decimal."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return {"whole": 0, "num": 0, "den": 1}
    if value < 0:
        value = 0.0
    frac = Fraction(value).limit_denominator(8)
    whole, remainder = divmod(frac.numerator, frac.denominator)
    return {"whole": whole, "num": remainder, "den": frac.denominator}


def _annotate_amounts(recipe: dict) -> None:
    for step in recipe.get("steps") or []:
        for ingredient in step.get("ingredients") or []:
            ingredient["amount_frac"] = _amount_to_fraction_parts(ingredient.get("amount", 0))


def _format_nutrition_value(value: float, unit: str) -> str:
    # Whole numbers for kcal and anything >= 10 g; one decimal below that so
    # small values (e.g. 2.5 g fat) don't collapse to a misleading 3 or 2.
    if unit == "kcal" or value >= 10:
        return str(int(value + 0.5))
    return f"{value:.1f}"


def _annotate_nutrition(recipe: dict) -> None:
    """Derives a per-serving nutrition summary from Tandoor's computed
    food_properties (type id -> {name, unit, order, total_value, missing_value};
    total_value covers the whole recipe, so it's divided by servings). The
    manual `nutrition` field is empty in practice and not used. Stored as
    recipe["nutrition_display"], or None if there's nothing worth showing."""
    properties = recipe.get("food_properties") or {}
    try:
        servings = float(recipe.get("servings") or 1)
    except (TypeError, ValueError):
        servings = 1.0
    if servings <= 0:
        servings = 1.0

    items = []
    incomplete = False
    for prop in sorted(properties.values(), key=lambda p: (p.get("order", 0), p.get("id", 0))):
        total = prop.get("total_value")
        if total is None:
            continue
        unit = prop.get("unit") or ""
        items.append({
            "name": prop.get("name") or "",
            "value": _format_nutrition_value(float(total) / servings, unit),
            "unit": unit,
            "raw": float(total),
        })
        incomplete = incomplete or bool(prop.get("missing_value"))

    if not any(item["raw"] > 0 for item in items):
        recipe["nutrition_display"] = None
        return
    recipe["nutrition_display"] = {
        "items": [{k: v for k, v in item.items() if k != "raw"} for item in items],
        "incomplete": incomplete,
    }


class RecipeFiles:
    """Paths/ids for a recipe already written to work_dir, reusable across
    several test compiles at different font sizes (see main._fit_steps_font_size)
    without re-fetching the recipe or re-writing its JSON/image each time."""

    def __init__(self, json_filename: str, image_arg: str, id_prefix: str):
        self.json_filename = json_filename
        self.image_arg = image_arg
        self.id_prefix = id_prefix

    def call(self, steps_font_size_pt: float, print_mode: bool = False) -> str:
        print_mode_arg = "true" if print_mode else "false"
        return (
            f"#recipe_from_json(json({_typst_string_literal(self.json_filename)}), "
            f"image_path: {self.image_arg}, "
            f"id_prefix: {_typst_string_literal(self.id_prefix)}, "
            f"steps_font_size_pt: {steps_font_size_pt}pt, print_mode: {print_mode_arg})\n"
        )


def write_recipe_files(
    work_dir: str,
    recipe: dict,
    index,
    image: tuple[bytes, str] | None,
) -> RecipeFiles:
    """Writes recipe_{index}.json (and the image, if any) into work_dir."""
    _annotate_amounts(recipe)
    _annotate_nutrition(recipe)
    json_filename = f"recipe_{index}.json"
    with open(os.path.join(work_dir, json_filename), "w", encoding="utf-8") as f:
        json.dump(recipe, f)

    image_arg = "none"
    if image is not None:
        image_bytes, extension = image
        image_filename = f"image_{index}.{extension}"
        with open(os.path.join(work_dir, image_filename), "wb") as f:
            f.write(image_bytes)
        image_arg = _typst_string_literal(image_filename)

    # id_prefix keeps footnote label names unique across recipes when several
    # end up in the same compiled document (the collected cookbook PDF).
    return RecipeFiles(json_filename, image_arg, id_prefix=f"r{index}")


def write_main(
    work_dir: str,
    entries: list[str],
    filename: str = "main.typ",
    include_toc: bool = False,
    print_mode: bool = False,
    toc_font_size_pt: float = 11,
) -> None:
    ensure_template_copied(work_dir)
    if include_toc:
        print_mode_arg = "true" if print_mode else "false"
        header = (
            '#import "template.typ": recipe_from_json, toc_page\n'
            f"#toc_page(print_mode: {print_mode_arg}, entries_font_size_pt: {toc_font_size_pt}pt)\n"
            "#pagebreak()\n#counter(page).update(1)\n"
        )
    else:
        header = '#import "template.typ": recipe_from_json\n'
    body = header + "#pagebreak()\n".join(entries)
    with open(os.path.join(work_dir, filename), "w", encoding="utf-8") as f:
        f.write(body)


def _write_stub_headings(parts: list[str], titles: list[str]) -> None:
    # Tiny and tightly packed so these always take as few pages as possible -
    # keeps the "how many pages do the stubs alone need" measurement small
    # and stable regardless of how many recipes there are.
    parts.append("#set text(size: 4pt)\n")
    for index, title in enumerate(titles):
        parts.append(f"#let title{index} = {_typst_string_literal(title)}\n")
        parts.append(f"#heading(level: 1)[#title{index}]\n")


def write_toc_test(work_dir: str, titles: list[str], entries_font_size_pt: float, filename: str) -> None:
    """Writes a lightweight stand-in document: the real toc_page() (so its
    page count is accurate) followed by bare, body-less headings for each
    recipe title - #outline() only needs the headings to exist somewhere to
    list them, so this avoids compiling every recipe's full content just to
    measure how many pages the table of contents itself needs. The compiled
    page count includes both the TOC and these stub pages - see
    write_stub_only() for measuring the stub pages alone so they can be
    subtracted back out."""
    ensure_template_copied(work_dir)
    parts = [
        '#import "template.typ": toc_page\n',
        f"#toc_page(entries_font_size_pt: {entries_font_size_pt}pt)\n#pagebreak()\n",
    ]
    _write_stub_headings(parts, titles)
    with open(os.path.join(work_dir, filename), "w", encoding="utf-8") as f:
        f.write("".join(parts))


def write_stub_only(work_dir: str, titles: list[str], filename: str) -> None:
    """The same bare stub headings as write_toc_test(), without toc_page() -
    used once to measure how many pages the stubs alone take up, so that
    count can be subtracted from a write_toc_test() total to get the TOC's
    own page count (see main._fit_toc_font_size)."""
    parts: list[str] = []
    _write_stub_headings(parts, titles)
    with open(os.path.join(work_dir, filename), "w", encoding="utf-8") as f:
        f.write("".join(parts))
