# SafeHer — Backend REST API Documentation

The **SafeHer** backend is a Python Flask REST API designed to evaluate, rank, and serve safe routes for women traveling alone. It calculates real-time multi-factor safety scores, provides verified safe havens and police stations, records emergency SOS panic alerts into SQLite, and provides an AI safety companion.

**Base URL**: `http://127.0.0.1:5000`

---

## Table of Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check & SQLite database connectivity status |
| `GET` | `/api/safety-zones` | Retrieve safe commercial corridors & risky low-lit zones |
| `GET` | `/api/police-stations` | Retrieve police booths, transit police, & emergency desks |
| `POST` | `/api/routes` | Calculate candidate routes with multi-factor safety scoring |
| `POST` | `/api/sos` | Trigger an emergency SOS panic alert & locate nearest police unit |
| `POST` | `/api/chat` | AI Women Safety Assistant advice & de-escalation tips |

---

## 1. GET `/api/health`

Checks whether the Flask API server and SQLite database are operational.

### Response `200 OK`
```json
{
  "status": "healthy",
  "service": "SafeHer Backend API",
  "version": "1.0.0",
  "database": "connected",
  "timestamp": "2026-09-21T08:15:30.123456Z"
}
```

### Example `curl`
```bash
curl -X GET http://127.0.0.1:5000/api/health
```

---

## 2. GET `/api/safety-zones`

Returns geographic circles representing verified safe corridors (green) and high-risk / low-lit unmonitored zones (red) with radius in meters.

### Response `200 OK`
```json
{
  "status": "success",
  "count": 5,
  "data": [
    {
      "id": 1,
      "lat": 28.6365,
      "lng": 77.2240,
      "radius": 420,
      "type": "safe",
      "title": "Grand Boulevard Commercial Corridor",
      "desc": "High foot traffic, 24/7 supermarkets, LED lighting & active security guards."
    },
    {
      "id": 4,
      "lat": 28.6385,
      "lng": 77.2175,
      "radius": 350,
      "type": "risky",
      "title": "Canal Back Alleyway",
      "desc": "Reported poor lighting, limited visibility, and isolated after 9 PM."
    }
  ]
}
```

### Example `curl`
```bash
curl -X GET http://127.0.0.1:5000/api/safety-zones
```

---

## 3. GET `/api/police-stations`

Returns active police outposts, women safety help desks, and transit police stations.

### Response `200 OK`
```json
{
  "status": "success",
  "count": 3,
  "data": [
    {
      "id": 1,
      "lat": 28.6370,
      "lng": 77.2235,
      "name": "Police Assistance Booth #4",
      "type": "booth",
      "phone": "112",
      "desc": "24/7 Women Safety Help Desk • Officers on Duty: 3"
    },
    {
      "id": 2,
      "lat": 28.6335,
      "lng": 77.2180,
      "name": "Metro Security & Transit Police",
      "type": "station",
      "phone": "112",
      "desc": "Quick Response Team (QRT) Station"
    }
  ]
}
```

### Example `curl`
```bash
curl -X GET http://127.0.0.1:5000/api/police-stations
```

---

## 4. POST `/api/routes`

Calculates multiple candidate routes between origin and destination, computes composite safety scores (0-100) using 7 safety dimensions, and returns ranked routes (Safest first, followed by Moderate transit and Risky shortcut alternatives).

### Safety Scoring Algorithm
$$\text{Score} = (0.25 \times \text{Lighting}) + (0.25 \times \text{Crime Safety}) + (0.20 \times \text{Crowd}) + (0.15 \times \text{Police}) + (0.15 \times \text{Zone Intersections}) + \Delta_{\text{Time}}$$

- **Street Lighting (25%)**: Percentage of road length with high-intensity LED streetlights.
- **Crime Rate (25%)**: Inverted historical incident rate $(100 - \text{Crime Index})$.
- **Crowd & Commercial Activity (20%)**: Open 24/7 pharmacies, cafes, metro interchanges.
- **Police Proximity (15%)**: Proximity to nearest active outpost/booth.
- **Safe / Risky Zones (15%)**: Bonus for traversing safe corridors (+), penalties for risky zones (-).
- **Time of Day ($\Delta_{\text{Time}}$)**: Night conditions apply severe penalties to unlit/isolated passages.

### Request Body
```json
{
  "start": "Metro Station Central, Gate 3",
  "destination": "Greenfield Heights, Sector 14",
  "time_of_day": "night",
  "start_coords": [28.6328, 77.2155],
  "dest_coords": [28.6435, 77.2340]
}
```

### Response `200 OK`
```json
{
  "status": "success",
  "data": {
    "start": "Metro Station Central, Gate 3",
    "destination": "Greenfield Heights, Sector 14",
    "time_period": "night",
    "safest_route_id": "route-safest",
    "nearest_police": {
      "station": {
        "name": "Police Assistance Booth #4",
        "phone": "112"
      },
      "distance_meters": 140,
      "walking_eta_mins": 2
    },
    "safety_summary": {
      "recommended_route": "Main Boulevard Safe Corridor",
      "safest_score": 94,
      "time_context": "Safety scores adjusted for night conditions."
    },
    "routes": [
      {
        "id": "route-safest",
        "name": "Main Boulevard Safe Corridor",
        "shortName": "Boulevard (Safest)",
        "type": "safest",
        "score": 94,
        "scoreColor": "green",
        "tier": "SAFEST RECOMMENDED ROUTE",
        "time": "14 min",
        "distance": "3.2 km",
        "desc": "Optimal continuous LED street lighting, active pedestrian foot traffic...",
        "lighting": {
          "val": "96% Lit",
          "percent": 96,
          "sub": "Continuous high-intensity LED illumination",
          "status": "green"
        },
        "crime": {
          "val": "Very Low",
          "percent": 12,
          "sub": "Zero violent incidents recorded in 180 days",
          "status": "green"
        },
        "crowd": {
          "val": "High Activity",
          "percent": 92,
          "sub": "Open 24/7 pharmacies, cafes, & bus interchanges",
          "status": "green"
        },
        "police": {
          "val": "2 Booths (150m)",
          "percent": 95,
          "sub": "Patrol response estimated within 90 seconds",
          "status": "green"
        },
        "coordinates": [
          [28.6328, 77.2155],
          [28.6360, 77.2220],
          [28.6435, 77.2340]
        ],
        "turns": [
          {
            "action": "Start on Metro Plaza Walkway",
            "dist": "100 m",
            "safety": "🛡️ Safe Zone (CCTV Monitored)"
          }
        ]
      }
    ]
  }
}
```

### Example `curl`
```bash
curl -X POST http://127.0.0.1:5000/api/routes \
  -H "Content-Type: application/json" \
  -d '{
    "start": "Metro Station Central, Gate 3",
    "destination": "Greenfield Heights, Sector 14",
    "time_of_day": "night"
  }'
```

---

## 5. POST `/api/sos`

Triggered when the user taps the Emergency SOS button, completes the countdown, or requests SMS alert to family. Records the incident in SQLite `sos_logs` and matches the nearest police dispatch station.

### Request Body
```json
{
  "latitude": 28.6315,
  "longitude": 77.2167,
  "location_name": "Near Metro Pillar 128, Inner Ring Rd",
  "user_name": "Priya Sharma",
  "phone": "+91-9876543210",
  "emergency_type": "PANIC_BUTTON",
  "notes": "SOS Siren triggered by user in quiet area"
}
```

### Response `201 Created`
```json
{
  "status": "success",
  "message": "Emergency SOS alert recorded and live GPS shared with emergency network.",
  "sos_id": 1,
  "timestamp": "2026-09-21T08:16:00.000000Z",
  "alert_details": {
    "latitude": 28.6315,
    "longitude": 77.2167,
    "location_name": "Near Metro Pillar 128, Inner Ring Rd",
    "emergency_type": "PANIC_BUTTON",
    "emergency_helpline": "112",
    "women_safety_helpline": "1091"
  },
  "nearest_police_dispatch": {
    "station": {
      "name": "Police Assistance Booth #4",
      "phone": "112",
      "type": "booth"
    },
    "distance_meters": 140,
    "walking_eta_mins": 2
  },
  "contacts_notified": true
}
```

### Example `curl`
```bash
curl -X POST http://127.0.0.1:5000/api/sos \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 28.6315,
    "longitude": 77.2167,
    "location_name": "Near Metro Pillar 128",
    "emergency_type": "PANIC_BUTTON"
  }'
```

---

## 6. POST `/api/chat`

SafeHer AI Safety Assistant endpoint. Answers navigation inquiries, warns against low-light alleyways, advises on nearest police locations, and provides emergency de-escalation tips.

### Request Body
```json
{
  "message": "Is Old Canal Alleyway safe to walk right now?",
  "time_of_day": "night"
}
```

### Response `200 OK`
```json
{
  "status": "success",
  "reply": "⚠️ We strongly advise AGAINST using the Old Canal Alleyway shortcut, especially during night hours. It has only 28% street lighting, multiple blind corners, deserted industrial warehouses, and zero police surveillance. Please choose the Main Boulevard Safe Corridor instead (94/100 safety rating, 96% LED lit).",
  "route_safety_score": 42,
  "time_period": "night",
  "recommendations": [
    "Take Main Boulevard Safe Corridor",
    "Stay in well-lit areas with active foot traffic",
    "Share your live trip location with trusted contacts"
  ]
}
```

### Example `curl`
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Where is the nearest police station?",
    "time_of_day": "night"
  }'
```
