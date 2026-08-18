const express = require('express');
const fetch   = require('node-fetch');
const cors    = require('cors');
const path    = require('path');
const fs      = require('fs');
const { PythonShell } = require('python-shell');

// On Railway the venv is built at /app/.venv; locally fall back to system python3
const VENV_PYTHON = '/app/.venv/bin/python3';
const PYTHON_PATH = process.env.PYTHON_PATH || (fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3');

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

  if (!fs.existsSync(path.join(__dirname, '..', 'temp'))) {
    fs.mkdirSync(path.join(__dirname, '..', 'temp'));
  }

  try {
    const patientForPdf = {
      name:       patient.name,
      age:        patient.age,
      gender:     patient.gender,
      zone:       patient.zone,
      condition:  patient.condition,
      pain_score: parseInt(patient.painScore || patient.pain_score || 0),
      date:       'Generated ' + new Date().toLocaleDateString('en-GB', {
                    day: 'numeric', month: 'short', year: 'numeric'
                  })
    };

    // Step 1: Generate PDF via Python
    await new Promise((resolve, reject) => {
      const shell = new PythonShell(
        path.join(__dirname, '..', 'pdf-generator', 'generate_pdf.py'),
        {
          args: ['--json', JSON.stringify({ patient: patientForPdf, plan, output: outputPath })],
          pythonPath: PYTHON_PATH
        }
      );
      shell.on('error', reject);
      shell.end((err) => err ? reject(err) : resolve());
    });

    // Step 2: Upload to Google Drive
    const { google } = require('googleapis');
    let authConfig;
    if (process.env.GOOGLE_CREDENTIALS_JSON) {
      const creds = JSON.parse(
        Buffer.from(process.env.GOOGLE_CREDENTIALS_JSON, 'base64').toString()
      );
      authConfig = { credentials: creds, scopes: ['https://www.googleapis.com/auth/drive.file'] };
    } else {
      authConfig = { keyFile: path.join(__dirname, '..', 'credentials.json'), scopes: ['https://www.googleapis.com/auth/drive.file'] };
    }
    const auth = new google.auth.GoogleAuth(authConfig);
    const drive = google.drive({ version: 'v3', auth });

    console.log('Drive folder ID:', process.env.GOOGLE_DRIVE_FOLDER_ID);

    const fileStream = fs.createReadStream(outputPath);
    const uploaded = await drive.files.create({
      supportsAllDrives: true,
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
      supportsAllDrives: true,
      fileId: uploaded.data.id,
      requestBody: {
        role: 'reader',
        type: 'anyone'
      }
    });

    res.json({
      success: true,
      filename,
      driveLink: uploaded.data.webViewLink,
      fileId: uploaded.data.id
    });

  } catch (err) {
    console.error('PDF save error:', err);
    res.status(500).json({ error: err.message });
  } finally {
    // Runs whether or not the Drive upload threw. Previously this sat at the end
    // of the try, so an expired service account or a quota error left the file
    // behind for the life of the container.
    if (fs.existsSync(outputPath)) fs.unlinkSync(outputPath);
  }
});

// ── PDF download (same Python generator, no Drive upload) ───────────
app.post('/download-pdf', async (req, res) => {
  const { patient, plan } = req.body;

  const timestamp = new Date().toISOString().slice(0, 10);
  const safeName = (patient.name || 'Patient').replace(/\s+/g, '_');
  const safeCondition = (patient.condition || 'Plan').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 20);
  const filename = `${safeName}_${safeCondition}_${timestamp}.pdf`;

  const tempDir = path.join(__dirname, '..', 'temp');
  if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);
  const outputPath = path.join(tempDir, filename);

  try {
    const patientForPdf = {
      name:       patient.name,
      age:        patient.age,
      gender:     patient.gender,
      zone:       patient.zone,
      condition:  patient.condition,
      pain_score: parseInt(patient.painScore || patient.pain_score || 0),
      date:       'Generated ' + new Date().toLocaleDateString('en-GB', {
                    day: 'numeric', month: 'short', year: 'numeric'
                  })
    };

    await new Promise((resolve, reject) => {
      const shell = new PythonShell(
        path.join(__dirname, '..', 'pdf-generator', 'generate_pdf.py'),
        {
          args: ['--json', JSON.stringify({ patient: patientForPdf, plan, output: outputPath })],
          pythonPath: PYTHON_PATH
        }
      );
      shell.on('error', reject);
      shell.end((err) => err ? reject(err) : resolve());
    });

    res.download(outputPath, filename, (err) => {
      if (fs.existsSync(outputPath)) fs.unlinkSync(outputPath);
    });
  } catch (err) {
    console.error('Download error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Caregiver PDF download (separate generator, patient-facing document) ──
app.post('/download-caregiver-pdf', async (req, res) => {
  const { patient, plan } = req.body;

  const timestamp = new Date().toISOString().slice(0, 10);
  const safeName = (patient.name || 'Patient').replace(/\s+/g, '_');
  const safeType = (patient.care_type || 'CarePlan').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 20);
  const filename = `${safeName}_${safeType}_${timestamp}.pdf`;

  const tempDir = path.join(__dirname, '..', 'temp');
  if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);
  const outputPath = path.join(tempDir, filename);

  try {
    const patientForPdf = {
      name:         patient.name,
      age:          patient.age,
      gender:       patient.gender,
      zone:         patient.zone,
      care_type:    patient.care_type,
      service_tier: patient.service_tier,
      start_date:   patient.start_date,
      assessed_by:  patient.assessed_by,
      // Emergency details come from the assessment, never from the model
      emergency_name:  patient.emergency_name,
      emergency_phone: patient.emergency_phone,
      doctor_name:     patient.doctor_name,
      doctor_phone:    patient.doctor_phone,
      date:         'Generated ' + new Date().toLocaleDateString('en-GB', {
                      day: 'numeric', month: 'short', year: 'numeric'
                    })
    };

    await new Promise((resolve, reject) => {
      const shell = new PythonShell(
        path.join(__dirname, '..', 'pdf-generator', 'generate_caregiver_pdf.py'),
        {
          args: ['--json', JSON.stringify({ patient: patientForPdf, plan, output: outputPath })],
          pythonPath: PYTHON_PATH
        }
      );
      shell.on('error', reject);
      shell.end((err) => err ? reject(err) : resolve());
    });

    res.download(outputPath, filename, (err) => {
      if (fs.existsSync(outputPath)) fs.unlinkSync(outputPath);
    });
  } catch (err) {
    console.error('Caregiver download error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Serve frontend ──────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, '..', 'public')));

app.get('/caregiver', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'caregiver.html'));
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Care Plan Generator running on port ${PORT}`));
