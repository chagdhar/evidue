const SHEET_NAME = "Contact submissions";
const HEADERS = [
  "Submitted at",
  "Name",
  "Email",
  "Company",
  "Discussion type",
  "Message",
  "Confidential-data confirmation",
  "Submission channel",
  "Acquisition source",
  "Campaign",
  "Demo version",
  "Submission ID",
  "Role",
  "Billing model",
  "Verification method",
  "Evidence location",
  "Commercial action",
  "Feedback area",
  "Open to 15-minute conversation",
];

function jsonResponse(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function safeCell(value) {
  const text = value == null ? "" : String(value);
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function toHex(bytes) {
  return bytes.map(function (byte) {
    const value = byte < 0 ? byte + 256 : byte;
    return ("0" + value.toString(16)).slice(-2);
  }).join("");
}

function signaturesMatch(left, right) {
  if (typeof left !== "string" || typeof right !== "string" || left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function isFreshTimestamp(value, now) {
  const submittedAt = new Date(value).getTime();
  return Boolean(submittedAt) && Math.abs(now - submittedAt) <= 5 * 60 * 1000;
}

function doPost(event) {
  const lock = LockService.getScriptLock();
  try {
    const envelope = JSON.parse(event.postData.contents || "{}");
    const expectedSecret = PropertiesService.getScriptProperties()
      .getProperty("EVIDUE_CONTACT_SECRET");
    const payloadText = typeof envelope.payload === "string" ? envelope.payload : "";
    const expectedSignature = toHex(
      Utilities.computeHmacSha256Signature(payloadText, expectedSecret || "")
    );

    if (!expectedSecret || !signaturesMatch(envelope.signature, expectedSignature)) {
      return jsonResponse({ ok: false, error: "unauthorized" });
    }
    const payload = JSON.parse(payloadText);
    if (!isFreshTimestamp(payload.submitted_at, Date.now())) {
      return jsonResponse({ ok: false, error: "expired" });
    }

    lock.waitLock(10000);
    const submissionCache = CacheService.getScriptCache();
    const submissionKey = "submission:" + String(payload.submission_id || "");
    if (!payload.submission_id || submissionCache.get(submissionKey)) {
      return jsonResponse({ ok: false, error: "duplicate" });
    }
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = spreadsheet.getSheetByName(SHEET_NAME);
    if (!sheet) sheet = spreadsheet.insertSheet(SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(HEADERS);
      sheet.setFrozenRows(1);
      sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold");
    } else {
      const existingWidth = sheet.getLastColumn();
      if (existingWidth < HEADERS.length) {
        sheet.getRange(1, existingWidth + 1, 1, HEADERS.length - existingWidth)
          .setValues([HEADERS.slice(existingWidth)]);
      }
    }

    sheet.appendRow([
      safeCell(payload.submitted_at),
      safeCell(payload.name),
      safeCell(payload.email),
      safeCell(payload.company),
      safeCell(payload.discussion_type),
      safeCell(payload.message),
      safeCell(payload.confirmed_no_confidential_data),
      safeCell(payload.submission_channel),
      safeCell(payload.attribution_source),
      safeCell(payload.campaign),
      safeCell(payload.demo_version),
      safeCell(payload.submission_id),
      safeCell(payload.role),
      safeCell(payload.billing_model),
      safeCell(payload.verification_method),
      safeCell(payload.evidence_location),
      safeCell(payload.commercial_action),
      safeCell(payload.feedback_area),
      safeCell(payload.open_to_call),
    ]);
    submissionCache.put(submissionKey, "1", 21600);

    return jsonResponse({ ok: true });
  } catch (error) {
    return jsonResponse({ ok: false, error: "submission_failed" });
  } finally {
    if (lock.hasLock()) lock.releaseLock();
  }
}
