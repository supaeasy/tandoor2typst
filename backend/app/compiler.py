import os
import subprocess

from pypdf import PdfReader

FONT_PATH = "/usr/share/fonts/truetype/tandoor2typst"


def compile_typ(work_dir: str, typ_filename: str, pdf_filename: str, timeout: int = 120) -> int:
    """Compile a .typ file to PDF via the typst CLI and return the resulting
    page count. Raises RuntimeError with the compiler's stderr output (Typst's
    diagnostics are human-readable and already point at the offending line)
    if compilation fails."""
    try:
        result = subprocess.run(
            ["typst", "compile", "--font-path", FONT_PATH, typ_filename, pdf_filename],
            cwd=work_dir,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Typst-Kompilierung hat das Zeitlimit ({timeout}s) überschritten.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Typst-Kompilierung fehlgeschlagen:\n{detail[-4000:]}")

    return len(PdfReader(os.path.join(work_dir, pdf_filename)).pages)
