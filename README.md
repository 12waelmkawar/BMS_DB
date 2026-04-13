# BMS Test Intelligence Dashboard

A full-stack web application that monitors **BMW BMS (Battery Management System)** test results, integrates with Jira for bug tracking, and provides real-time traceability for automotive SW engineers and managers.

---

## Tech Stack

| Layer      | Technology                                         |
|------------|----------------------------------------------------|
| Frontend   | **Vue 3** + **TypeScript** + Vite + Pinia + ECharts |
| Backend    | **Python FastAPI** + uvicorn                       |
| Database   | **PostgreSQL** (psycopg2)                          |
| File parse | lxml, BeautifulSoup4, openpyxl                     |
| Jira       | jira Python package                                |
| Watcher    | watchdog + schedule                                |

---

## Prerequisites — Tools to Install

### 1. PostgreSQL

| OS      | Command |
|---------|---------|
| Ubuntu/Debian | `sudo apt update && sudo apt install -y postgresql postgresql-contrib` |
| macOS (Homebrew) | `brew install postgresql@16 && brew services start postgresql@16` |
| Windows | Download from https://www.postgresql.org/download/windows/ and run the installer |

### 2. Python 3.11+

| OS | Command |
|----|---------|
| Ubuntu/Debian | `sudo apt install -y python3.11 python3.11-venv python3-pip` |
| macOS | `brew install python@3.11` |
| Windows | Download from https://www.python.org/downloads/ |

### 3. Node.js 20+ and npm

| OS | Command |
|----|---------|
| Ubuntu/Debian | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash - && sudo apt install -y nodejs` |
| macOS | `brew install node@20` |
| Windows | Download from https://nodejs.org/ |

### 4. Git

```bash
# Ubuntu/Debian
sudo apt install -y git

# macOS
brew install git

# Windows: https://git-scm.com/download/win
```

---

## Step-by-Step Deployment on localhost

### Step 1 — Clone the repository

```bash
git clone https://github.com/12waelmkawar/BMS_DB.git
cd BMS_DB
```

### Step 2 — Create the PostgreSQL database and user

```bash
# Switch to postgres superuser
sudo -u postgres psql

# Inside psql prompt:
CREATE USER bms_user WITH PASSWORD 'bms_password';
CREATE DATABASE bms_intelligence OWNER bms_user;
GRANT ALL PRIVILEGES ON DATABASE bms_intelligence TO bms_user;
\q
```

> **Windows**: Open "pgAdmin 4" or "SQL Shell (psql)" from the Start menu and run the same commands.

### Step 3 — Configure backend environment

```bash
cd backend
cp .env.example .env
```

Open `.env` in your editor and fill in the values:

```dotenv
# PostgreSQL — adjust if you used different credentials in Step 2
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bms_intelligence
POSTGRES_USER=bms_user
POSTGRES_PASSWORD=bms_password

# Jira (optional — leave blank to skip Jira polling in demo mode)
JIRA_URL=https://jira.bmw.com
JIRA_USER=engineer@bmw.com
JIRA_TOKEN=your_jira_api_token_here
JIRA_PROJECT=BMS

# Network drive path (optional — leave blank for demo mode)
NETWORK_DRIVE_PATH=\\NETWORK\xchange
```

### Step 4 — Install Python dependencies

```bash
# Still inside the backend/ directory
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows PowerShell

pip install -r requirements.txt
```

### Step 5 — Start the backend API

```bash
# Inside backend/ with venv activated
python main.py
```

You should see:

```
INFO:     Started server process [...]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The API is now live at **http://localhost:8000**.  
Interactive API docs: **http://localhost:8000/docs**

### Step 6 — Load demo data (optional but recommended for first run)

Open a second terminal and run:

```bash
curl -X POST http://localhost:8000/api/seed-demo
```

Or simply click the **⚡ Load Demo Data** button in the dashboard after the frontend starts.

### Step 7 — Install frontend dependencies

Open a **new terminal** (keep the backend terminal running):

```bash
cd frontend
npm install
```

### Step 8 — Start the frontend dev server

```bash
npm run dev
```

You should see:

```
  VITE v5.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

Open **http://localhost:5173/** in your browser. 🎉

---

## Project Structure

```
BMS_DB/
├── backend/
│   ├── main.py          ← FastAPI app + all API endpoints + demo seed
│   ├── watcher.py       ← Jira poller + watchdog file watcher + fix validator
│   ├── parsers.py       ← TRF (XML) / HTML / XLSX report parsers
│   ├── database.py      ← PostgreSQL schema + query helpers
│   ├── models.py        ← Pydantic response models
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── main.ts            ← Vue app entry point
    │   ├── App.vue            ← Root component
    │   ├── style.css          ← Global dark-theme CSS
    │   ├── types/index.ts     ← TypeScript interfaces
    │   ├── api/index.ts       ← Axios API client
    │   ├── stores/bms.ts      ← Pinia store (state + actions)
    │   ├── router/index.ts    ← Vue Router
    │   ├── views/
    │   │   └── Dashboard.vue  ← 5-tab main dashboard
    │   └── components/
    │       ├── KpiCard.vue
    │       ├── AlertBanner.vue
    │       ├── StatusBadge.vue
    │       ├── JiraBadge.vue
    │       ├── TicketModal.vue
    │       └── DomainTable.vue
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── index.html
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET  | `/api/releases` | List all SOPs + releases |
| GET  | `/api/results/{sop}/{release}` | TC results for a release |
| GET  | `/api/tickets` | All Jira tickets (sorted by severity) |
| GET  | `/api/tickets/{tc_id}` | Single ticket |
| GET  | `/api/fix-alerts` | All FIX_FAILED tickets |
| GET  | `/api/stats/{sop}/{release}` | Pass/fail counts per domain |
| GET  | `/api/traceability` | Failing TCs with ticket + fix status |
| GET  | `/api/diff/{sop}/{rel_a}/{rel_b}` | Changed TCs between two releases |
| POST | `/api/seed-demo` | Load mock demo data |

---

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Overview** | KPI cards, bar chart, donut chart, domain table, fix claims panel |
| **Traceability** | Failing TCs grouped by domain with result-per-release matrix |
| **TC Drill-Down** | Filter TCs by domain for the selected release |
| **Release Diff** | Compare two releases — see regressions and fixes |
| **All Tickets** | Full Jira ticket table sorted by severity |

Click any **Jira badge** anywhere in the dashboard to open the **Ticket Modal** with full details and direct link to Jira.

---

## Production Build

```bash
# Build the frontend
cd frontend
npm run build
# Output is in frontend/dist/

# Serve the backend with a production ASGI server
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

To serve the frontend static files from FastAPI (single deployment):

```python
# Add to main.py after app definition:
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `bms_intelligence` | Database name |
| `POSTGRES_USER` | `bms_user` | Database user |
| `POSTGRES_PASSWORD` | `bms_password` | Database password |
| `JIRA_URL` | — | Jira server URL |
| `JIRA_USER` | — | Jira username / email |
| `JIRA_TOKEN` | — | Jira API token |
| `JIRA_PROJECT` | `BMS` | Jira project key |
| `NETWORK_DRIVE_PATH` | — | UNC path to ECU-Test reports |
| `PORT` | `8000` | FastAPI listen port |

---

## Troubleshooting

**PostgreSQL connection refused**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql       # Linux
brew services info postgresql@16       # macOS
# Windows: check Services app for "postgresql-x64-16"
```

**`psycopg2` install fails**
```bash
# Ubuntu — install system lib first
sudo apt install -y libpq-dev
pip install psycopg2-binary
```

**CORS error in browser**
The FastAPI backend allows all origins by default (`allow_origins=["*"]`). If you change the backend port, update `vite.config.ts` proxy target accordingly.

**Vite proxy not working**
Make sure the backend is running on port 8000 before starting `npm run dev`.