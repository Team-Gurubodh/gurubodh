#!/usr/bin/env node
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const CONVERTERS = {
  aps: path.join(__dirname, "vendor", "hindietools_aps_prakash_to_unicode.js"),
  shreelipi: path.join(__dirname, "vendor", "hindietools_shreelipi_to_unicode.js"),
};

function loadConverter(converterName) {
  const converterPath = CONVERTERS[converterName];
  if (!converterPath) {
    throw new Error(`Unknown converter: ${converterName}`);
  }
  return fs.readFileSync(converterPath, "utf8");
}

function convertOne(converterSource, input) {
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

function normalizePayload(payload) {
  if (Array.isArray(payload)) {
    return { converter: "aps", texts: payload };
  }
  return payload;
}

const raw = fs.readFileSync(0, "utf8");
const payload = normalizePayload(JSON.parse(raw));
const converter = payload.converter || "aps";
const texts = payload.texts || [];
const converterSource = loadConverter(converter);
process.stdout.write(JSON.stringify(texts.map((text) => convertOne(converterSource, text))));
