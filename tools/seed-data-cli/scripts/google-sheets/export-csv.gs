/**
 * Export Gurubodh Category and Subject seed-data worksheets to CSV files.
 *
 * Usage:
 * 1. Open the Google Sheet.
 * 2. Extensions > Apps Script.
 * 3. Paste this file into the same Apps Script project as the seed-data scripts.
 * 4. Run exportCategorySubjectSeedDataCsv().
 */
const CATEGORY_SUBJECT_CSV_EXPORTS = [
  {
    sheetName: 'Categories',
    fileName: 'categories.csv',
    columns: [
      'code',
      'legacy_code',
      'is_active',
      'sort_order',
      'desired_status',
      'name_en',
      'description_en',
      'name_hi-IN',
      'description_hi-IN',
    ],
    requiredRowColumns: ['code'],
  },
  {
    sheetName: 'Subjects',
    fileName: 'subjects.csv',
    columns: [
      'code',
      'legacy_code',
      'is_active',
      'sort_order',
      'category_code',
      'desired_status',
      'name_en',
      'description_en',
      'name_hi-IN',
      'description_hi-IN',
      'from_date',
      'to_date',
      'prabodhan_count',
    ],
    requiredRowColumns: ['code', 'category_code'],
  },
];

function exportCategorySubjectSeedDataCsv() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const folder = getSpreadsheetFolder_(spreadsheet);

  CATEGORY_SUBJECT_CSV_EXPORTS.forEach((exportConfig) => {
    const csv = buildSheetCsv_(spreadsheet, exportConfig);
    upsertCsvFile_(folder, exportConfig.fileName, csv);
    Logger.log(`Exported ${exportConfig.fileName}.`);
  });
}

function buildSheetCsv_(spreadsheet, exportConfig) {
  const sheet = spreadsheet.getSheetByName(exportConfig.sheetName);
  if (!sheet) {
    throw new Error(`Sheet "${exportConfig.sheetName}" does not exist.`);
  }

  const lastColumn = sheet.getLastColumn();
  if (lastColumn === 0) {
    throw new Error(`Sheet "${exportConfig.sheetName}" does not have a header row.`);
  }

  const headerValues = sheet.getRange(1, 1, 1, lastColumn).getDisplayValues()[0];
  const headerMap = buildHeaderMap_(headerValues);
  assertExportColumnsExist_(exportConfig, headerMap);

  const outputRows = [exportConfig.columns];
  const lastRow = sheet.getLastRow();

  if (lastRow > 1) {
    const dataValues = sheet.getRange(2, 1, lastRow - 1, lastColumn).getDisplayValues();
    dataValues.forEach((row) => {
      if (shouldExportRow_(row, exportConfig.requiredRowColumns, headerMap)) {
        outputRows.push(exportConfig.columns.map((columnName) => row[headerMap.get(columnName) - 1]));
      }
    });
  }

  return outputRows.map(csvRow_).join('\r\n') + '\r\n';
}

function buildHeaderMap_(headers) {
  const headerMap = new Map();
  const duplicateHeaders = new Set();

  headers.forEach((header, index) => {
    const normalizedHeader = String(header).trim();
    if (normalizedHeader !== '') {
      if (headerMap.has(normalizedHeader)) {
        duplicateHeaders.add(normalizedHeader);
      }
      headerMap.set(normalizedHeader, index + 1);
    }
  });

  if (duplicateHeaders.size > 0) {
    throw new Error(`Duplicate header columns found: ${Array.from(duplicateHeaders).join(', ')}.`);
  }

  return headerMap;
}

function assertExportColumnsExist_(exportConfig, headerMap) {
  const missingColumns = exportConfig.columns.filter((columnName) => !headerMap.has(columnName));

  if (missingColumns.length > 0) {
    throw new Error(
      `Sheet "${exportConfig.sheetName}" is missing required export columns: ${missingColumns.join(', ')}.`
    );
  }
}

function shouldExportRow_(row, requiredColumns, headerMap) {
  return requiredColumns.every((columnName) => {
    const value = row[headerMap.get(columnName) - 1];
    return String(value).trim() !== '';
  });
}

function csvRow_(values) {
  return values.map(csvValue_).join(',');
}

function csvValue_(value) {
  const text = String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }

  return text;
}

function getSpreadsheetFolder_(spreadsheet) {
  const spreadsheetFile = DriveApp.getFileById(spreadsheet.getId());
  const parents = spreadsheetFile.getParents();

  if (parents.hasNext()) {
    return parents.next();
  }

  return DriveApp.getRootFolder();
}

function upsertCsvFile_(folder, fileName, csv) {
  const matchingFiles = folder.getFilesByName(fileName);

  if (!matchingFiles.hasNext()) {
    folder.createFile(fileName, csv, 'text/csv');
    return;
  }

  const file = matchingFiles.next();
  if (matchingFiles.hasNext()) {
    throw new Error(`Multiple files named "${fileName}" exist in the spreadsheet folder.`);
  }

  file.setContent(csv);
}
