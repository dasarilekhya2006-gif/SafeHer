# SafeHer — Women Safety Route Navigation (Flask Backend)

SafeHer is a comprehensive, production-grade navigation platform designed for women traveling alone. The platform evaluates route safety using multi-factor environmental and situational parameters (street illumination, historical crime, crowd presence, police proximity, safety zones, and time of day) to recommend the safest path home.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.8+** installed on your system.

### Step 1: Install Dependencies
Open your terminal (PowerShell, Command Prompt, or Bash) in this project directory and run:

```bash
pip install -r requirements.txt
```

> **Note:** The backend only requires `Flask` and `Flask-Cors`. If `Flask-Cors` is not installed, the backend includes automatic CORS header fallback.

### Step 2: Run the Backend Server
You can launch the server using either:

```bash
python run.py
```
*or*
```bash
python app.py
```

You will see:
```text
========================================================================
   🛡️   SafeHer — Women Safety Route Navigation Backend
========================================================================
✓ SQLite Database (safety.db) initialized and sample data verified.
✓ Flask application loaded successfully.

Starting local server on http://127.0.0.1:5000 ...
```

### Step 3: Open the SafeHer Web Application
You have two easy ways to access the app:
1. **Via the Flask Web Server (Recommended)**:
   Navigate to [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in any modern web browser.
2. **Via Standalone File**:
   Double click `index.html` or run through Live Server. `app.js` will automatically communicate with the backend at `http://127.0.0.1:5000/api`.

When the backend is active, the top-left indicator will show:
`🛡️ Safety Shield Active (API Connected)`

---

## 📁 Project Architecture

```
women safety/
├── app.py              # Main Flask REST API application & static file server
├── database.py         # SQLite database schema, initialization & query helpers
├── safety_engine.py    # Multi-factor safety scoring engine & route generator
├── run.py              # Beginner-friendly server launcher with health diagnostics
├── requirements.txt    # Python package dependencies
├── test_api.py         # Automated test suite for all 6 API endpoints
├── API_DOCS.md         # Full REST API endpoint reference & curl commands
├── README.md           # This documentation guide
├── index.html          # Frontend web application layout (HTML5 + Leaflet)
├── app.js              # Frontend controller & interactive Leaflet map logic
└── style.css           # Modern dark-mode styling with glassmorphism
```

---

## 🛡️ Multi-Factor Safety Scoring Model

Every route is evaluated using 7 key safety dimensions:

| Factor | Weight | Evaluation Criteria |
|---|---|---|
| **Street Lighting** | **25%** | Percentage of the road equipped with high-intensity LED illumination. |
| **Crime Rate** | **25%** | Inverted incident rate ($100 - \text{Crime Index}$) based on reported issues and CCTV coverage. |
| **Crowd & Commercial Activity** | **20%** | Density of open 24/7 pharmacies, convenience stores, cafes, and active transit hubs. |
| **Police Proximity** | **15%** | Distance to nearest active police assistance booth or transit police desk. |
| **Safe & Risky Zones** | **15%** | Safety bonus for traversing verified safe watch zones; penalty for risky unmonitored alleys. |
| **Time of Day** | **Dynamic** | Between 20:00 and 05:00 (night), unlit routes suffer heavy point deductions, while well-lit corridors retain high confidence. |

### Safety Tiers
- **85 – 100** : 🟢 **SAFEST RECOMMENDED ROUTE** (Wide avenues, LED lit, active foot traffic, police post).
- **60 – 84** : 🟡 **MODERATE SAFETY ROUTE** (Transit avenue along metro pillars, moderate crowd).
- **Below 60** : 🔴 **HIGH RISK — NOT RECOMMENDED** (Unlit alleyways, blind corners, isolated warehouses).

---

## 📡 REST API Summary

All endpoints return JSON responses. See [API_DOCS.md](API_DOCS.md) for full payloads and curl examples.

- `GET /api/health` — Check server status & SQLite database connection.
- `GET /api/safety-zones` — Retrieve green safe corridors and red risky zones.
- `GET /api/police-stations` — Retrieve police assistance booths and phone helplines.
- `POST /api/routes` — Generate routes with multi-factor safety evaluation.
- `POST /api/sos` — Record emergency panic alert with GPS coordinates into SQLite.
- `POST /api/chat` — SafeHer AI Assistant providing navigation safety advice.

---

## 💾 SQLite Database (`safety.db`)

The backend automatically creates and seeds `safety.db` on startup:

1. **`routes`** — Pre-configured verified routes with turn-by-turn guidance and factor metrics.
2. **`safety_zones`** — Safe zones and risky zones with coordinates and radiuses.
3. **`police_stations`** — Police assistance booths and helpline telephone numbers.
4. **`sos_logs`** — Audit log of all emergency SOS events, coordinates, and contact details.
5. **`chat_logs`** — Log of user safety questions and AI recommendations.

---

## 🧪 Running Automated Tests

Run the included automated test suite to verify all endpoints:

```bash
python test_api.py
```

Expected output:
```text
=================================================================
  🧪 Running SafeHer API Test Suite
=================================================================

[1/6] Testing GET /api/health ... PASSED ✓ (status: healthy, db: connected)
[2/6] Testing GET /api/safety-zones ... PASSED ✓ (retrieved 5 zones)
[3/6] Testing GET /api/police-stations ... PASSED ✓ (retrieved 3 police posts)
[4/6] Testing POST /api/routes ... PASSED ✓ (safest route: 'Main Boulevard Safe Corridor', score: 94/100)
[5/6] Testing POST /api/sos ... PASSED ✓ (created incident #1, nearest police: Police Assistance Booth #4)
[6/6] Testing POST /api/chat ... PASSED ✓ (AI advice generated, 3 recommendations)

=================================================================
  Summary: 6/6 Tests Passed Successfully! (100%)
=================================================================
```

---

## 💡 Key Interactive Features in Web App

1. **Safest Route Recommendation**: Highlights the 94/100 rated Boulevard corridor with green outer glow.
2. **Interactive Route Selection**: Click any route card or polyline to inspect the 4-meter breakdown (Lighting, Crime, Crowd, Police).
3. **Turn-by-Turn Safety Navigation**: Tap **Start Safe Route** to launch the live simulation HUD with next-turn safety badges.
4. **Emergency SOS Countdown & Siren**: 3-second abort countdown, followed by high-decibel audio siren and real dispatch to `POST /api/sos`.
5. **AI Safety Assistant**: Tap the chat icon in the header to ask questions about route safety, police stations, or late-night travel tips.
6. **Swap Destination**: Tap the swap button to swap start and destination and dynamically recalculate paths.
7. **Offline Graceful Fallback**: If the Flask backend is not yet started, the frontend operates seamlessly using cached safety data without crashing.
