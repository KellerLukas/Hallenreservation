from typing import Callable, Protocol, cast

import fitz


class _PdfBytes(Protocol):
    def tobytes(self) -> bytes: ...


class _PdfInsert(Protocol):
    def insert_pdf(
        self,
        docsrc: fitz.Document,
        *,
        from_page: int = 0,
        to_page: int = -1,
    ) -> None: ...


class _PdfSave(Protocol):
    def save(self, filename: str) -> None: ...


def _open_pdf_from_bytes(content: bytes) -> fitz.Document:
    open_pdf = cast(Callable[..., fitz.Document], fitz.open)
    return open_pdf(stream=content, filetype="pdf")


def _open_pdf_from_path(file_path: str) -> fitz.Document:
    open_pdf = cast(Callable[..., fitz.Document], fitz.open)
    return open_pdf(file_path)


def _open_empty_pdf() -> fitz.Document:
    open_pdf = cast(Callable[..., fitz.Document], fitz.open)
    return open_pdf()


def _pdf_tobytes(pdf_doc: fitz.Document) -> bytes:
    return cast(_PdfBytes, pdf_doc).tobytes()


def _insert_pdf(
    target: fitz.Document,
    source: fitz.Document,
    *,
    from_page: int = 0,
    to_page: int = -1,
) -> None:
    cast(_PdfInsert, target).insert_pdf(
        source,
        from_page=from_page,
        to_page=to_page,
    )


def _save_pdf(pdf_doc: fitz.Document, file_path: str) -> None:
    cast(_PdfSave, pdf_doc).save(file_path)
