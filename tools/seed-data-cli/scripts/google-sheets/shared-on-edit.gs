/**
 * Shared Google Sheets edit trigger for Gurubodh seed-data sheets.
 *
 * Add this file to the same Apps Script project as category-validations.gs and
 * subject-validations.gs. Keep only one global onEdit(e) function in the
 * project; this file dispatches to Category and Subject trimming helpers.
 */
function onEdit(e) {
  trimCategoryNamesOnEdit_(e);
  trimSubjectNamesOnEdit_(e);
}

function trimCategoryNamesOnEdit_(e) {
  if (!e || !e.range) {
    return;
  }

  const sheet = e.range.getSheet();
  if (sheet.getName() !== CATEGORY_SHEET_NAME) {
    return;
  }

  trimEditedColumns_(e.range, [6, 8]); // name_en, name_hi-IN
}

function trimSubjectNamesOnEdit_(e) {
  if (!e || !e.range) {
    return;
  }

  const sheet = e.range.getSheet();
  if (sheet.getName() !== SUBJECT_SHEET_NAME) {
    return;
  }

  trimEditedColumns_(e.range, [9, 11]); // name_en, name_hi-IN
}

function trimEditedColumns_(range, columnsToTrim) {
  const startRow = range.getRow();
  const startColumn = range.getColumn();
  const rowCount = range.getNumRows();
  const columnCount = range.getNumColumns();

  if (startRow < 2) {
    return;
  }

  const values = range.getValues();
  let changed = false;

  for (let rowOffset = 0; rowOffset < rowCount; rowOffset += 1) {
    for (let columnOffset = 0; columnOffset < columnCount; columnOffset += 1) {
      const absoluteColumn = startColumn + columnOffset;
      if (!columnsToTrim.includes(absoluteColumn)) {
        continue;
      }

      const value = values[rowOffset][columnOffset];
      if (typeof value !== 'string') {
        continue;
      }

      const trimmedValue = value.trim();
      if (trimmedValue !== value) {
        values[rowOffset][columnOffset] = trimmedValue;
        changed = true;
      }
    }
  }

  if (changed) {
    range.setValues(values);
  }
}
