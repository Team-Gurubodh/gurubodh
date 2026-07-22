/**
 * Google Sheets setup for Gurubodh Category seed data.
 *
 * Shape: one row per Category, with localized field columns for English and
 * Hindi. Strapi internal id/documentId values are intentionally not included.
 *
 * Usage:
 * 1. Open the Google Sheet.
 * 2. Extensions > Apps Script.
 * 3. Paste this file into a script file.
 * 4. Run setupCategorySeedDataSheet().
 */
const CATEGORY_SHEET_NAME = 'Categories';
const CATEGORY_MAX_ROWS = 1000;

const CATEGORY_HEADERS = [
  'code',
  'legacy_code',
  'is_active',
  'sort_order',
  'desired_status',
  'name_en',
  'description_en',
  'name_hi-IN',
  'description_hi-IN',
];

function setupCategorySeedDataSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = getOrCreateCategorySheet_(spreadsheet);

  setupCategoryHeaders_(sheet);
  setupCategoryDataValidations_(sheet);
  setupCategoryConditionalFormatting_(sheet);
  setupCategoryPresentation_(sheet);
}

function getOrCreateCategorySheet_(spreadsheet) {
  return spreadsheet.getSheetByName(CATEGORY_SHEET_NAME)
    || spreadsheet.insertSheet(CATEGORY_SHEET_NAME);
}

function setupCategoryHeaders_(sheet) {
  const headerRange = sheet.getRange(1, 1, 1, CATEGORY_HEADERS.length);
  headerRange.setValues([CATEGORY_HEADERS]);
  headerRange
    .setFontWeight('bold')
    .setBackground('#e8f0fe')
    .setWrap(true);
  sheet.setFrozenRows(1);
}

function setupCategoryDataValidations_(sheet) {
  const lastRow = CATEGORY_MAX_ROWS;

  setFormulaValidation_(
    sheet.getRange(`A2:A${lastRow}`),
    '=OR(A2="",REGEXMATCH(A2,"^CAT[0-9]{3}$"))',
    'Category code must use CATnnn format, e.g. CAT001.'
  );
  setFormulaValidation_(
    sheet.getRange(`B2:B${lastRow}`),
    '=OR(B2="",LEN(B2)<=255)',
    'Legacy code must be 255 characters or fewer.'
  );
  setListValidation_(sheet.getRange(`C2:C${lastRow}`), ['true', 'false']);
  setFormulaValidation_(
    sheet.getRange(`D2:D${lastRow}`),
    '=OR(D2="",AND(ISNUMBER(D2),INT(D2)=D2))',
    'Sort order must be an integer.'
  );
  setListValidation_(sheet.getRange(`E2:E${lastRow}`), ['draft', 'published']);
  setFormulaValidation_(
    sheet.getRange(`F2:F${lastRow}`),
    '=OR(F2="",LEN(F2)<=255)',
    'English category name must be 255 characters or fewer.'
  );
  setFormulaValidation_(
    sheet.getRange(`H2:H${lastRow}`),
    '=OR(H2="",LEN(H2)<=255)',
    'Hindi category name must be 255 characters or fewer.'
  );
}

function setupCategoryConditionalFormatting_(sheet) {
  const rules = [];

  rules.push(requiredRule_(sheet.getRange(`A2:A${CATEGORY_MAX_ROWS}`), '=A2=""'));
  rules.push(requiredRule_(sheet.getRange(`C2:C${CATEGORY_MAX_ROWS}`), '=C2=""'));
  rules.push(requiredRule_(sheet.getRange(`D2:D${CATEGORY_MAX_ROWS}`), '=D2=""'));
  rules.push(requiredRule_(sheet.getRange(`F2:F${CATEGORY_MAX_ROWS}`), '=F2=""'));

  rules.push(duplicateRule_(sheet.getRange(`A2:A${CATEGORY_MAX_ROWS}`), '=AND(A2<>"",COUNTIF($A$2:$A,A2)>1)'));
  rules.push(duplicateRule_(sheet.getRange(`B2:B${CATEGORY_MAX_ROWS}`), '=AND(B2<>"",COUNTIF($B$2:$B,B2)>1)'));
  rules.push(duplicateRule_(sheet.getRange(`D2:D${CATEGORY_MAX_ROWS}`), '=AND(D2<>"",COUNTIF($D$2:$D,D2)>1)'));

  rules.push(invalidRule_(sheet.getRange(`A2:A${CATEGORY_MAX_ROWS}`), '=AND(A2<>"",NOT(REGEXMATCH(A2,"^CAT[0-9]{3}$")))'));
  rules.push(invalidRule_(sheet.getRange(`B2:B${CATEGORY_MAX_ROWS}`), '=LEN(B2)>255'));
  rules.push(invalidRule_(sheet.getRange(`F2:F${CATEGORY_MAX_ROWS}`), '=LEN(F2)>255'));
  rules.push(invalidRule_(sheet.getRange(`H2:H${CATEGORY_MAX_ROWS}`), '=LEN(H2)>255'));

  sheet.setConditionalFormatRules(rules);
}

function setupCategoryPresentation_(sheet) {
  sheet.autoResizeColumns(1, CATEGORY_HEADERS.length);
  if (!sheet.getFilter()) {
    sheet.getRange(`A1:I${CATEGORY_MAX_ROWS}`).createFilter();
  }
}

function setFormulaValidation_(range, formula, helpText) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(formula)
    .setAllowInvalid(false)
    .setHelpText(helpText)
    .build();
  range.setDataValidation(rule);
}

function setListValidation_(range, values) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(values, true)
    .setAllowInvalid(false)
    .build();
  range.setDataValidation(rule);
}

function requiredRule_(range, formula) {
  return SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground('#fce8e6')
    .setRanges([range])
    .build();
}

function duplicateRule_(range, formula) {
  return SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground('#fef7e0')
    .setRanges([range])
    .build();
}

function invalidRule_(range, formula) {
  return SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground('#f4cccc')
    .setRanges([range])
    .build();
}
