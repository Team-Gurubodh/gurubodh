/**
 * Google Sheets setup for Gurubodh Subject seed data.
 *
 * Shape: one row per Subject, with localized field columns for English and
 * Hindi. Strapi internal id/documentId values are intentionally not included.
 *
 * Usage:
 * 1. Open the Google Sheet.
 * 2. Extensions > Apps Script.
 * 3. Paste this file into a script file.
 * 4. Run setupSubjectSeedDataSheet().
 *
 * The category lookup expects a Categories sheet where:
 * - code is in column A
 * - name_en is in column F
 * - name_hi-IN is in column H
 */
const SUBJECT_SHEET_NAME = 'Subjects';
const SUBJECT_CATEGORY_SHEET_NAME = 'Categories';
const SUBJECT_MAX_ROWS = 1000;

const SUBJECT_HEADERS = [
  'code',
  'legacy_code',
  'is_active',
  'sort_order',
  'category_name_en',
  'category_name_hi-IN',
  'category_code',
  'desired_status',
  'name_en',
  'description_en',
  'name_hi-IN',
  'description_hi-IN',
];

function setupSubjectSeedDataSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = getOrCreateSubjectSheet_(spreadsheet);

  setupSubjectHeaders_(sheet);
  setupSubjectCategoryCodeFormulas_(sheet);
  setupSubjectCategoryLookupHelpers_(sheet);
  setupSubjectDataValidations_(spreadsheet, sheet);
  setupSubjectConditionalFormatting_(spreadsheet, sheet);
  setupSubjectPresentation_(sheet);
}

function getOrCreateSubjectSheet_(spreadsheet) {
  return spreadsheet.getSheetByName(SUBJECT_SHEET_NAME)
    || spreadsheet.insertSheet(SUBJECT_SHEET_NAME);
}

function setupSubjectHeaders_(sheet) {
  const headerRange = sheet.getRange(1, 1, 1, SUBJECT_HEADERS.length);
  headerRange.setValues([SUBJECT_HEADERS]);
  headerRange
    .setFontWeight('bold')
    .setBackground('#e8f0fe')
    .setWrap(true);
  sheet.setFrozenRows(1);
}

function setupSubjectCategoryCodeFormulas_(sheet) {
  const formulas = [];
  for (let row = 2; row <= SUBJECT_MAX_ROWS; row += 1) {
    formulas.push([
      `=IF(E${row}<>"",IFERROR(XLOOKUP(E${row},Categories!$F$2:$F,Categories!$A$2:$A,""),""),IF(F${row}<>"",IFERROR(XLOOKUP(F${row},Categories!$H$2:$H,Categories!$A$2:$A,""),""),""))`,
    ]);
  }
  sheet.getRange(2, 7, SUBJECT_MAX_ROWS - 1, 1).setFormulas(formulas);
  sheet
    .getRange(`G2:G${SUBJECT_MAX_ROWS}`)
    .setNote('Auto-filled from category_name_en or category_name_hi-IN. Edit the category name helper columns instead of this column.');
}

function setupSubjectCategoryLookupHelpers_(sheet) {
  const enCodeFormulas = [];
  const hiCodeFormulas = [];
  const warningFormulas = [];

  for (let row = 2; row <= SUBJECT_MAX_ROWS; row += 1) {
    enCodeFormulas.push([
      `=IF(E${row}<>"",IFERROR(XLOOKUP(E${row},Categories!$F$2:$F,Categories!$A$2:$A,""),""),"")`,
    ]);
    hiCodeFormulas.push([
      `=IF(F${row}<>"",IFERROR(XLOOKUP(F${row},Categories!$H$2:$H,Categories!$A$2:$A,""),""),"")`,
    ]);
    warningFormulas.push([
      `=IF(AND(M${row}<>"",N${row}<>"",M${row}<>N${row}),"category name mismatch","")`,
    ]);
  }

  sheet.getRange('M1:O1').setValues([[
    '_category_name_en_code',
    '_category_name_hi_code',
    '_category_lookup_warning',
  ]]);
  sheet.getRange(2, 13, SUBJECT_MAX_ROWS - 1, 1).setFormulas(enCodeFormulas);
  sheet.getRange(2, 14, SUBJECT_MAX_ROWS - 1, 1).setFormulas(hiCodeFormulas);
  sheet.getRange(2, 15, SUBJECT_MAX_ROWS - 1, 1).setFormulas(warningFormulas);
}

function setupSubjectDataValidations_(spreadsheet, sheet) {
  const lastRow = SUBJECT_MAX_ROWS;

  setSubjectFormulaValidation_(
    sheet.getRange(`A2:A${lastRow}`),
    '=OR(A2="",REGEXMATCH(A2,"^SUB[0-9]{3}$"))',
    'Subject code must use SUBnnn format, e.g. SUB001.'
  );
  setSubjectFormulaValidation_(
    sheet.getRange(`B2:B${lastRow}`),
    '=OR(B2="",LEN(B2)<=255)',
    'Legacy code must be 255 characters or fewer.'
  );
  setSubjectListValidation_(sheet.getRange(`C2:C${lastRow}`), ['true', 'false']);
  setSubjectFormulaValidation_(
    sheet.getRange(`D2:D${lastRow}`),
    '=OR(D2="",AND(ISNUMBER(D2),INT(D2)=D2))',
    'Sort order must be an integer.'
  );
  setSubjectCategoryNameValidation_(spreadsheet, sheet.getRange(`E2:E${lastRow}`), 'F');
  setSubjectCategoryNameValidation_(spreadsheet, sheet.getRange(`F2:F${lastRow}`), 'H');
  setSubjectCategoryCodeValidation_(spreadsheet, sheet.getRange(`G2:G${lastRow}`));
  setSubjectListValidation_(sheet.getRange(`H2:H${lastRow}`), ['draft', 'published']);
  setSubjectFormulaValidation_(
    sheet.getRange(`I2:I${lastRow}`),
    '=OR(I2="",LEN(I2)<=255)',
    'English subject name must be 255 characters or fewer.'
  );
  setSubjectFormulaValidation_(
    sheet.getRange(`K2:K${lastRow}`),
    '=OR(K2="",LEN(K2)<=255)',
    'Hindi subject name must be 255 characters or fewer.'
  );
}

function setSubjectCategoryNameValidation_(spreadsheet, range, sourceColumn) {
  const categorySheet = spreadsheet.getSheetByName(SUBJECT_CATEGORY_SHEET_NAME);
  if (!categorySheet) {
    range.setNote('Create the Categories sheet and run setupCategorySeedDataSheet() before applying category-name dropdown validation.');
    return;
  }

  const categoryNameRange = categorySheet.getRange(`${sourceColumn}2:${sourceColumn}${SUBJECT_MAX_ROWS}`);
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInRange(categoryNameRange, true)
    .setAllowInvalid(false)
    .setHelpText('Choose a Category name from the Categories sheet.')
    .build();
  range.setDataValidation(rule);
}

function setSubjectCategoryCodeValidation_(spreadsheet, range) {
  const categorySheet = spreadsheet.getSheetByName(SUBJECT_CATEGORY_SHEET_NAME);
  if (!categorySheet) {
    range.setNote('Create the Categories sheet and run setupCategorySeedDataSheet() before applying category_code validation.');
    return;
  }

  const categoryCodeRange = categorySheet.getRange(`A2:A${SUBJECT_MAX_ROWS}`);
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInRange(categoryCodeRange, true)
    .setAllowInvalid(false)
    .setHelpText('Subject category_code must match an existing Category code.')
    .build();
  range.setDataValidation(rule);
}

function setupSubjectConditionalFormatting_(spreadsheet, sheet) {
  const rules = [];

  rules.push(subjectRequiredRule_(sheet.getRange(`A2:A${SUBJECT_MAX_ROWS}`), '=A2=""'));
  rules.push(subjectRequiredRule_(sheet.getRange(`C2:C${SUBJECT_MAX_ROWS}`), '=C2=""'));
  rules.push(subjectRequiredRule_(sheet.getRange(`D2:D${SUBJECT_MAX_ROWS}`), '=D2=""'));
  rules.push(subjectRequiredRule_(sheet.getRange(`G2:G${SUBJECT_MAX_ROWS}`), '=G2=""'));
  rules.push(subjectRequiredRule_(sheet.getRange(`I2:I${SUBJECT_MAX_ROWS}`), '=I2=""'));

  rules.push(subjectDuplicateRule_(sheet.getRange(`A2:A${SUBJECT_MAX_ROWS}`), '=AND(A2<>"",COUNTIF($A$2:$A,A2)>1)'));
  rules.push(subjectDuplicateRule_(sheet.getRange(`B2:B${SUBJECT_MAX_ROWS}`), '=AND(B2<>"",COUNTIF($B$2:$B,B2)>1)'));
  rules.push(subjectDuplicateRule_(sheet.getRange(`D2:D${SUBJECT_MAX_ROWS}`), '=AND(D2<>"",COUNTIF($D$2:$D,D2)>1)'));

  rules.push(subjectInvalidRule_(sheet.getRange(`A2:A${SUBJECT_MAX_ROWS}`), '=AND(A2<>"",NOT(REGEXMATCH(A2,"^SUB[0-9]{3}$")))'));
  rules.push(subjectInvalidRule_(sheet.getRange(`B2:B${SUBJECT_MAX_ROWS}`), '=LEN(B2)>255'));
  rules.push(subjectInvalidRule_(sheet.getRange(`I2:I${SUBJECT_MAX_ROWS}`), '=LEN(I2)>255'));
  rules.push(subjectInvalidRule_(sheet.getRange(`K2:K${SUBJECT_MAX_ROWS}`), '=LEN(K2)>255'));

  rules.push(subjectInvalidRule_(
    sheet.getRange(`E2:F${SUBJECT_MAX_ROWS}`),
    '=$O2<>""'
  ));

  sheet.setConditionalFormatRules(rules);
}

function setupSubjectPresentation_(sheet) {
  sheet.autoResizeColumns(1, SUBJECT_HEADERS.length);
  sheet.hideColumns(13, 3);
  if (!sheet.getFilter()) {
    sheet.getRange(`A1:L${SUBJECT_MAX_ROWS}`).createFilter();
  }
}

function setSubjectFormulaValidation_(range, formula, helpText) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(formula)
    .setAllowInvalid(false)
    .setHelpText(helpText)
    .build();
  range.setDataValidation(rule);
}

function setSubjectListValidation_(range, values) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(values, true)
    .setAllowInvalid(false)
    .build();
  range.setDataValidation(rule);
}

function subjectRequiredRule_(range, formula) {
  return SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground('#fce8e6')
    .setRanges([range])
    .build();
}

function subjectDuplicateRule_(range, formula) {
  return SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground('#fef7e0')
    .setRanges([range])
    .build();
}

function subjectInvalidRule_(range, formula) {
  return SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground('#f4cccc')
    .setRanges([range])
    .build();
}
