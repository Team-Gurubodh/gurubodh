/**
 * Append additional Gurubodh Subject seed-data columns.
 *
 * Usage:
 * 1. Open the Google Sheet.
 * 2. Extensions > Apps Script.
 * 3. Paste this file into the same Apps Script project as subject-validations.gs.
 * 4. Run appendSubjectSeedDataColumns().
 */
const APPEND_SUBJECT_COLUMNS = [
  {
    header: 'from_date',
    type: 'date',
    required: true,
  },
  {
    header: 'to_date',
    type: 'date',
    required: true,
  },
  {
    header: 'prabodhan_count',
    type: 'count',
    required: true,
    defaultValue: 50,
  },
];

function appendSubjectSeedDataColumns() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheetName = getAppendSubjectSheetName_();
  const sheet = spreadsheet.getSheetByName(sheetName);

  if (!sheet) {
    throw new Error(`Sheet "${sheetName}" does not exist.`);
  }

  const existingHeaderMap = getAppendSubjectHeaderMap_(sheet);
  const columnsToAppend = APPEND_SUBJECT_COLUMNS.filter(
    (column) => !existingHeaderMap.has(column.header)
  );

  if (columnsToAppend.length === 0) {
    Logger.log('All requested Subject columns already exist. No columns appended.');
    return;
  }

  const appendStartColumn = Math.max(sheet.getLastColumn(), 1) + 1;
  const appendedColumnNumbers = appendSubjectHeaders_(sheet, appendStartColumn, columnsToAppend);
  const updatedHeaderMap = getAppendSubjectHeaderMap_(sheet);

  applyAppendSubjectColumnSetup_(sheet, updatedHeaderMap, appendedColumnNumbers);
  expandAppendSubjectFilter_(sheet);
  sheet.autoResizeColumns(appendStartColumn, columnsToAppend.length);
}

function getAppendSubjectHeaderMap_(sheet) {
  const headerMap = new Map();
  const lastColumn = sheet.getLastColumn();

  if (lastColumn === 0) {
    return headerMap;
  }

  const headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];
  headers.forEach((header, index) => {
    if (header !== '') {
      headerMap.set(String(header), index + 1);
    }
  });

  return headerMap;
}

function getAppendSubjectSheetName_() {
  return typeof SUBJECT_SHEET_NAME !== 'undefined'
    ? SUBJECT_SHEET_NAME
    : 'Subjects';
}

function getAppendSubjectMaxRows_() {
  return typeof SUBJECT_MAX_ROWS !== 'undefined'
    ? SUBJECT_MAX_ROWS
    : 1000;
}

function appendSubjectHeaders_(sheet, startColumn, columns) {
  const headerRange = sheet.getRange(1, startColumn, 1, columns.length);
  headerRange.setValues([columns.map((column) => column.header)]);
  headerRange
    .setFontWeight('bold')
    .setBackground('#e8f0fe')
    .setWrap(true);

  return columns.map((_, index) => startColumn + index);
}

function applyAppendSubjectColumnSetup_(sheet, headerMap, appendedColumnNumbers) {
  const fromDateColumn = headerMap.get('from_date');
  const toDateColumn = headerMap.get('to_date');
  const prabodhanCountColumn = headerMap.get('prabodhan_count');
  const appendedHeaders = new Set();
  const maxRows = getAppendSubjectMaxRows_();

  appendedColumnNumbers.forEach((columnNumber) => {
    const header = sheet.getRange(1, columnNumber).getValue();
    appendedHeaders.add(header);
    const dataRange = sheet.getRange(2, columnNumber, maxRows - 1, 1);

    if (header === 'from_date') {
      dataRange.setNumberFormat('yyyy-mm-dd');
      setAppendSubjectFormulaValidation_(
        dataRange,
        `=AND(${columnToLetter_(columnNumber)}2<>"",ISDATE(${columnToLetter_(columnNumber)}2))`,
        'from_date is required and must be a Google Sheets date.'
      );
    }

    if (header === 'to_date') {
      dataRange.setNumberFormat('yyyy-mm-dd');
      setAppendSubjectFormulaValidation_(
        dataRange,
        `=AND(${columnToLetter_(columnNumber)}2<>"",ISDATE(${columnToLetter_(columnNumber)}2),${columnToLetter_(columnNumber)}2>=${columnToLetter_(fromDateColumn)}2)`,
        'to_date is required, must be a Google Sheets date, and cannot be earlier than from_date.'
      );
    }

    if (header === 'prabodhan_count') {
      dataRange.setNumberFormat('0');
      prefillAppendSubjectBlankCells_(dataRange, 50);
      setAppendSubjectFormulaValidation_(
        dataRange,
        `=AND(${columnToLetter_(columnNumber)}2<>"",ISNUMBER(${columnToLetter_(columnNumber)}2),INT(${columnToLetter_(columnNumber)}2)=${columnToLetter_(columnNumber)}2,${columnToLetter_(columnNumber)}2>=1,${columnToLetter_(columnNumber)}2<=999)`,
        'prabodhan_count is required and must be a whole number between 1 and 999.'
      );
    }
  });

  appendSubjectConditionalFormatting_(
    sheet,
    appendedHeaders,
    maxRows,
    fromDateColumn,
    toDateColumn,
    prabodhanCountColumn
  );
}

function prefillAppendSubjectBlankCells_(range, defaultValue) {
  const values = range.getValues();
  let changed = false;

  for (let rowIndex = 0; rowIndex < values.length; rowIndex += 1) {
    if (values[rowIndex][0] === '') {
      values[rowIndex][0] = defaultValue;
      changed = true;
    }
  }

  if (changed) {
    range.setValues(values);
  }
}

function setAppendSubjectFormulaValidation_(range, formula, helpText) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(formula)
    .setAllowInvalid(false)
    .setHelpText(helpText)
    .build();
  range.setDataValidation(rule);
}

function appendSubjectConditionalFormatting_(
  sheet,
  appendedHeaders,
  maxRows,
  fromDateColumn,
  toDateColumn,
  prabodhanCountColumn
) {
  const rules = sheet.getConditionalFormatRules();

  if (appendedHeaders.has('from_date')) {
    addAppendSubjectConditionalRule_(
      rules,
      sheet.getRange(2, fromDateColumn, maxRows - 1, 1),
      `=${columnToLetter_(fromDateColumn)}2=""`,
      '#fce8e6'
    );
  }

  if (appendedHeaders.has('to_date')) {
    addAppendSubjectConditionalRule_(
      rules,
      sheet.getRange(2, toDateColumn, maxRows - 1, 1),
      `=${columnToLetter_(toDateColumn)}2=""`,
      '#fce8e6'
    );
    addAppendSubjectConditionalRule_(
      rules,
      sheet.getRange(2, toDateColumn, maxRows - 1, 1),
      `=AND(${columnToLetter_(toDateColumn)}2<>"",${columnToLetter_(fromDateColumn)}2<>"",${columnToLetter_(toDateColumn)}2<${columnToLetter_(fromDateColumn)}2)`,
      '#f4cccc'
    );
  }

  if (appendedHeaders.has('prabodhan_count')) {
    addAppendSubjectConditionalRule_(
      rules,
      sheet.getRange(2, prabodhanCountColumn, maxRows - 1, 1),
      `=${columnToLetter_(prabodhanCountColumn)}2=""`,
      '#fce8e6'
    );
    addAppendSubjectConditionalRule_(
      rules,
      sheet.getRange(2, prabodhanCountColumn, maxRows - 1, 1),
      `=AND(${columnToLetter_(prabodhanCountColumn)}2<>"",OR(NOT(ISNUMBER(${columnToLetter_(prabodhanCountColumn)}2)),INT(${columnToLetter_(prabodhanCountColumn)}2)<>${columnToLetter_(prabodhanCountColumn)}2,${columnToLetter_(prabodhanCountColumn)}2<1,${columnToLetter_(prabodhanCountColumn)}2>999))`,
      '#f4cccc'
    );
  }

  sheet.setConditionalFormatRules(rules);
}

function addAppendSubjectConditionalRule_(rules, range, formula, color) {
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied(formula)
      .setBackground(color)
      .setRanges([range])
      .build()
  );
}

function expandAppendSubjectFilter_(sheet) {
  const filter = sheet.getFilter();

  if (!filter) {
    return;
  }

  const filterRange = filter.getRange();
  if (filterRange.getRow() !== 1) {
    Logger.log('Existing filter does not start on the header row. Leaving filter unchanged.');
    return;
  }

  const lastColumn = sheet.getLastColumn();
  const filterEndColumn = filterRange.getColumn() + filterRange.getNumColumns() - 1;

  if (filterEndColumn >= lastColumn) {
    return;
  }

  const criteriaByColumn = {};
  for (let column = filterRange.getColumn(); column <= filterEndColumn; column += 1) {
    const criteria = filter.getColumnFilterCriteria(column);
    if (criteria) {
      criteriaByColumn[column] = criteria;
    }
  }

  try {
    filter.remove();
    const expandedFilterRange = sheet.getRange(
      1,
      filterRange.getColumn(),
      filterRange.getNumRows(),
      lastColumn - filterRange.getColumn() + 1
    );
    expandedFilterRange.createFilter();
    const expandedFilter = sheet.getFilter();

    Object.keys(criteriaByColumn).forEach((column) => {
      expandedFilter.setColumnFilterCriteria(Number(column), criteriaByColumn[column]);
    });
  } catch (error) {
    restoreAppendSubjectFilter_(sheet, filterRange, criteriaByColumn);
    Logger.log(`Could not safely expand the existing filter: ${error.message}`);
  }
}

function restoreAppendSubjectFilter_(sheet, filterRange, criteriaByColumn) {
  try {
    if (sheet.getFilter()) {
      sheet.getFilter().remove();
    }

    filterRange.createFilter();
    const restoredFilter = sheet.getFilter();
    Object.keys(criteriaByColumn).forEach((column) => {
      restoredFilter.setColumnFilterCriteria(Number(column), criteriaByColumn[column]);
    });
  } catch (restoreError) {
    Logger.log(`Could not restore the original filter: ${restoreError.message}`);
  }
}

function columnToLetter_(columnNumber) {
  let letter = '';
  let remaining = columnNumber;

  while (remaining > 0) {
    const remainder = (remaining - 1) % 26;
    letter = String.fromCharCode(65 + remainder) + letter;
    remaining = Math.floor((remaining - remainder - 1) / 26);
  }

  return letter;
}
