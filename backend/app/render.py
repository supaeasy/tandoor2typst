import json
import os
import shutil

TEMPLATE_SRC = os.path.join(os.path.dirname(__file__), "..", "templates", "recipe-template.typ")


def _typst_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def ensure_template_copied(work_dir: str) -> None:
    shutil.copyfile(TEMPLATE_SRC, os.path.join(work_dir, "template.typ"))


def write_recipe_entry(
    work_dir: str,
    recipe: dict,
    index: int,
    image: tuple[bytes, str] | None,
    page_number: bool,
) -> str:
    """Writes recipe_{index}.json (and the image, if any) into work_dir and
    returns the Typst call that renders it."""
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

    page_number_arg = "true" if page_number else "false"
    return (
        f"#recipe_from_json(json({_typst_string_literal(json_filename)}), "
        f"image_path: {image_arg}, page_number: {page_number_arg})\n"
    )


def write_main(work_dir: str, entries: list[str]) -> None:
    ensure_template_copied(work_dir)
    body = '#import "template.typ": recipe_from_json\n' + "#pagebreak()\n".join(entries)
    with open(os.path.join(work_dir, "main.typ"), "w", encoding="utf-8") as f:
        f.write(body)
