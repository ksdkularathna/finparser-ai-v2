# Bank Statement Extractor

A standalone application that converts bank statement PDFs into organized Excel spreadsheets.

## Features

- 📄 **PDF Extraction** - Uses pdfplumber for accurate text and table extraction
- 💰 **Currency Parsing** - Handles formats like `$1,234.56` and accounting negatives `(50.00)`
- 📊 **Excel Output** - Generates formatted Excel with Summary and Transactions sheets
- 🎨 **Premium UI** - Modern dark theme with drag-and-drop file upload

## Quick Start

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run the application
python -m uvicorn main:app --port 8000
```

Open http://localhost:8000 in your browser.

## Project Structure

```
backend/
├── main.py           # FastAPI app + extraction logic
├── requirements.txt  # Python dependencies
└── static/           # Built React frontend
    ├── index.html
    └── assets/
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the web UI |
| `/convert` | POST | Upload PDF, returns Excel file |

## Tech Stack

- **Backend**: Python, FastAPI, pdfplumber, pandas
- **Frontend**: React, Vite
- **Styling**: Custom CSS with glassmorphism effects
