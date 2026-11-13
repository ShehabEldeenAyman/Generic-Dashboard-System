"""Generic, run-scoped semantic pipeline operations.

Every function receives explicit input and output paths. Uploaded data is
materialised inside an isolated run directory, so no stage depends on the
repository's historical example data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time as time_type
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Sequence
from urllib.parse import quote
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from rdflib import Graph

from SHACL import shacl_engine
from triple_store_ingestion import ingest


ROOT_DIR = Path(__file__).resolve().parents[1]
RML_MAPPER_JAR = Path(
    os.getenv("RML_MAPPER_JAR", str(ROOT_DIR / "pipeline" / "rmlmapper.jar"))
).expanduser().resolve()
DEFAULT_GRAPH_BASE = os.getenv("FUSEKI_GRAPH_BASE", "https://example.org/graphs/")
COMMAND_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_COMMAND_TIMEOUT", "300"))
SUPPORTED_TABULAR_EXTENSIONS = {".csv", ".xlsx"}


class PipelineError(RuntimeError):
    """An actionable stage error safe to display in the dashboard."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


@dataclass
class CommandResult:
    stdout: str
    stderr: str

    @property
    def log(self) -> str:
        return "\n".join(part.strip() for part in (self.stdout, self.stderr) if part.strip())


def run_command(command: Sequence[str], *, cwd: Path, label: str) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise PipelineError(f"{label} cannot start because an executable is missing: {error}") from error
    except subprocess.TimeoutExpired as error:
        output = "\n".join(str(item) for item in (error.stdout, error.stderr) if item)
        raise PipelineError(
            f"{label} exceeded the {COMMAND_TIMEOUT_SECONDS}-second execution limit.", output
        ) from error

    result = CommandResult(completed.stdout or "", completed.stderr or "")
    if completed.returncode != 0:
        raise PipelineError(
            f"{label} failed with exit code {completed.returncode}.",
            result.log or "The process did not provide an error message.",
        )
    return result


def safe_filename(filename: str | None) -> str:
    original = Path(filename or "dataset.csv").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", original).strip("._")
    if not cleaned:
        cleaned = "dataset.csv"
    if Path(cleaned).suffix.lower() not in SUPPORTED_TABULAR_EXTENSIONS:
        raise PipelineError("Please upload a .csv or .xlsx file.")
    return cleaned


def csv_preview(path: str | Path, limit: int = 30) -> dict[str, Any]:
    source = Path(path)
    sample = source.read_bytes()[:65_536]
    if not sample:
        raise PipelineError("The uploaded CSV file is empty.")

    encoding = "utf-8-sig"
    try:
        decoded_sample = sample.decode(encoding)
    except UnicodeDecodeError:
        encoding = "latin-1"
        decoded_sample = sample.decode(encoding)

    try:
        dialect = csv.Sniffer().sniff(decoded_sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    rows: list[dict[str, str]] = []
    total_rows = 0
    try:
        with source.open("r", encoding=encoding, errors="strict", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            columns = [str(column).strip() for column in (reader.fieldnames or []) if column is not None]
            if not columns:
                raise PipelineError("No CSV header row could be detected.")
            for raw_row in reader:
                total_rows += 1
                if len(rows) < limit:
                    rows.append({column: "" if raw_row.get(column) is None else str(raw_row[column]) for column in columns})
    except UnicodeDecodeError as error:
        raise PipelineError(f"The CSV could not be decoded as {encoding}: {error}") from error
    except csv.Error as error:
        raise PipelineError(f"The CSV could not be parsed: {error}") from error

    return {
        "format": "csv",
        "columns": columns,
        "rows": rows,
        "preview_row_count": len(rows),
        "total_rows": total_rows,
        "delimiter": "tab" if delimiter == "\t" else delimiter,
        "encoding": encoding,
        "size": source.stat().st_size,
    }


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return str(value)


def _unique_columns(values: Sequence[Any]) -> list[str]:
    columns: list[str] = []
    used: dict[str, int] = {}
    for index, value in enumerate(values, start=1):
        base = _cell_text(value).strip() or f"column_{index}"
        count = used.get(base, 0) + 1
        used[base] = count
        columns.append(base if count == 1 else f"{base}_{count}")
    return columns


@dataclass(frozen=True)
class XlsxColumn:
    """One output CSV column derived from one or more worksheet columns."""

    name: str
    source_indexes: tuple[int, ...]
    kind: str = "value"


@dataclass(frozen=True)
class XlsxTablePlan:
    """Detected tabular layout for an XLSX worksheet."""

    columns: tuple[XlsxColumn, ...]
    data_start_row: int
    header_row_count: int
    source_column_count: int


def _is_data_value(value: Any) -> bool:
    return value is not None and not isinstance(value, str) and isinstance(
        value, (date, time_type, int, float, bool)
    )


def _date_part(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) and not isinstance(value, time_type):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            try:
                return date.fromisoformat(text)
            except ValueError:
                return None
    return None


def _time_part(value: Any) -> time_type | None:
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time_type):
        return value
    if isinstance(value, str):
        try:
            return time_type.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _is_date_value(value: Any) -> bool:
    return _date_part(value) is not None


def _is_time_value(value: Any) -> bool:
    return _time_part(value) is not None


def _last_populated_index(row: Sequence[Any]) -> int:
    return max(
        (index for index, value in enumerate(row) if _cell_text(value).strip()),
        default=-1,
    )


def _xlsx_table_plan(worksheet: Any, sample_size: int = 20) -> XlsxTablePlan:
    sampled_rows: list[tuple[int, tuple[Any, ...]]] = []
    for row_number, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
        if not any(_cell_text(value).strip() for value in row):
            continue
        sampled_rows.append((row_number, row))
        if len(sampled_rows) >= sample_size:
            break

    if not sampled_rows:
        raise PipelineError(f"Worksheet '{worksheet.title}' is empty.")

    first_row_number = sampled_rows[0][0]
    data_sample_index: int | None = None
    for index, (_, row) in enumerate(sampled_rows[1:], start=1):
        populated = [value for value in row if _cell_text(value).strip()]
        data_values = sum(_is_data_value(value) for value in populated)
        if populated and data_values and data_values / len(populated) >= 0.5:
            data_sample_index = index
            break

    if data_sample_index is None:
        header_rows = [sampled_rows[0][1]]
        data_start_row = first_row_number + 1
        first_data_row: tuple[Any, ...] = ()
    else:
        header_rows = [row for _, row in sampled_rows[:data_sample_index]]
        data_start_row = sampled_rows[data_sample_index][0]
        first_data_row = sampled_rows[data_sample_index][1]

    source_column_count = max(
        (_last_populated_index(row) + 1 for _, row in sampled_rows),
        default=0,
    )
    raw_columns: list[XlsxColumn] = []
    source_index = 0
    while source_index < source_column_count:
        if (
            source_index + 1 < source_column_count
            and source_index < len(first_data_row)
            and source_index + 1 < len(first_data_row)
            and _is_date_value(first_data_row[source_index])
            and _is_time_value(first_data_row[source_index + 1])
        ):
            raw_columns.append(
                XlsxColumn("DateTime", (source_index, source_index + 1), "datetime")
            )
            source_index += 2
            continue

        fragments: list[str] = []
        for header_row in header_rows:
            if source_index >= len(header_row):
                continue
            fragment = _cell_text(header_row[source_index]).strip()
            if fragment and fragment not in fragments:
                fragments.append(fragment)
        raw_columns.append(
            XlsxColumn(" | ".join(fragments) or f"column_{source_index + 1}", (source_index,))
        )
        source_index += 1

    unique_names = _unique_columns([column.name for column in raw_columns])
    columns = tuple(
        XlsxColumn(name, column.source_indexes, column.kind)
        for name, column in zip(unique_names, raw_columns, strict=True)
    )
    return XlsxTablePlan(
        columns=columns,
        data_start_row=data_start_row,
        header_row_count=len(header_rows),
        source_column_count=source_column_count,
    )


def _combined_datetime(date_value: Any, time_value: Any) -> str:
    parsed_date = _date_part(date_value)
    parsed_time = _time_part(time_value)
    if parsed_date is None or parsed_time is None:
        return ""
    return datetime.combine(parsed_date, parsed_time).isoformat()


def _xlsx_row_values(row: Sequence[Any], plan: XlsxTablePlan) -> list[str]:
    values: list[str] = []
    for column in plan.columns:
        if column.kind == "datetime":
            date_index, time_index = column.source_indexes
            date_value = row[date_index] if date_index < len(row) else None
            time_value = row[time_index] if time_index < len(row) else None
            values.append(_combined_datetime(date_value, time_value))
        else:
            source_index = column.source_indexes[0]
            values.append(_cell_text(row[source_index] if source_index < len(row) else None))
    return values


def xlsx_preview(path: str | Path, limit: int = 30) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        raise PipelineError("The uploaded XLSX file is empty.")

    try:
        workbook = load_workbook(source, read_only=True, data_only=True)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as error:
        raise PipelineError(f"The XLSX workbook could not be opened: {error}") from error

    try:
        worksheets = workbook.worksheets
        if not worksheets:
            raise PipelineError("The XLSX workbook does not contain a worksheet.")
        worksheet = workbook.active if workbook.active in worksheets else worksheets[0]
        plan = _xlsx_table_plan(worksheet)
        columns = [column.name for column in plan.columns]
        rows: list[dict[str, str]] = []
        total_rows = 0
        for raw_row in worksheet.iter_rows(min_row=plan.data_start_row, values_only=True):
            row_values = _xlsx_row_values(raw_row, plan)
            if not any(value.strip() for value in row_values):
                continue
            total_rows += 1
            if len(rows) < limit:
                rows.append(dict(zip(columns, row_values, strict=True)))

        return {
            "format": "xlsx",
            "columns": columns,
            "rows": rows,
            "preview_row_count": len(rows),
            "total_rows": total_rows,
            "sheet_name": worksheet.title,
            "sheet_names": workbook.sheetnames,
            "header_row_count": plan.header_row_count,
            "data_start_row": plan.data_start_row,
            "size": source.stat().st_size,
        }
    finally:
        workbook.close()


def tabular_preview(path: str | Path, limit: int = 30) -> dict[str, Any]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return csv_preview(source, limit)
    if source.suffix.lower() == ".xlsx":
        return xlsx_preview(source, limit)
    raise PipelineError("Please upload a .csv or .xlsx file.")


def xlsx_to_csv(
    source_path: str | Path,
    destination_path: str | Path,
    preview: dict[str, Any],
) -> Path:
    source = Path(source_path)
    destination = Path(destination_path)
    try:
        workbook = load_workbook(source, read_only=True, data_only=True)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as error:
        raise PipelineError(f"The XLSX workbook could not be opened: {error}") from error

    try:
        worksheet = workbook[preview["sheet_name"]]
        plan = _xlsx_table_plan(worksheet)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            columns = [column.name for column in plan.columns]
            if columns != preview["columns"]:
                raise PipelineError("The XLSX worksheet structure changed while it was being parsed.")
            writer.writerow(columns)
            for raw_row in worksheet.iter_rows(min_row=plan.data_start_row, values_only=True):
                row_values = _xlsx_row_values(raw_row, plan)
                if any(value.strip() for value in row_values):
                    writer.writerow(row_values)
    finally:
        workbook.close()
    return destination


def parse_turtle(text: str, *, label: str) -> int:
    try:
        graph = Graph().parse(data=text, format="turtle", publicID="https://example.org/input/")
    except Exception as error:
        raise PipelineError(f"{label} is not valid Turtle: {error}") from error
    return len(graph)


def rdf_instance_preview(
    rdf_path: str | Path,
    *,
    offset: int = 0,
    limit: int = 10,
) -> dict[str, Any]:
    """Return a deterministic Turtle page grouped by RDF subject.

    A subject is treated as one RDF instance. Keeping pagination subject-based
    avoids splitting one instance's predicate/object statements across pages.
    """
    source = Path(rdf_path)
    if not source.is_file():
        raise PipelineError("The RDF artifact is missing.")
    try:
        graph = Graph().parse(source, format="turtle")
    except Exception as error:
        raise PipelineError(f"The RDF could not be previewed: {error}") from error

    subjects = sorted(set(graph.subjects()), key=lambda term: (term.__class__.__name__, term.n3()))
    total_instances = len(subjects)
    bounded_offset = min(max(offset, 0), total_instances)
    page_subjects = subjects[bounded_offset : bounded_offset + limit]
    page_graph = Graph()
    for prefix, namespace in graph.namespaces():
        page_graph.bind(prefix, namespace)
    for subject in page_subjects:
        for predicate, obj in graph.predicate_objects(subject):
            page_graph.add((subject, predicate, obj))

    returned = len(page_subjects)
    return {
        "text": page_graph.serialize(format="turtle") if returned else "",
        "offset": bounded_offset,
        "limit": limit,
        "returned_instances": returned,
        "total_instances": total_instances,
        "total_triples": len(graph),
        "has_previous": bounded_offset > 0,
        "has_next": bounded_offset + returned < total_instances,
    }


def run_rml_mapping(
    run_directory: Path,
    source_csv: Path,
    mapping_text: str,
) -> dict[str, Any]:
    if not mapping_text.strip():
        raise PipelineError("Paste an RML mapping before running this stage.")
    mapping_document = mapping_text
    if not re.search(r"(?im)^\s*@base\s+", mapping_document):
        mapping_document = "@base <https://example.org/rml-mapping/> .\n" + mapping_document
    mapping_triples = parse_turtle(mapping_document, label="The RML mapping")
    mapping_path = run_directory / "mapping.rml.ttl"
    output_path = run_directory / "mapped.ttl"
    mapping_path.write_text(mapping_document, encoding="utf-8")

    if not RML_MAPPER_JAR.is_file():
        raise PipelineError(
            "RMLMapper is not available. Set RML_MAPPER_JAR to the mapper JAR path in the deployment."
        )

    result = run_command(
        [
            "java",
            "-jar",
            str(RML_MAPPER_JAR),
            "-m",
            str(mapping_path),
            "-o",
            str(output_path),
            "-s",
            "turtle",
        ],
        cwd=run_directory,
        label="RML mapping",
    )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise PipelineError(
            "RMLMapper completed without producing RDF. Check that rml:source is "
            f"'{source_csv.name}' and that every template/reference name matches a CSV column.",
            result.log,
        )
    try:
        mapped_graph = Graph().parse(output_path, format="turtle")
    except Exception as error:
        raise PipelineError(f"RMLMapper produced invalid Turtle: {error}", result.log) from error
    if not mapped_graph:
        available_columns: list[str] = []
        try:
            with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
                available_columns = next(csv.reader(handle), [])
        except (OSError, csv.Error, StopIteration):
            pass
        column_hint = (
            " Available CSV columns: " + ", ".join(repr(column) for column in available_columns)
            if available_columns
            else ""
        )
        raise PipelineError(
            "RMLMapper produced zero triples. A subject template usually cannot be created when "
            "a referenced column is missing or empty." + column_hint,
            result.log,
        )
    return {
        "mapping_path": mapping_path,
        "output_path": output_path,
        "mapping_triples": mapping_triples,
        "rdf_triples": len(mapped_graph),
        "log": result.log,
    }



def graph_name_to_uri(graph_name: str) -> str:
    value = graph_name.strip()
    if not value:
        raise PipelineError("Enter a graph name before ingestion.")
    if value.startswith(("http://", "https://")):
        if any(character.isspace() for character in value):
            raise PipelineError("A graph IRI cannot contain whitespace.")
        return value
    return f"{DEFAULT_GRAPH_BASE.rstrip('/')}/{quote(value, safe='-._~')}"


def ingest_graph(rdf_path: Path, graph_name: str, mode: str = "replace") -> dict[str, Any]:
    """Load RDF into a Fuseki named graph, replacing or appending to its content."""
    if mode not in {"replace", "append"}:
        raise PipelineError("Ingestion mode must be 'replace' or 'append'.")
    graph_uri = graph_name_to_uri(graph_name)
    replace = mode == "replace"
    if replace and not ingest.delete_graph(graph_uri):
        raise PipelineError(
            f"Fuseki could not clear the named graph {graph_uri}. No data was uploaded."
        )
    if not ingest.upload_graph(str(rdf_path), graph_uri, replace=replace):
        raise PipelineError(
            "Fuseki ingestion failed. Check FUSEKI_DATA_URL, the dataset name, and the Fuseki logs."
        )
    return {"graph_uri": graph_uri, "mode": mode, "graph_cleared": replace}


def load_rdf(path: Path, *, label: str = "The RDF data") -> Graph:
    if not path.is_file():
        raise PipelineError(f"{label} is missing. Run the RML mapping first.")
    try:
        return Graph().parse(path, format="turtle")
    except Exception as error:
        raise PipelineError(f"{label} could not be loaded: {error}") from error


def load_shapes(shapes_text: str) -> Graph:
    if not shapes_text.strip():
        raise PipelineError("Provide SHACL shapes by pasting them or uploading a file.")
    try:
        return Graph().parse(
            data=shapes_text, format="turtle", publicID="https://example.org/shapes/"
        )
    except Exception as error:
        raise PipelineError(f"The SHACL shapes are not valid Turtle: {error}") from error


def run_shacl_validation(run_directory: Path, data_path: Path, shapes_text: str) -> dict[str, Any]:
    """Validate RDF against SHACL shapes, including SHACL-SPARQL constraints."""
    shapes = load_shapes(shapes_text)
    data = load_rdf(data_path)
    shapes_path = run_directory / "shacl_validation_shapes.ttl"
    report_path = run_directory / "shacl_validation_report.txt"
    shapes_path.write_text(shapes_text, encoding="utf-8")
    try:
        result = shacl_engine.validate(data, shapes)
    except Exception as error:
        raise PipelineError(f"SHACL validation could not run: {error}") from error
    report_path.write_text(result.pop("report_text"), encoding="utf-8")
    return {
        **result,
        "shapes": shacl_engine.shapes_summary(shapes),
        "data_triples": len(data),
        "shapes_path": shapes_path,
        "report_path": report_path,
    }


def run_shacl_rules(run_directory: Path, data_path: Path, shapes_text: str) -> dict[str, Any]:
    """Apply sh:rule definitions and write the enriched graph as a new artifact."""
    shapes = load_shapes(shapes_text)
    summary = shacl_engine.shapes_summary(shapes)
    if not summary["rules"]:
        raise PipelineError(
            "The shapes do not declare any sh:rule. Add a sh:TripleRule or sh:SPARQLRule to enrich data."
        )
    data = load_rdf(data_path)
    shapes_path = run_directory / "shacl_rules_shapes.ttl"
    output_path = run_directory / "enriched.ttl"
    shapes_path.write_text(shapes_text, encoding="utf-8")
    try:
        enriched = shacl_engine.apply_rules(data, shapes)
    except Exception as error:
        raise PipelineError(f"SHACL rules could not run: {error}") from error
    enriched.serialize(destination=output_path, format="turtle")
    return {
        "shapes": summary,
        "input_triples": len(data),
        "inferred_triples": max(len(enriched) - len(data), 0),
        "total_triples": len(enriched),
        "shapes_path": shapes_path,
        "output_path": output_path,
    }


RDF_EXPORT_FORMATS = {
    "turtle": ("text/turtle", "ttl"),
    "ntriples": ("application/n-triples", "nt"),
    "jsonld": ("application/ld+json", "jsonld"),
    "xml": ("application/rdf+xml", "rdf"),
}


def export_rdf(path: Path, rdf_format: str) -> tuple[bytes, str, str]:
    """Serialise an RDF artifact in the requested format: (content, media type, extension)."""
    if rdf_format not in RDF_EXPORT_FORMATS:
        raise PipelineError(
            "Unsupported RDF format. Choose one of: " + ", ".join(RDF_EXPORT_FORMATS) + "."
        )
    media_type, extension = RDF_EXPORT_FORMATS[rdf_format]
    if rdf_format == "turtle":
        if not path.is_file():
            raise PipelineError("The RDF data is missing. Run the RML mapping first.")
        return path.read_bytes(), media_type, extension
    graph = load_rdf(path)
    serialised = graph.serialize(format="json-ld" if rdf_format == "jsonld" else rdf_format)
    data = serialised.encode("utf-8") if isinstance(serialised, str) else serialised
    return data, media_type, extension


def tool_status() -> dict[str, Any]:
    return {
        "java": bool(shutil.which("java")),
        "rml_mapper": RML_MAPPER_JAR.is_file(),
        "rml_mapper_path": str(RML_MAPPER_JAR),
    }
