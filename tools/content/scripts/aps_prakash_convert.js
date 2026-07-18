#!/usr/bin/env node
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const converterPath = path.join(__dirname, "vendor", "hindietools_aps_prakash_to_unicode.js");
const converterSource = fs.readFileSync(converterPath, "utf8");

function convertOne(input) {
  const store = {
    legacy_text: { value: input },
    unicode_text: { value: "" },
  };
  const context = {
    document: {
      getElementById(id) {
        return store[id];
      },
    },
    setTimeout(fn) {
      return fn();
    },
    alert() {},
    console,
  };

  vm.createContext(context);
  vm.runInContext(converterSource, context);
  context.convert_to_unicode();
  return store.unicode_text.value;
}

const raw = fs.readFileSync(0, "utf8");
const values = JSON.parse(raw);
process.stdout.write(JSON.stringify(values.map(convertOne)));
