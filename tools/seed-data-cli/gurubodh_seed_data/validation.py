import csv
import re
from collections import defaultdict
from dataclasses import dataclass

from gurubodh_seed_data.paths import category_paths, glossary_paths, subject_paths


REQUIRED_GLOSSARY_HEADERS = ("Sr No", "Term Code", "Term", "Definition")
REQUIRED_CATEGORY_HEADERS = (
    "code",
    "legacy_code",
    "is_active",
    "sort_order",
    "desired_status",
    "name_en",
    "description_en",
    "name_hi-IN",
    "description_hi-IN",
)
REQUIRED_SUBJECT_HEADERS = (
    "code",
    "legacy_code",
    "is_active",
    "sort_order",
    "category_code",
    "desired_status",
    "name_en",
    "description_en",
    "name_hi-IN",
    "description_hi-IN",
    "from_date",
    "to_date",
    "prabodhan_count",
)
TERM_CODE_PATTERN = re.compile(r"^T([0-9]{5})$")
CATEGORY_CODE_PATTERN = re.compile(r"^CAT[0-9]{3}$")
SUBJECT_CODE_PATTERN = re.compile(r"^SUB[0-9]{3}$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TERM_CODE_MIN = 1
TERM_CODE_MAX = 50000
BOOLEAN_VALUES = {"true", "false"}
DESIRED_STATUS_VALUES = {"draft", "published"}
MAX_TEXT_LENGTHS = {
    "legacy_code": 255,
    "name_en": 255,
    "name_hi-IN": 255,
}


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    row_number: int
    column: str
    message: str


@dataclass(frozen=True)
class CsvValidationResult:
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


GlossaryValidationResult = CsvValidationResult
CategoryValidationResult = CsvValidationResult
SubjectValidationResult = CsvValidationResult


def normalize_term_for_uniqueness(term):
    return "".join(term.split())


def parse_boolean(value):
    return value.strip().lower() == "true"


def parse_optional_integer(value):
    value = value.strip()
    return int(value) if value else None


def parse_optional_text(value):
    value = value.strip()
    return value or None


def validate_glossary_csv(source):
    paths = glossary_paths(source)
    csv_path = paths.csv_input
    issues = []
    data_row_count = 0

    if not csv_path.exists():
        return CsvValidationResult(
            source_key=source.key,
            csv_path=str(paths.csv_input),
            data_row_count=0,
            issues=(
                ValidationIssue(
                    severity="error",
                    row_number=0,
                    column="File",
                    message=f"CSV input file does not exist: {csv_path}",
                ),
            ),
        )

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        try:
            headers = next(reader)
        except StopIteration:
            return CsvValidationResult(
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
            return CsvValidationResult(
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

    return CsvValidationResult(
        source_key=source.key,
        csv_path=str(paths.csv_input),
        data_row_count=data_row_count,
        issues=tuple(sorted(issues, key=lambda issue: (issue.row_number, issue.column))),
    )


def validate_category_csv(source):
    paths = category_paths(source)
    return _validate_reference_seed_csv(
        source=source,
        csv_path=paths.csv_input,
        expected_headers=REQUIRED_CATEGORY_HEADERS,
        required_columns=("code", "is_active", "sort_order", "desired_status", "name_en"),
        code_column="code",
        code_pattern=CATEGORY_CODE_PATTERN,
        code_format_message="Expected format CATnnn, for example CAT001.",
        duplicate_columns=("code", "legacy_code", "sort_order"),
    )


def validate_subject_csv(source, category_source=None):
    paths = subject_paths(source)
    result = _validate_reference_seed_csv(
        source=source,
        csv_path=paths.csv_input,
        expected_headers=REQUIRED_SUBJECT_HEADERS,
        required_columns=(
            "code",
            "is_active",
            "sort_order",
            "category_code",
            "desired_status",
            "name_en",
        ),
        code_column="code",
        code_pattern=SUBJECT_CODE_PATTERN,
        code_format_message="Expected format SUBnnn, for example SUB001.",
        duplicate_columns=("code", "legacy_code", "sort_order"),
        category_code_column="category_code",
        date_columns=("from_date", "to_date"),
        integer_columns=("prabodhan_count",),
    )
    if category_source is None or _has_header_or_file_error(result):
        return result

    category_result = validate_category_csv(category_source)
    if not category_result.is_valid:
        return _append_issues(
            result,
            (
                ValidationIssue(
                    severity="error",
                    row_number=0,
                    column="category_code",
                    message="Category source validation failed; cannot validate subject references.",
                ),
            ),
        )

    category_codes = _load_category_codes(category_source)
    reference_issues = _validate_subject_category_references(
        source,
        category_codes,
    )
    return _append_issues(result, reference_issues)


def _validate_reference_seed_csv(
    source,
    csv_path,
    expected_headers,
    required_columns,
    code_column,
    code_pattern,
    code_format_message,
    duplicate_columns,
    category_code_column=None,
    date_columns=(),
    integer_columns=(),
):
    issues = []
    data_row_count = 0

    if not csv_path.exists():
        return CsvValidationResult(
            source_key=source.key,
            csv_path=str(csv_path),
            data_row_count=0,
            issues=(
                ValidationIssue(
                    severity="error",
                    row_number=0,
                    column="File",
                    message=f"CSV input file does not exist: {csv_path}",
                ),
            ),
        )

    duplicate_values = {column: defaultdict(list) for column in duplicate_columns}

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        try:
            headers = next(reader)
        except StopIteration:
            return CsvValidationResult(
                source_key=source.key,
                csv_path=str(csv_path),
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

        if tuple(headers) != expected_headers:
            expected = ", ".join(expected_headers)
            actual = ", ".join(headers) if headers else "(none)"
            return CsvValidationResult(
                source_key=source.key,
                csv_path=str(csv_path),
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
            if len(row) != len(expected_headers):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column="Row",
                        message=f"Expected {len(expected_headers)} columns, found {len(row)}.",
                    )
                )
                continue

            values = dict(zip(expected_headers, row))
            stripped_values = {
                column: value.strip()
                for column, value in values.items()
            }

            for column in required_columns:
                if not stripped_values[column]:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            row_number=row_number,
                            column=column,
                            message="Required value is missing.",
                        )
                    )

            code = stripped_values[code_column]
            if code and not code_pattern.fullmatch(code):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column=code_column,
                        message=code_format_message,
                    )
                )

            category_code = stripped_values.get(category_code_column or "")
            if category_code and not CATEGORY_CODE_PATTERN.fullmatch(category_code):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column=category_code_column,
                        message="Expected format CATnnn, for example CAT001.",
                    )
                )

            _validate_boolean(row_number, stripped_values, "is_active", issues)
            _validate_integer(row_number, stripped_values, "sort_order", issues)
            _validate_desired_status(row_number, stripped_values, issues)
            _validate_max_lengths(row_number, stripped_values, issues)
            for column in date_columns:
                _validate_optional_date(row_number, stripped_values, column, issues)
            for column in integer_columns:
                _validate_optional_integer(row_number, stripped_values, column, issues)

            for column in duplicate_columns:
                value = stripped_values[column]
                if value:
                    duplicate_values[column][value].append(row_number)

    issues.extend(_duplicate_issues(duplicate_values))
    return CsvValidationResult(
        source_key=source.key,
        csv_path=str(csv_path),
        data_row_count=data_row_count,
        issues=tuple(sorted(issues, key=lambda issue: (issue.row_number, issue.column))),
    )


def _validate_boolean(row_number, values, column, issues):
    value = values[column]
    if value and value.lower() not in BOOLEAN_VALUES:
        issues.append(
            ValidationIssue(
                severity="error",
                row_number=row_number,
                column=column,
                message="Expected boolean value true or false.",
            )
        )


def _validate_integer(row_number, values, column, issues):
    value = values[column]
    if value:
        try:
            int(value)
        except ValueError:
            issues.append(
                ValidationIssue(
                    severity="error",
                    row_number=row_number,
                    column=column,
                    message="Expected an integer value.",
                )
            )


def _validate_optional_integer(row_number, values, column, issues):
    value = values[column]
    if value:
        try:
            int(value)
        except ValueError:
            issues.append(
                ValidationIssue(
                    severity="error",
                    row_number=row_number,
                    column=column,
                    message="Expected an integer value when present.",
                )
            )


def _validate_optional_date(row_number, values, column, issues):
    value = values[column]
    if value and not DATE_PATTERN.fullmatch(value):
        issues.append(
            ValidationIssue(
                severity="error",
                row_number=row_number,
                column=column,
                message="Expected date format YYYY-MM-DD when present.",
            )
        )


def _validate_desired_status(row_number, values, issues):
    value = values["desired_status"]
    if value and value not in DESIRED_STATUS_VALUES:
        issues.append(
            ValidationIssue(
                severity="error",
                row_number=row_number,
                column="desired_status",
                message="Expected desired_status to be draft or published.",
            )
        )


def _validate_max_lengths(row_number, values, issues):
    for column, max_length in MAX_TEXT_LENGTHS.items():
        value = values.get(column, "")
        if len(value) > max_length:
            issues.append(
                ValidationIssue(
                    severity="error",
                    row_number=row_number,
                    column=column,
                    message=f"Value must be {max_length} characters or fewer.",
                )
            )


def _duplicate_issues(duplicate_values):
    issues = []
    for column, rows_by_value in duplicate_values.items():
        for value, rows in rows_by_value.items():
            if len(rows) > 1:
                row_list = ", ".join(str(row_number) for row_number in rows)
                for row_number in rows:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            row_number=row_number,
                            column=column,
                            message=(
                                f"Duplicate non-empty {column} value {value!r}; "
                                f"appears on rows: {row_list}."
                            ),
                        )
                    )
    return issues


def _has_header_or_file_error(result):
    return any(issue.column in {"File", "Header"} for issue in result.errors)


def _append_issues(result, issues):
    return CsvValidationResult(
        source_key=result.source_key,
        csv_path=result.csv_path,
        data_row_count=result.data_row_count,
        issues=tuple(
            sorted(
                result.issues + tuple(issues),
                key=lambda issue: (issue.row_number, issue.column),
            )
        ),
    )


def _load_category_codes(category_source):
    paths = category_paths(category_source)
    with paths.csv_input.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return {
            row["code"].strip()
            for row in reader
            if row.get("code", "").strip()
        }


def _validate_subject_category_references(subject_source, category_codes):
    paths = subject_paths(subject_source)
    issues = []
    with paths.csv_input.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):
            category_code = row.get("category_code", "").strip()
            if category_code and category_code not in category_codes:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        row_number=row_number,
                        column="category_code",
                        message=(
                            "Unresolved category_code; no matching category "
                            f"code found: {category_code}."
                        ),
                    )
                )
    return tuple(issues)
