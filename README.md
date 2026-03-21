# AI Adaptive Onboarding Engine

An AI-powered onboarding assistant that compares a candidate resume against a job description, identifies skill gaps, and generates an adaptive learning roadmap with reasoning trace.

## Features

- Upload **resume** and **job description** as `.txt` files
- Extracts candidate/role summary
- Computes a **skill gap matrix**
- Generates an **adaptive weekly roadmap**
- Persists generated plans in SQLite
- Returns structured reasoning trace for explainability

---

## Tech Stack

### Frontend
- React + TypeScript
- Vite
- Fetch API

### Backend
- FastAPI
- SQLAlchemy
- SQLite
- Uvicorn

### Infra
- Docker + Docker Compose

---

## Project Structure

```text
.
├── backend
│   ├── app
│   │   ├── core
│   │   ├── models
│   │   ├── routes
│   │   ├── schemas
│   │   ├── services
│   │   ├── init_db.py
│   │   └── main.py
│   ├── data
│   ├── requirements.txt
│   └── Dockerfile
├── frontend
│   ├── src
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
└── docker-compose.yml
```

---

## API Contract

### `POST /api/generate-plan`

Accepts multipart form-data:

- `resume` (file, `.txt`)
- `job_description` (file, `.txt`)

Returns JSON with:
- `candidate_name`
- `role_title`
- `skill_gaps`
- `roadmap`
- `reasoning_trace`
- `metrics`

### `GET /health`
Returns service health status.

---

## Run with Docker (Recommended)

### Prerequisites
- Docker Desktop running
- WSL2 integration enabled (Windows)

### 1) Create backend env file

Create `backend/.env`:

```env
DATABASE_URL=sqlite:////app/data/onboarding.db
CORS_ORIGINS=http://localhost:5173
```

### 2) Start services

```bash
docker compose down -v
docker compose up --build
```

### 3) Open apps
- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health

---

## Run Locally (Without Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python -m app.init_db
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

---

## Sample Test Files

### `resume.txt`
```txt
Riya Sharma
Data Analyst with 2 years of experience in Python, SQL, Statistics, and Data Visualization.
Built ML prototypes using scikit-learn and collaborated with business stakeholders.
Familiar with Docker basics and CI/CD concepts.
```

### `jd.txt`
```txt
Machine Learning Engineer
Must have strong Python, SQL, Machine Learning, and MLOps.
Deep Learning knowledge (PyTorch/TensorFlow) required.
Nice to have data visualization and communication.
```

---

## Quick API Test (PowerShell)

```powershell
curl.exe -X POST "http://localhost:8000/api/generate-plan" `
  -F "resume=@resume.txt" `
  -F "job_description=@jd.txt"
```

---

## Troubleshooting

### 1) `Failed to fetch` in frontend
- Ensure backend is reachable: http://localhost:8000/health
- Check browser Network tab request URL
- Verify frontend API base is `http://localhost:8000`

### 2) `sqlite3.OperationalError: no such table: plans`
- Ensure DB initialization runs:
  - `python -m app.init_db` (local), or
  - Docker backend command includes init step before `uvicorn`

### 3) `unable to open database file`
- Ensure backend data directory exists and is mounted:
  - host: `./backend/data`
  - container: `/app/data`
- Ensure `DATABASE_URL=sqlite:////app/data/onboarding.db`

### 4) Docker daemon/engine not found
- Start Docker Desktop and wait for **Engine running**

---

## Demo Flow (2 Minutes)

1. Open frontend and upload resume + JD text files  
2. Click **Generate Adaptive Plan**  
3. Show:
   - Skill gap table
   - Weekly roadmap
   - Reasoning trace
4. Explain how roadmap changes with different candidate profiles

---

## Future Improvements

- PDF/DOCX parsing support
- LLM-based semantic skill extraction
- Personalized resource recommendations (courses/videos)
- Authentication and user dashboard
- PostgreSQL + plan history analytics

---
