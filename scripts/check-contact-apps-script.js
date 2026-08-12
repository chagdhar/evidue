#!/usr/bin/env node
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("integrations/google-sheets/Code.gs", "utf8");
const rows = [];
const cache = new Map();
const sheet = {
  appendRow: (row) => rows.push(row),
  getLastRow: () => rows.length,
  getLastColumn: () => rows.length ? rows[0].length : 0,
  setFrozenRows: () => undefined,
  getRange: () => ({
    setFontWeight: () => undefined,
    setValues: (values) => {
      if (!rows.length) rows.push([]);
      rows[0].push(...values[0]);
    },
  }),
};
const context = {
  Date,
  JSON,
  String,
  Math,
  Boolean,
  ContentService: {
    MimeType: { JSON: "json" },
    createTextOutput: (text) => ({
      text,
      setMimeType() { return this; },
    }),
  },
  LockService: {
    getScriptLock: () => ({
      held: false,
      waitLock() { this.held = true; },
      hasLock() { return this.held; },
      releaseLock() { this.held = false; },
    }),
  },
  PropertiesService: {
    getScriptProperties: () => ({ getProperty: () => "test-secret-at-least-32-characters" }),
  },
  Utilities: {
    computeHmacSha256Signature: (value, secret) => [
      ...crypto.createHmac("sha256", secret).update(value).digest(),
    ].map((byte) => byte > 127 ? byte - 256 : byte),
  },
  CacheService: {
    getScriptCache: () => ({
      get: (key) => cache.get(key) ?? null,
      put: (key, value) => cache.set(key, value),
    }),
  },
  SpreadsheetApp: {
    getActiveSpreadsheet: () => ({
      getSheetByName: () => sheet,
      insertSheet: () => sheet,
    }),
  },
};

vm.createContext(context);
vm.runInContext(`${source}\nthis.__test = { safeCell, signaturesMatch, isFreshTimestamp, doPost };`, context);
const { safeCell, signaturesMatch, isFreshTimestamp, doPost } = context.__test;

assert.equal(safeCell("=IMPORTXML('https://evil.example')"), "'=IMPORTXML('https://evil.example')");
assert.equal(safeCell("ordinary feedback"), "ordinary feedback");
assert.equal(isFreshTimestamp("not-a-date", Date.now()), false);
assert.equal(isFreshTimestamp(new Date(Date.now() - 60_000).toISOString(), Date.now()), true);
assert.equal(signaturesMatch("abc", "abc"), true);
assert.equal(signaturesMatch("abc", "abd"), false);

const payload = JSON.stringify({
  submitted_at: new Date().toISOString(),
  submission_id: "11111111-1111-4111-8111-111111111111",
  name: "Alex",
  email: "alex@example.com",
  company: "Acme",
  discussion_type: "Product feedback",
  role: "Finance",
  billing_model: "",
  verification_method: "",
  evidence_location: "",
  commercial_action: "",
  feedback_area: "Demo clarity",
  message: "Useful feedback",
  open_to_call: false,
  confirmed_no_confidential_data: true,
  submission_channel: "native_contact_form",
  attribution_source: "hacker_news",
  campaign: "railway_beta",
  demo_version: "hn_demo",
});
const signature = crypto
  .createHmac("sha256", "test-secret-at-least-32-characters")
  .update(payload)
  .digest("hex");
const event = { postData: { contents: JSON.stringify({ payload, signature }) } };

assert.deepEqual(JSON.parse(doPost(event).text), { ok: true });
assert.deepEqual(JSON.parse(doPost(event).text), { ok: false, error: "duplicate" });
assert.equal(rows.length, 2);
assert.equal(rows[1][7], "native_contact_form");

process.stdout.write("Contact Apps Script checks passed.\n");
