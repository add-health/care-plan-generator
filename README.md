# Lifetime Health — Care Plan Generator

AI-powered physiotherapy care plan generator. Built on Lifetime Health's 24 condition protocol library.

## Project structure

```
care-plan-generator/
├── public/
│   └── index.html          ← Frontend (works standalone or served by Express)
├── server/
│   └── server.js           ← Express API proxy for Claude
├── pdf-generator/
│   └── generate_pdf.py     ← Patient PDF generator (Python/ReportLab)
├── scripts/
│   └── cloudflare-worker.js ← Alternative deployment (no server needed)
├── docs/
│   ├── spec-v1.2.docx      ← Product specification
│   └── protocols.json      ← Raw protocol data
├── package.json
├── railway.toml            ← Railway deployment config
└── README.md
```

---

## Option A — Local development (5 min)

### Prerequisites
- Node.js 18+
- An Anthropic API key (get one at console.anthropic.com)

### Steps

```bash
# 1. Install dependencies
npm install

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# 3. Start the server
npm start
# or for auto-reload during development:
npx nodemon server/server.js

# 4. Open in browser
open http://localhost:3000
```

---

## Option B — Deploy to Railway (30 min, shareable URL)

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Select your repo
4. Add the environment variables under Railway → Variables:

   | Variable | Required for | Value |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | plan generation | your Claude API key |
   | `GOOGLE_DRIVE_FOLDER_ID` | saving PDFs to Drive | the Drive folder ID |
   | `GOOGLE_CREDENTIALS_JSON` | saving PDFs to Drive | service account JSON, **base64-encoded** |

   `credentials.json` is gitignored and cannot be placed in the container, so on
   Railway the service account has to come through `GOOGLE_CREDENTIALS_JSON`.
   The server base64-decodes it before parsing, so encode the file first:

   ```bash
   base64 -i credentials.json
   ```

   Without it, `/save-pdf` falls back to reading `./credentials.json`, does not
   find it, and every Drive upload fails. Plan generation and the direct PDF
   download are unaffected.

5. Railway auto-deploys. You get a URL like `https://your-app.railway.app`

Share that URL with your physio test group — works on any device.

---

## Option C — Cloudflare Workers (no server needed)

1. Go to dash.cloudflare.com → Workers & Pages → Create Worker
2. Paste the contents of `scripts/cloudflare-worker.js`
3. Add environment variable: `ANTHROPIC_API_KEY` = your key
4. Deploy → copy your Worker URL (e.g. `https://care-plan.your-name.workers.dev`)
5. Open `public/index.html`, change line 12:
   ```javascript
   const API_ENDPOINT = 'https://care-plan.your-name.workers.dev';
   ```
6. Open the HTML file directly in browser — no server needed

---

## PDF generation

```bash
# Install dependency
pip install reportlab

# Generate sample PDF (TKR example)
python pdf-generator/generate_pdf.py

# Generate from JSON data
python pdf-generator/generate_pdf.py --json '{"patient":{...},"plan":{...},"output":"plan.pdf"}'
```

---

## Protocol library

All 24 Lifetime Health physiotherapy conditions are embedded in `public/index.html` (the `PROTOCOLS` array, line ~30). To update a protocol, edit that array directly.

When moving to production (admin console integration), the protocols should be loaded from the database via API instead.

---

## Architecture (production path)

```
Admin console (React)
  └── InitialAssessment component  ←  convert index.html to JSX
        └── POST /api/assessment/generate
              └── server.js (or existing backend)
                    └── Claude API
                          └── JSON plan → render in console + PDF
```

The React conversion is straightforward — all the logic in index.html maps 1:1 to React state and components. Hand the HTML to the dev team as the functional spec.

---

## What to test with physios

1. Fill in a real patient you saw recently
2. Check: does the plan match what you would have written?
3. Are exercises clinically appropriate for the condition?
4. Does high pain (7–9/10) produce a conservative Phase 1?
5. Do comorbidities show up correctly? (add Diabetes — glucose monitoring should appear)
6. Is the language right for patients?

Collect feedback → iterate on the AI prompt in `server.js` (the `systemPrompt` variable).

---

## Customisation

**Add a condition:** Add to the `PROTOCOLS` array in `index.html` and `server/server.js`

**Change the AI prompt:** Edit `systemPrompt` in `server/server.js`

**Add a form field:** Add to the relevant `renderStep` function in `index.html`

**Change colours:** Edit the `B` object at the top of `index.html`

---

## Files produced in this project

| File | Description |
|---|---|
| `public/index.html` | Full working frontend prototype |
| `server/server.js` | Express API proxy |
| `pdf-generator/generate_pdf.py` | Patient PDF generator |
| `scripts/cloudflare-worker.js` | Serverless alternative |
| `docs/LH_CarePlan_Spec_v1.2.docx` | Product specification |

---

*Lifetime Health — Internal prototype. Not for patient distribution.*
