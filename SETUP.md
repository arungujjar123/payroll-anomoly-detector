# Setup Guide

This guide explains how to run the Payroll Anomaly Detector locally in under 5 minutes.

---

## Prerequisites

* Python 3.11+
* Node.js 18+
* An ERPNext instance with Payroll data (API key + secret)
* A Groq API key

---

## 1. Clone the repository

```bash
git clone https://github.com/arungujjar123/payroll-anomoly-detector.git
cd payroll-anomoly-detector
```

---

## 2. Create and activate a virtual environment

**Mac / Linux**

```bash
python -m venv venv
source venv/bin/activate
```

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure environment variables

Create a `.env` file inside the `backend/` directory (the app is started from
there, so that is where `pydantic-settings` looks for it).

Copy the contents of `.env.example` and fill in your own values:

```bash
cp .env.example backend/.env
```

```ini
ERPNEXT_BASE_URL=https://yoursite.erpnext.com
ERPNEXT_API_KEY=abc123...
ERPNEXT_API_SECRET=xyz789...

GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

ANOMALY_THRESHOLD_PCT=15.0

APP_VERSION=1.0.0
APP_ENV=development
```

---

## 5. Run the backend

```bash
cd backend
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`.
Interactive API docs: `http://localhost:8000/docs`

---

## 6. Run the frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

The frontend calls `http://localhost:8000/api/v1` by default. To point it
somewhere else, set `VITE_API_BASE` in `frontend/.env`:

```ini
VITE_API_BASE=http://localhost:8000/api/v1
```

---

## 7. Verify the backend is healthy

Open `http://localhost:8000/api/v1/health`

Expected response:

```json
{
  "service": "Payroll Anomaly Detector",
  "version": "1.0.0",
  "status": "ok",
  "environment": "development"
}
```

---

## 8. Run the tests

The rule engine is covered by unit tests that need no ERPNext instance and no
LLM key:

```bash
pip install -r requirements-dev.txt
cd backend
pytest
```

See [Testing](README.md#testing) for what is covered and why.

---

## 9. Example workflow

1. Open the frontend application
2. Enter a payroll review request
3. Run the payroll review
4. Review the detected anomalies in the HITL preview
5. Approve or cancel the HITL checkpoint
6. The final audit report is generated on approval

**Example prompt**

```text
Review this month's payroll data and flag anything unusual.
```

---

## API Endpoints

| Endpoint          | Method | Purpose                  |
| ----------------- | ------ | ------------------------ |
| `/api/v1/health`  | GET    | Health check             |
| `/api/v1/run`     | POST   | Start payroll audit      |
| `/api/v1/confirm` | POST   | Confirm or cancel HITL   |
| `/api/v1/history` | GET    | Retrieve session history |

---

## Troubleshooting

**`ValidationError` on startup** — `.env` is missing or is not inside
`backend/`. All four credentials (`ERPNEXT_BASE_URL`, `ERPNEXT_API_KEY`,
`ERPNEXT_API_SECRET`, `GROQ_API_KEY`) are required and have no defaults.

**`503 ERPNext API error`** — the backend reached ERPNext but ERPNext rejected
the call. Check the API key/secret pair and that the user has read access to
the Salary Slip doctype.

**`no_data` response** — there are no salary slips for the current or previous
calendar month in ERPNext. The comparison window is derived from today's date.

---

## Notes

* The frontend communicates only with the FastAPI backend.
* No direct ERPNext calls are made from the frontend.
* Payroll anomaly detection logic is fully deterministic.
* Agno coordinates the specialist agents for modular analysis.
