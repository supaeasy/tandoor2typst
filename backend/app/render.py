import json
import os
import shutil
from fractions import Fraction

TEMPLATE_SRC = os.path.join(os.path.dirname(__file__), "..", "templates", "recipe-template.typ")


def _typst_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def ensure_template_copied(work_dir: str) -> None:
    shutil.copyfile(TEMPLATE_SRC, os.path.join(work_dir, "template.typ"))


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


class RecipeFiles:
    """Paths for a recipe already written to work_dir, reusable across several
    test compiles at different font sizes (see main._fit_steps_font_size)
    without re-fetching the recipe or re-writing its JSON/image each time."""

    def __init__(self, json_filename: str, image_arg: str):
        self.json_filename = json_filename
        self.image_arg = image_arg

    def call(self, page_number: bool, steps_font_size_pt: float) -> str:
        page_number_arg = "true" if page_number else "false"
        return (
            f"#recipe_from_json(json({_typst_string_literal(self.json_filename)}), "
            f"image_path: {self.image_arg}, page_number: {page_number_arg}, "
            f"steps_font_size_pt: {steps_font_size_pt}pt)\n"
        )


def write_recipe_files(
    work_dir: str,
    recipe: dict,
    index,
    image: tuple[bytes, str] | None,
) -> RecipeFiles:
    """Writes recipe_{index}.json (and the image, if any) into work_dir."""
    _annotate_amounts(recipe)
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

    return RecipeFiles(json_filename, image_arg)


def write_main(work_dir: str, entries: list[str], filename: str = "main.typ") -> None:
    ensure_template_copied(work_dir)
    body = '#import "template.typ": recipe_from_json\n' + "#pagebreak()\n".join(entries)
    with open(os.path.join(work_dir, filename), "w", encoding="utf-8") as f:
        f.write(body)
