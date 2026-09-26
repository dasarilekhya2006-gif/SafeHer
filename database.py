"""
database.py - SQLite Database Setup and Query Helpers for SafeHer

Handles SQLite database schema creation, initial sample safety data seeding,
and transactional helper functions for routes, safety zones, police outposts,
SOS emergency alerts, and chat logs.
"""

import sqlite3
import json
import os
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'safety.db')


def get_db_connection():
    """Returns a SQLite connection with row factory configured as dictionary-like Row objects."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database schema and populates sample safety data if not already present."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Routes Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            short_name TEXT NOT NULL,
            type TEXT NOT NULL,
            score INTEGER NOT NULL,
            score_color TEXT NOT NULL,
            tier TEXT NOT NULL,
            time TEXT NOT NULL,
            distance TEXT NOT NULL,
            desc TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            lighting_val TEXT NOT NULL,
            lighting_pct INTEGER NOT NULL,
            lighting_sub TEXT NOT NULL,
            lighting_status TEXT NOT NULL,
            crime_val TEXT NOT NULL,
            crime_pct INTEGER NOT NULL,
            crime_sub TEXT NOT NULL,
            crime_status TEXT NOT NULL,
            crowd_val TEXT NOT NULL,
            crowd_pct INTEGER NOT NULL,
            crowd_sub TEXT NOT NULL,
            crowd_status TEXT NOT NULL,
            police_val TEXT NOT NULL,
            police_pct INTEGER NOT NULL,
            police_sub TEXT NOT NULL,
            police_status TEXT NOT NULL,
            coordinates TEXT NOT NULL,
            turns TEXT NOT NULL
        )
    ''')

    # 2. Safety Zones Table (Safe Corridors & Risky Dark Zones)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS safety_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            radius REAL NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            desc TEXT NOT NULL
        )
    ''')

    # 3. Police Stations & Help Desks Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS police_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            phone TEXT NOT NULL,
            desc TEXT NOT NULL
        )
    ''')

    # 4. SOS Emergency Incident Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sos_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy REAL,
            location_name TEXT,
            user_name TEXT,
            phone TEXT,
            emergency_type TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT
        )
    ''')
    try:
        cursor.execute('ALTER TABLE sos_logs ADD COLUMN accuracy REAL')
    except Exception:
        pass


    # 5. AI Safety Assistant Chat Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_message TEXT NOT NULL,
            bot_reply TEXT NOT NULL,
            recommendations TEXT
        )
    ''')

    # 6. Emergency Contacts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            relationship TEXT NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    conn.commit()

    # Seed Sample Data if tables are empty
    seed_sample_data(cursor, conn)
    conn.close()


def seed_sample_data(cursor, conn):
    """Seeds initial verified routes, safety zones, and police stations."""
    # Check if safety zones already seeded
    cursor.execute('SELECT COUNT(*) as count FROM safety_zones')
    if cursor.fetchone()['count'] == 0:
        sample_zones = [
            (28.6365, 77.2240, 420, 'safe', 'Grand Boulevard Commercial Corridor',
             'High foot traffic, 24/7 supermarkets, LED lighting & active security guards.'),
            (28.6330, 77.2160, 280, 'safe', 'Central Metro Hub',
             'Active CCTV coverage, transit security & continuous public presence.'),
            (28.6430, 77.2330, 300, 'safe', 'Sector 14 Residential Watch',
             'Gated community area with manned security checkpoints.'),
            (28.6385, 77.2175, 350, 'risky', 'Canal Back Alleyway',
             'Reported poor lighting, limited visibility, and isolated after 9 PM.'),
            (28.6405, 77.2230, 260, 'risky', 'Industrial Underpass Stretch',
             'Blind turns, closed warehouses, and absence of police surveillance.')
        ]
        cursor.executemany('''
            INSERT INTO safety_zones (lat, lng, radius, type, title, desc)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_zones)

    # Check if police stations already seeded
    cursor.execute('SELECT COUNT(*) as count FROM police_stations')
    if cursor.fetchone()['count'] == 0:
        sample_police = [
            (28.6370, 77.2235, 'Police Assistance Booth #4', 'booth', '112',
             '24/7 Women Safety Help Desk • Officers on Duty: 3'),
            (28.6335, 77.2180, 'Metro Security & Transit Police', 'station', '112',
             'Quick Response Team (QRT) Station'),
            (28.6420, 77.2310, 'Sector 14 Patrol Outpost', 'booth', '112',
             'Patrol bike unit & emergency safe shelter')
        ]
        cursor.executemany('''
            INSERT INTO police_stations (lat, lng, name, type, phone, desc)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_police)

    # Check if routes already seeded
    cursor.execute('SELECT COUNT(*) as count FROM routes')
    if cursor.fetchone()['count'] == 0:
        sample_routes = [
            (
                'route-safest',
                'Main Boulevard Safe Corridor',
                'Boulevard (Safest)',
                'safest',
                94,
                'green',
                'SAFEST RECOMMENDED ROUTE',
                '14 min',
                '3.2 km',
                'Optimal continuous LED street lighting, active pedestrian foot traffic, open 24/7 stores, and two active police outposts.',
                'Recommended: Keeps you on wide avenues with high visibility.',
                '96% Lit', 96, 'Continuous high-intensity LED illumination', 'green',
                'Very Low', 12, 'Zero violent incidents recorded in 180 days', 'green',
                'High Activity', 92, 'Open 24/7 pharmacies, cafes, & bus interchanges', 'green',
                '2 Booths (150m)', 95, 'Patrol response estimated within 90 seconds', 'green',
                json.dumps([
                    [28.6328, 77.2155],
                    [28.6342, 77.2185],
                    [28.6360, 77.2220],
                    [28.6375, 77.2260],
                    [28.6385, 77.2305],
                    [28.6410, 77.2325],
                    [28.6435, 77.2340]
                ]),
                json.dumps([
                    {'action': 'Start on Metro Plaza Walkway', 'dist': '100 m', 'safety': '🛡️ Safe Zone (24/7 Security Cameras)'},
                    {'action': 'Turn right onto Grand Boulevard', 'dist': '180 m', 'safety': '💡 100% LED Illuminated Corridor'},
                    {'action': 'Continue past Central City Police Station', 'dist': '650 m', 'safety': '👮 Police Booth within 60 meters'},
                    {'action': 'Pass open Late-Night Pharmacy & Market', 'dist': '1.2 km', 'safety': '👥 High Foot Traffic Area'},
                    {'action': 'Arrive at Greenfield Heights, Gate 2', 'dist': 'Destination', 'safety': '🛡️ Verified Safe Residence Arrival'}
                ])
            ),
            (
                'route-transit',
                'Metro Avenue & Transit Link',
                'Transit Ave (Fastest)',
                'moderate',
                76,
                'amber',
                'MODERATE SAFETY ROUTE',
                '10 min',
                '2.7 km',
                'Faster transit road along metro pillars. Well-trafficked until 10:30 PM, with some quiet pedestrian sidewalk stretches.',
                'Caution: Suitable during daylight or rush hours.',
                '72% Lit', 72, 'Standard lamps with some tree cover shadows', 'amber',
                'Moderate', 45, 'Sporadic petty theft / phone snatching reports', 'amber',
                'Moderate', 65, 'Bustling near stations, quiet side walks', 'amber',
                '1 Station (650m)', 60, 'Metro security desk at Sector 12 interchange', 'amber',
                json.dumps([
                    [28.6328, 77.2155],
                    [28.6350, 77.2170],
                    [28.6380, 77.2210],
                    [28.6395, 77.2270],
                    [28.6435, 77.2340]
                ]),
                json.dumps([
                    {'action': 'Head east along Metro Viaduct', 'dist': '300 m', 'safety': '💡 Moderate Street Lighting'},
                    {'action': 'Turn onto Transit Link Rd', 'dist': '500 m', 'safety': '⚠️ Quiet pedestrian stretch'},
                    {'action': 'Reach Greenfield Heights', 'dist': 'Destination', 'safety': '🛡️ Arrival'}
                ])
            ),
            (
                'route-alley',
                'Old Canal Alleyway Shortcut',
                'Old Alley (Risky)',
                'risky',
                42,
                'red',
                'HIGH RISK — NOT RECOMMENDED',
                '8 min',
                '2.1 km',
                'Shortcut cutting through unmonitored back alleys and empty service lanes. Frequent non-functioning streetlights.',
                'Warning: Not safe for solo walking at night.',
                '28% Lit', 28, 'Several broken streetlights & dark corners', 'red',
                'Elevated Risk', 85, 'Multiple incidents reported after dark', 'red',
                'Isolated Area', 18, 'Closed shutters, deserted industrial alleyway', 'red',
                'No Outpost (>1.8km)', 15, 'Emergency patrol response exceeds 12 mins', 'red',
                json.dumps([
                    [28.6328, 77.2155],
                    [28.6348, 77.2140],
                    [28.6390, 77.2180],
                    [28.6415, 77.2250],
                    [28.6435, 77.2340]
                ]),
                json.dumps([
                    {'action': 'Enter narrow canal access path', 'dist': '150 m', 'safety': '⚠️ Unlit Alleyway'},
                    {'action': 'Pass unmonitored rail underpass', 'dist': '400 m', 'safety': '⚠️ High incident blind spot'},
                    {'action': 'Exit into Sector 14 Gate', 'dist': 'Destination', 'safety': '🛡️ Arrival'}
                ])
            )
        ]
        cursor.executemany('''
            INSERT INTO routes (
                id, name, short_name, type, score, score_color, tier, time, distance,
                desc, recommendation, lighting_val, lighting_pct, lighting_sub, lighting_status,
                crime_val, crime_pct, crime_sub, crime_status,
                crowd_val, crowd_pct, crowd_sub, crowd_status,
                police_val, police_pct, police_sub, police_status,
                coordinates, turns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_routes)

    # Check if emergency contacts already seeded
    cursor.execute('SELECT COUNT(*) as count FROM emergency_contacts')
    if cursor.fetchone()['count'] == 0:
        now = datetime.utcnow().isoformat() + 'Z'
        sample_contacts = [
            ('Mom', '+91 98765 43210', 'Mother', 1, 1, now, now),
            ('Sister', '+91 98765 43211', 'Sister', 0, 1, now, now)
        ]
        cursor.executemany('''
            INSERT INTO emergency_contacts (name, phone, relationship, is_primary, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_contacts)

    conn.commit()


def get_all_routes():
    """Fetches all stored routes from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM routes')
    rows = cursor.fetchall()
    routes = []
    for r in rows:
        route_dict = {
            'id': r['id'],
            'name': r['name'],
            'shortName': r['short_name'],
            'type': r['type'],
            'score': r['score'],
            'scoreColor': r['score_color'],
            'tier': r['tier'],
            'time': r['time'],
            'distance': r['distance'],
            'desc': r['desc'],
            'recommendation': r['recommendation'],
            'lighting': {
                'val': r['lighting_val'],
                'percent': r['lighting_pct'],
                'sub': r['lighting_sub'],
                'status': r['lighting_status']
            },
            'crime': {
                'val': r['crime_val'],
                'percent': r['crime_pct'],
                'sub': r['crime_sub'],
                'status': r['crime_status']
            },
            'crowd': {
                'val': r['crowd_val'],
                'percent': r['crowd_pct'],
                'sub': r['crowd_sub'],
                'status': r['crowd_status']
            },
            'police': {
                'val': r['police_val'],
                'percent': r['police_pct'],
                'sub': r['police_sub'],
                'status': r['police_status']
            },
            'coordinates': json.loads(r['coordinates']),
            'turns': json.loads(r['turns'])
        }
        routes.append(route_dict)
    conn.close()
    return routes


def get_safety_zones():
    """Fetches all safety zones (safe and risky circles)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM safety_zones')
    rows = cursor.fetchall()
    zones = []
    for r in rows:
        zones.append({
            'id': r['id'],
            'lat': r['lat'],
            'lng': r['lng'],
            'radius': r['radius'],
            'type': r['type'],
            'title': r['title'],
            'desc': r['desc']
        })
    conn.close()
    return zones


def get_police_stations():
    """Fetches all police stations and booths."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM police_stations')
    rows = cursor.fetchall()
    stations = []
    for r in rows:
        stations.append({
            'id': r['id'],
            'lat': r['lat'],
            'lng': r['lng'],
            'name': r['name'],
            'type': r['type'],
            'phone': r['phone'],
            'desc': r['desc']
        })
    conn.close()
    return stations


def log_sos(latitude, longitude, location_name, user_name, phone, emergency_type, notes='', accuracy=None):
    """Logs an incoming SOS alert into the database and returns the generated incident ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().isoformat() + 'Z'
    cursor.execute('''
        INSERT INTO sos_logs (timestamp, latitude, longitude, accuracy, location_name, user_name, phone, emergency_type, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, latitude, longitude, accuracy, location_name, user_name, phone, emergency_type, 'ACTIVE_DISPATCH', notes))
    conn.commit()
    sos_id = cursor.lastrowid
    conn.close()
    return sos_id, timestamp


def get_sos_logs():
    """Fetches past SOS logs for review or admin monitoring."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sos_logs ORDER BY id DESC LIMIT 50')
    rows = cursor.fetchall()
    logs = [dict(r) for r in rows]
    conn.close()
    return logs


def get_sos_log(sos_id):
    """Fetches a specific SOS log by incident ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sos_logs WHERE id = ?', (sos_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def cancel_sos(sos_id):
    """Cancels an active SOS alert by updating status to 'CANCELLED'."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cancelled_at = datetime.utcnow().isoformat() + 'Z'
    cursor.execute('''
        UPDATE sos_logs
        SET status = 'CANCELLED', notes = notes || ' [Cancelled at ' || ? || ']'
        WHERE id = ?
    ''', (cancelled_at, sos_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def log_chat(user_message, bot_reply, recommendations=None):
    """Logs an interaction with the AI Safety Assistant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().isoformat() + 'Z'
    recs_json = json.dumps(recommendations or [])
    cursor.execute('''
        INSERT INTO chat_logs (timestamp, user_message, bot_reply, recommendations)
        VALUES (?, ?, ?, ?)
    ''', (timestamp, user_message, bot_reply, recs_json))
    conn.commit()
    conn.close()


# -------------------------------------------------------------------------
# Emergency Contacts Helpers
# -------------------------------------------------------------------------

def normalize_phone_core(phone_str):
    """
    Extracts the 10-digit core of an Indian phone number for comparison and uniqueness checking.
    Returns 10-digit string if valid, otherwise None.
    Valid Indian mobile numbers are 10 digits starting with 6, 7, 8, or 9.
    Accepts prefixes: +91, 91, 0, or raw 10 digits.
    """
    if not phone_str:
        return None
    # Strip everything except digits
    digits = re.sub(r'\D', '', str(phone_str).strip())
    # Handle country code 91 with 12 digits (e.g. +91 9876543210 -> 919876543210)
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    # Handle leading trunk code 0 with 11 digits (e.g. 09876543210)
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    
    if len(digits) == 10 and digits[0] in '6789':
        return digits
    return None


def format_indian_phone(phone_str):
    """Formats a valid Indian phone number into standard '+91 XXXXX XXXXX' format."""
    core = normalize_phone_core(phone_str)
    if core:
        return f"+91 {core[:5]} {core[5:]}"
    return str(phone_str).strip()


def validate_contact_input(name, phone, relationship, contact_id=None):
    """
    Validates name, phone, relationship and checks for duplicate phone numbers.
    Returns (is_valid: bool, error_message: str or None, formatted_phone: str or None).
    """
    if not name or not str(name).strip():
        return False, "Name is required.", None
    
    if not phone or not str(phone).strip():
        return False, "Phone number is required.", None
        
    if not relationship or not str(relationship).strip():
        return False, "Relationship is required.", None

    core = normalize_phone_core(phone)
    if not core:
        return False, "Invalid Indian phone number. Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9 (e.g., +91 98765 43210).", None

    formatted = format_indian_phone(phone)

    # Check for duplicates across all existing contacts (excluding contact_id if updating)
    conn = get_db_connection()
    cursor = conn.cursor()
    if contact_id is not None:
        cursor.execute('SELECT id, phone FROM emergency_contacts WHERE id != ?', (contact_id,))
    else:
        cursor.execute('SELECT id, phone FROM emergency_contacts')
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        existing_core = normalize_phone_core(r['phone'])
        if existing_core == core:
            return False, "A contact with this phone number already exists.", None

    return True, None, formatted


def _row_to_contact_dict(row):
    """Converts a SQLite Row object to a clean JSON-serializable contact dictionary."""
    if not row:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'phone': row['phone'],
        'relationship': row['relationship'],
        'is_primary': bool(row['is_primary']),
        'enabled': bool(row['enabled']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at']
    }


def get_all_contacts():
    """
    Fetches all emergency contacts ordered by primary status first, then id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM emergency_contacts ORDER BY is_primary DESC, id ASC')
    rows = cursor.fetchall()
    contacts = [_row_to_contact_dict(r) for r in rows]
    conn.close()
    return contacts


def get_contact_by_id(contact_id):
    """Fetches a single emergency contact by id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM emergency_contacts WHERE id = ?', (contact_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_contact_dict(row)


def get_enabled_contacts():
    """Fetches only enabled emergency contacts ordered by primary status first, then id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM emergency_contacts WHERE enabled = 1 ORDER BY is_primary DESC, id ASC')
    rows = cursor.fetchall()
    contacts = [_row_to_contact_dict(r) for r in rows]
    conn.close()
    return contacts


def add_contact(name, phone, relationship, is_primary=False, enabled=True):
    """
    Adds a new emergency contact. If is_primary is True, resets primary flag on all other contacts.
    Returns the created contact dictionary.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat() + 'Z'
    is_prim_int = 1 if is_primary else 0
    enabled_int = 1 if enabled else 0
    formatted_phone = format_indian_phone(phone)
    clean_name = str(name).strip()
    clean_rel = str(relationship).strip()

    # Reset other primary contacts if this one is marked primary
    if is_prim_int:
        cursor.execute('UPDATE emergency_contacts SET is_primary = 0')

    cursor.execute('''
        INSERT INTO emergency_contacts (name, phone, relationship, is_primary, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (clean_name, formatted_phone, clean_rel, is_prim_int, enabled_int, now, now))
    
    contact_id = cursor.lastrowid
    conn.commit()

    cursor.execute('SELECT * FROM emergency_contacts WHERE id = ?', (contact_id,))
    new_row = cursor.fetchone()
    contact = _row_to_contact_dict(new_row)
    conn.close()
    return contact


def update_contact(contact_id, name, phone, relationship, is_primary=False, enabled=True):
    """
    Updates an existing emergency contact. If is_primary is True, resets primary flag on all other contacts.
    Returns the updated contact dictionary, or None if contact_id not found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM emergency_contacts WHERE id = ?', (contact_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return None

    now = datetime.utcnow().isoformat() + 'Z'
    is_prim_int = 1 if is_primary else 0
    enabled_int = 1 if enabled else 0
    formatted_phone = format_indian_phone(phone)
    clean_name = str(name).strip()
    clean_rel = str(relationship).strip()

    if is_prim_int:
        cursor.execute('UPDATE emergency_contacts SET is_primary = 0 WHERE id != ?', (contact_id,))

    cursor.execute('''
        UPDATE emergency_contacts
        SET name = ?, phone = ?, relationship = ?, is_primary = ?, enabled = ?, updated_at = ?
        WHERE id = ?
    ''', (clean_name, formatted_phone, clean_rel, is_prim_int, enabled_int, now, contact_id))
    
    conn.commit()

    cursor.execute('SELECT * FROM emergency_contacts WHERE id = ?', (contact_id,))
    updated_row = cursor.fetchone()
    contact = _row_to_contact_dict(updated_row)
    conn.close()
    return contact


def delete_contact(contact_id):
    """
    Deletes an emergency contact by ID.
    Returns True if deleted, False if contact was not found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM emergency_contacts WHERE id = ?', (contact_id,))
    if not cursor.fetchone():
        conn.close()
        return False

    cursor.execute('DELETE FROM emergency_contacts WHERE id = ?', (contact_id,))
    conn.commit()
    conn.close()
    return True

