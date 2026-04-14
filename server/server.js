const express = require('express');
const fetch   = require('node-fetch');
const cors    = require('cors');
const path    = require('path');
const { PythonShell } = require('python-shell');

const app = express();
app.use(express.json({ limit: '1mb' }));
app.use(cors());

// ── Health check ────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ status: 'ok', version: '1.0.0' }));

// ── Claude proxy ────────────────────────────────────────────────────
app.post('/generate-plan', async (req, res) => {
  if (!process.env.ANTHROPIC_API_KEY) {
    return res.status(500).json({ error: 'ANTHROPIC_API_KEY not set in environment' });
  }

  try {
    const { system, messages } = req.body;

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type':    'application/json',
        'x-api-key':       process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model:      'claude-sonnet-4-6',
        max_tokens: 8000,
        system,
        messages
      })
    });

    const data = await response.json();

    if (!response.ok) {
      console.error('Claude API error:', data);
      return res.status(response.status).json({ error: data.error?.message || 'Claude API error' });
    }

    res.json(data);

  } catch (err) {
    console.error('Server error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ── Google Drive PDF upload ─────────────────────────────────────────
app.post('/save-pdf', async (req, res) => {
  const { patient, plan } = req.body;

  const timestamp = new Date().toISOString().slice(0, 10);
  const safeName = (patient.name || 'Patient').replace(/\s+/g, '_');
  const safeCondition = (patient.condition || 'Plan').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 20);
  const filename = `${safeName}_${safeCondition}_${timestamp}.pdf`;
  const outputPath = path.join(__dirname, '..', 'temp', filename);

  const fs = require('fs');
  if (!fs.existsSync(path.join(__dirname, '..', 'temp'))) {
    fs.mkdirSync(path.join(__dirname, '..', 'temp'));
  }

  try {
    // Step 1: Generate PDF via Python
    await new Promise((resolve, reject) => {
      const shell = new PythonShell(
        path.join(__dirname, '..', 'pdf-generator', 'generate_pdf.py'),
        {
          args: ['--json', JSON.stringify({ patient, plan, output: outputPath })],
          pythonPath: process.env.PYTHON_PATH || 'python3'
        }
      );
      shell.on('error', reject);
      shell.end((err) => err ? reject(err) : resolve());
    });

    // Step 2: Upload to Google Drive
    const { google } = require('googleapis');
    const auth = new google.auth.GoogleAuth({
      keyFile: path.join(__dirname, '..', 'credentials.json'),
      scopes: ['https://www.googleapis.com/auth/drive.file']
    });
    const drive = google.drive({ version: 'v3', auth });

    const fileStream = fs.createReadStream(outputPath);
    const uploaded = await drive.files.create({
      requestBody: {
        name: filename,
        mimeType: 'application/pdf',
        parents: [process.env.GOOGLE_DRIVE_FOLDER_ID]
      },
      media: {
        mimeType: 'application/pdf',
        body: fileStream
      },
      fields: 'id, webViewLink'
    });

    // Step 3: Make file readable by anyone with link
    await drive.permissions.create({
      fileId: uploaded.data.id,
      requestBody: {
        role: 'reader',
        type: 'anyone'
      }
    });

    // Step 4: Clean up temp file
    fs.unlinkSync(outputPath);

    res.json({
      success: true,
      filename,
      driveLink: uploaded.data.webViewLink,
      fileId: uploaded.data.id
    });

  } catch (err) {
    console.error('PDF save error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Serve frontend ──────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, '..', 'public')));
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Care Plan Generator running on port ${PORT}`));
