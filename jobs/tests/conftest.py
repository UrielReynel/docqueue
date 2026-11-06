import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfWriter
from rest_framework.test import APIClient

from jobs.models import APIKey


@pytest.fixture(autouse=True)
def tmp_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def key(db):
    return APIKey.generate("test")  # (instance, raw_key)


@pytest.fixture
def client(key):
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=key[1])
    return c


@pytest.fixture
def pdf_file():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": "Test document"})
    buf = io.BytesIO()
    writer.write(buf)
    return SimpleUploadedFile("doc.pdf", buf.getvalue(), content_type="application/pdf")


@pytest.fixture
def png_file():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "red").save(buf, format="PNG")
    return SimpleUploadedFile("pic.png", buf.getvalue(), content_type="image/png")


def text_file(content: str, name: str = "notes.txt", encoding: str = "utf-8"):
    return SimpleUploadedFile(name, content.encode(encoding), content_type="text/plain")
