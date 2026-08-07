# Free Google Sheet contact storage

Evidue can store contact-form responses in a private Google Sheet without a
paid form service. The browser sends the form to Evidue, and the Evidue backend
forwards the validated response to a Google Apps Script web app.

The Apps Script deployment URL and shared secret are server-only values. Never
place either value in a `VITE_` variable or commit them to the repository. The
backend uses certificate-verified TLS 1.2 or newer, refuses HTTP downgrades and
off-domain redirects, and signs each submission with HMAC-SHA256. The script
rejects altered signatures and submissions older than five minutes.

## 1. Create the private Sheet

1. Create a Google Sheet named `Evidue contact responses`.
2. Keep its sharing setting **Restricted** and grant access only to people who
   should see contact submissions.
3. In that Sheet, select **Extensions → Apps Script**.
4. Replace the editor contents with
   [`integrations/google-sheets/Code.gs`](../integrations/google-sheets/Code.gs).
5. Save the Apps Script project as `Evidue contact intake`.

The script creates a `Contact submissions` tab and its header row on the first
successful submission. It also escapes values that Google Sheets could treat as
formulas and rejects duplicate submission IDs for six hours.

## 2. Create the shared secret

Generate a random secret locally:

```bash
openssl rand -hex 32
```

Copy the value. In Apps Script, open **Project Settings → Script Properties**
and add:

```text
Property: EVIDUE_CONTACT_SECRET
Value: the generated secret
```

## 3. Deploy the Apps Script web app

1. Select **Deploy → New deployment**.
2. Choose **Web app**.
3. Set **Execute as** to **Me**.
4. Set access to **Anyone** so the Evidue server can call it without a Google
   login. The shared secret still prevents unauthorized writes.
5. Select **Deploy**, authorize the script, and copy the URL ending in `/exec`.

Do not use the `/dev` test URL; it only works for script editors.

## 4. Configure Evidue

Set these backend environment variables in Railway or the deployment platform:

```text
EVIDUE_CONTACT_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/DEPLOYMENT_ID/exec
EVIDUE_CONTACT_SHEET_SECRET=the_same_generated_secret
```

Redeploy Evidue after saving the variables. Do not add these values as Docker
build arguments.

## 5. Verify

Submit a non-sensitive test response through `/contact`. Confirm that:

- the page shows `Response received.`;
- a `Contact submissions` tab exists in the private Sheet;
- one row contains the test response and a UTC submission timestamp;
- the shared secret does not appear in the Sheet or browser network payload.
- repeating the same signed test envelope is rejected as a duplicate.

If the form reports that storage is not configured, confirm both environment
variables are present. If it reports a rejected request, confirm the Script
Property and backend secret match exactly and that the latest script version is
deployed.

## Cost and limits

Google Apps Script and Google Sheets can be used with a consumer Google account
without adding a paid service to Evidue. They are subject to Google's daily
quotas and limits, which can change. This setup is appropriate for low-volume
beta contact intake, not a high-volume public form service.

Official references:

- [Deploy an Apps Script web app](https://developers.google.com/apps-script/guides/web)
- [Current Apps Script quotas](https://developers.google.com/apps-script/guides/services/quotas)
