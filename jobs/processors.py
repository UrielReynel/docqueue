"""File processors. Each takes an open binary file and returns a JSON-able dict.

Adding a new kind means: a detector branch in `detect_kind` and a function in
`PROCESSORS`. The worker does not need to change.
"""

import unicodedata
from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
PREVIEW_CHARS = 500

# Byte sequences that show up when UTF-8 text was decoded as Latin-1/Windows-1252
# (e.g. "é" -> "Ã©", "’" -> "â€™"). Finding them usually means a broken pipeline.
MOJIBAKE_MARKERS = ("Ã¡", "Ã©", "Ã­", "Ã³", "Ãº", "Ã±", "Ã‘", "â€™", "â€œ", "â€", "Â¿", "Â¡")


class UnsupportedFile(ValueError):
    pass


def detect_kind(filename: str, head: bytes) -> str:
    """Decide the file kind from its first bytes, falling back to the extension."""
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8")) or head[8:12] == b"WEBP":
        return "image"
    if Path(filename).suffix.lower() in TEXT_EXTENSIONS and b"\x00" not in head:
        return "text"
    raise UnsupportedFile(f"Unsupported file type: {filename!r}. Send a PDF, an image or a text file.")


def text_quality(text: str) -> dict:
    """Signals of encoding damage in extracted text."""
    replacement_chars = text.count("�")
    mojibake_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    return {
        "replacement_chars": replacement_chars,
        "mojibake_hits": mojibake_hits,
        "looks_broken": replacement_chars > 0 or mojibake_hits > 0,
    }


def _text_summary(text: str) -> dict:
    text = unicodedata.normalize("NFC", text)
    return {
        "chars": len(text),
        "words": len(text.split()),
        "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        "preview": text[:PREVIEW_CHARS],
        "quality": text_quality(text),
    }


def process_pdf(fh: BinaryIO) -> dict:
    reader = PdfReader(fh)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    meta = reader.metadata or {}
    return {
        "pages": len(reader.pages),
        "title": meta.get("/Title"),
        "author": meta.get("/Author"),
        **_text_summary(text),
    }


def process_image(fh: BinaryIO) -> dict:
    try:
        with Image.open(fh) as img:
            img.verify()  # detects truncated or corrupt files
        fh.seek(0)
        with Image.open(fh) as img:
            return {
                "format": img.format,
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "has_exif": bool(img.getexif()),
            }
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Corrupt or unreadable image: {exc}") from exc


def process_text(fh: BinaryIO) -> dict:
    raw = fh.read()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return {"encoding": encoding, **_text_summary(text)}


PROCESSORS = {
    "pdf": process_pdf,
    "image": process_image,
    "text": process_text,
}
