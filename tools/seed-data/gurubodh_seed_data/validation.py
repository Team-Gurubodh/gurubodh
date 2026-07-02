import csv
import re
from collections import defaultdict
from dataclasses import dataclass

from gurubodh_seed_data.paths import glossary_paths, resolve_seed_data_path


REQUIRED_GLOSSARY_HEADERS = ("Sr No", "Term Code", "Term", "Definition")
TERM_CODE_PATTERN = re.compile(r"^T([0-9]{5})$")
TERM_CODE_MIN = 1
TERM_CODE_MAX = 50000


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    row_number: int
    column: str
    message: str


@dataclass(frozen=True)
class GlossaryValidationResult:
    source_key: str
    csv_path: str
    data_row_count: int
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self):
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self):
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def is_valid(self):
        return not self.errors


def normalize_term_for_uniqueness(term):
    return "".join(term.split())


def validate_glossary_csv(source):
    paths = glossary_paths(source)
    csv_path = resolve_seed_data_path(paths.csv_input)
    issues = []
    data_row_count = 0

    if not csv_path.exists():
        return GlossaryValidationResult(
            source_key=source.key,
            csv_path=str(paths.csv_input),
            data_row_count=0,
            issues=(
                ValidationIssue(
                    severity="error",
                    row_number=0,
                    column="File",
                    message=f"CSV input file does not exist: {paths.csv_input}",
                ),
            ),
        )

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        try:
            headers = next(reader)
        except StopIteration:
            return GlossaryValidationResult(
                source_key=source.key,
                csv_path=str(paths.csv_input),
                data_row_count=0,
                issues=(
                    ValidationIssue(
                        severity="error",
                        row_number=1,
                        column="Header",
                        message="CSV file is empty; expected required headers.",
                    ),
                ),
            )

        if tuple(headers) != REQUIRED_GLOSSARY_HEADERS:
            expected = ", ".join(REQUIRED_GLOSSARY_HEADERS)
            actual = ", ".join(headers) if headers else "(none)"
            return GlossaryValidationResult(
                source_key=source.key,
                csv_path=str(paths.csv_input),
                data_row_count=0,
                issues=(
                    ValidationIssue(
                        severity="error",
                        row_number=1,
                        column="Header",
                        message=f"Expected headers: {expected}. Found: {actual}.",
                    ),
                ),
            )

        term_rows = defaultdict(list)
        for row_number, row in enumerate(reader, start=2):
            if not any(value.strip() for value in row):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column="Row",
                        message="Blank rows are not allowed.",
                    )
                )
                continue

            data_row_count += 1
            if len(row) != len(REQUIRED_GLOSSARY_HEADERS):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column="Row",
                        message=(
                            f"Expected {len(REQUIRED_GLOSSARY_HEADERS)} columns, "
                            f"found {len(row)}."
                        ),
                    )
                )
                continue

            values = dict(zip(REQUIRED_GLOSSARY_HEADERS, row))
            stripped_values = {
                column: value.strip()
                for column, value in values.items()
            }

            term_value = values["Term"]
            if term_value != term_value.strip():
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column="Term",
                        message=(
                            "Term has leading or trailing whitespace. "
                            f"Cell value: {term_value!r}."
                        ),
                    )
                )

            for column in REQUIRED_GLOSSARY_HEADERS:
                if not stripped_values[column]:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            row_number=row_number,
                            column=column,
                            message="Required value is missing.",
                        )
                    )

            term_code = stripped_values["Term Code"]
            if term_code:
                match = TERM_CODE_PATTERN.fullmatch(term_code)
                if not match:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            row_number=row_number,
                            column="Term Code",
                            message="Expected format Tnnnnn, for example T00001.",
                        )
                    )
                else:
                    term_number = int(match.group(1))
                    if term_number < TERM_CODE_MIN or term_number > TERM_CODE_MAX:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                row_number=row_number,
                                column="Term Code",
                                message="Term Code must be in range T00001 through T50000.",
                            )
                        )

            term = stripped_values["Term"]
            if term:
                term_rows[normalize_term_for_uniqueness(term)].append(
                    (row_number, term)
                )

    for normalized_term, row_terms in term_rows.items():
        if len(row_terms) > 1:
            rows = ", ".join(str(row_number) for row_number, _term in row_terms)
            for row_number, term in row_terms:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column="Term",
                        message=(
                            "Duplicate term within source after removing "
                            f"whitespace; normalized value '{normalized_term}' "
                            f"appears on rows: {rows}. Row value: '{term}'."
                        ),
                    )
                )

    return GlossaryValidationResult(
        source_key=source.key,
        csv_path=str(paths.csv_input),
        data_row_count=data_row_count,
        issues=tuple(sorted(issues, key=lambda issue: (issue.row_number, issue.column))),
    )
