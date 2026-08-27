"""Non-canonical, local-only DOCX assembly helpers for Gurubodh exports."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from gurubodh.docx.namespaces import W
from gurubodh.docx.validate import validate_docx


SECT_PR_TAG = qn("w:sectPr")


def _natural_filename_key(path: Path) -> tuple[tuple[int, int | str], ...]:
    """Return a case-insensitive natural-sort key for a DOCX filename."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", path.name)
    )


def _resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _validate_input_docx(value: str | Path, label: str) -> Path:
    path = _resolve_path(value)
    if not path.is_file():
        raise FileNotFoundError(f"{label} DOCX does not exist: {path}")
    if path.suffix.lower() != ".docx":
        raise ValueError(f"{label} must name a .docx file: {path}")
    try:
        validate_docx(path)
        Document(path)
    except Exception as exc:
        raise ValueError(f"{label} is not a valid DOCX file: {path}") from exc
    return path


def _validate_output_path(value: str | Path, overwrite: bool) -> Path:
    path = _resolve_path(value)
    if path.suffix.lower() != ".docx":
        raise ValueError(f"Output must name a .docx file: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {path.parent}")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output DOCX already exists (use --overwrite to replace it): {path}")
    return path


def discover_docx_sources(input_directory: str | Path, output_path: str | Path) -> list[Path]:
    """Discover eligible direct-child DOCX files in the required natural order."""
    directory = _resolve_path(input_directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {directory}")
    output = _resolve_path(output_path)
    sources = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".docx"
        and not path.name.startswith("~$")
        and path.resolve() != output
    ]
    sources.sort(key=_natural_filename_key)
    if not sources:
        raise ValueError(f"Input directory has no eligible DOCX files: {directory}")
    return sources


def _paragraph_style_names(document: Document) -> dict[str, str]:
    names = {}
    for style in document.styles.element.findall(qn("w:style")):
        if style.get(qn("w:type")) != "paragraph":
            continue
        name = style.find(qn("w:name"))
        style_id = style.get(qn("w:styleId"))
        if name is not None and style_id:
            names[style_id] = name.get(qn("w:val"))
    return names


def _paragraph_style_ids(document: Document) -> dict[str, str]:
    return {name: style_id for style_id, name in _paragraph_style_names(document).items()}


def _apply_destination_template(source: Document, destination: Document, copied_body: object) -> None:
    """Apply destination paragraph styles and remove source-direct run formatting."""
    source_style_names = _paragraph_style_names(source)
    destination_style_ids = _paragraph_style_ids(destination)
    for paragraph in copied_body.iter(W + "p"):
        paragraph_properties = paragraph.find(W + "pPr")
        source_style = paragraph_properties.find(W + "pStyle") if paragraph_properties is not None else None
        source_style_id = source_style.get(qn("w:val")) if source_style is not None else None
        source_style_name = source_style_names.get(source_style_id, "Normal")
        destination_style_id = destination_style_ids.get(source_style_name)
        if destination_style_id is None:
            raise ValueError(
                f"Destination DOCX does not define the required paragraph style: {source_style_name}"
            )
        if paragraph_properties is None:
            paragraph_properties = OxmlElement("w:pPr")
            paragraph.insert(0, paragraph_properties)
        for property_element in list(paragraph_properties):
            paragraph_properties.remove(property_element)
        destination_style = OxmlElement("w:pStyle")
        destination_style.set(qn("w:val"), destination_style_id)
        paragraph_properties.append(destination_style)
        for run in paragraph.iter(W + "r"):
            run_properties = run.find(W + "rPr")
            if run_properties is not None:
                run.remove(run_properties)


def _copy_document_body(source: Document, destination: Document, *, use_destination_template: bool = False) -> None:
    for child in source.element.body.iterchildren():
        if child.tag != SECT_PR_TAG:
            copied_child = deepcopy(child)
            if use_destination_template:
                _apply_destination_template(source, destination, copied_child)
            destination.element.body.insert(-1, copied_child)


def _save_docx(document: Document, path: Path) -> None:
    document.save(path)


def _publish_atomically(document: Document, output: Path) -> None:
    """Save, validate, and replace an output through a sibling temporary file."""
    with tempfile.NamedTemporaryFile(
        prefix=f".{output.name}.", suffix=".docx", dir=output.parent, delete=False
    ) as handle:
        temporary_path = Path(handle.name)
    try:
        _save_docx(document, temporary_path)
        validate_docx(temporary_path)
        os.replace(temporary_path, output)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_documents(paths: Iterable[Path]) -> list[Document]:
    try:
        return [Document(path) for path in paths]
    except Exception as exc:
        raise ValueError("Unable to read a validated DOCX input.") from exc


def run_lab_assemble_docx(
    input_directory: str | Path, output_path: str | Path, *, overwrite: bool = False
) -> dict[str, object]:
    """Assemble direct-child controlled DOCX exports into one new local DOCX."""
    sources = discover_docx_sources(input_directory, output_path)
    validated_sources = [_validate_input_docx(source, "Input") for source in sources]
    output = _validate_output_path(output_path, overwrite)
    source_documents = _load_documents(validated_sources)

    assembled = source_documents[0]
    for source in source_documents[1:]:
        assembled.add_page_break()
        _copy_document_body(source, assembled)
    _publish_atomically(assembled, output)
    return {"sources": validated_sources, "output": output}


def run_lab_append_docx(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    page_break: bool = True,
) -> dict[str, object]:
    """Append one controlled DOCX export to another via atomic replacement."""
    source = _resolve_path(source_path)
    destination = _resolve_path(destination_path)
    if source == destination:
        raise ValueError("Source and destination DOCX paths must be different.")
    source = _validate_input_docx(source, "Source")
    destination = _validate_input_docx(destination, "Destination")
    source_document, destination_document = _load_documents((source, destination))
    if page_break:
        destination_document.add_page_break()
    _copy_document_body(source_document, destination_document, use_destination_template=True)
    _publish_atomically(destination_document, destination)
    return {"source": source, "destination": destination, "page_break": page_break}
