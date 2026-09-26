"""
app.py - Flask REST API Backend for SafeHer Women Safety Route Navigation

Provides REST endpoints for:
- POST /api/routes           : Generates candidate routes with multi-factor safety evaluation
- GET  /api/safety-zones     : Retrieves safe corridors and low-light / risky zones
- GET  /api/police-stations  : Retrieves verified police booths, transit police, and helplines
- POST /api/sos              : Receives and records emergency alerts with live GPS coordinates
- POST /api/chat             : AI Safety Assistant providing travel guidance and safety protocols
- GET  /api/health           : Backend health status check
"""

import sys
import os
import re
import math
import sqlite3
import logging
from datetime import datetime

# Ensure Windows consoles don't crash on non-ASCII characters or Unicode paths
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

# Optional Flask-CORS support with manual fallback for zero-dependency portability
try:
    from flask_cors import CORS
    has_cors = True
except ImportError:
    has_cors = False

import database
import safety_engine
import chatbot
import ml_predictor
import notification_service


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')

if has_cors:
    CORS(app, resources={r"/api/*": {"origins": "*"}})
else:
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return response


# Initialize SQLite Database on startup
database.init_db()


# -------------------------------------------------------------------------
# Static File Routes (Serve frontend directly from Flask if desired)
# -------------------------------------------------------------------------
@app.route('/')
def serve_index():
    """Serves the SafeHer frontend index.html."""
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Serves static assets like style.css, app.js."""
    return send_from_directory(BASE_DIR, filename)


# -------------------------------------------------------------------------
# Standard Error Response Helper
# -------------------------------------------------------------------------

def make_error_response(error_code, message, status_code=400):
    """
    Returns a standardized JSON error response:
    {
        "status": "error",
        "error_code": "ERROR_CODE",
        "message": "Human readable message"
    }
    """
    return jsonify({
        'status': 'error',
        'error_code': error_code,
        'message': message
    }), status_code


# -------------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------------

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    GET /api/health
    Returns service health, database status, and current server timestamp.
    """
    try:
        # Test DB connection
        conn = database.get_db_connection()
        conn.execute('SELECT 1').fetchone()
        conn.close()
        db_status = 'connected'
        return jsonify({
            'status': 'healthy',
            'service': 'SafeHer Backend API',
            'version': '1.0.0',
            'database': db_status,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 200
    except Exception as e:
        app.logger.error(f"Health check database failure: {e}")
        return jsonify({
            'status': 'error',
            'error_code': 'DATABASE_ERROR',
            'message': f"Database connection error: {str(e)}",
            'service': 'SafeHer Backend API',
            'version': '1.0.0',
            'database': f'error: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 503


@app.route('/api/safety-zones', methods=['GET'])
def get_safety_zones():
    """
    GET /api/safety-zones
    Returns all safe zones and low-lit risky zones for map overlay.
    """
    try:
        zones = database.get_safety_zones()
        return jsonify({
            'status': 'success',
            'count': len(zones),
            'data': zones
        }), 200
    except sqlite3.Error as e:
        app.logger.error(f"Database error in /api/safety-zones: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to retrieve safety zones.', 500)
    except Exception as e:
        app.logger.error(f"Error in /api/safety-zones: {e}")
        return make_error_response('INTERNAL_ERROR', f"Safety zones retrieval error: {str(e)}", 500)


@app.route('/api/police-stations', methods=['GET'])
def get_police_stations():
    """
    GET /api/police-stations
    Returns all police outposts, transit police, and women safety help desks.
    """
    try:
        stations = database.get_police_stations()
        return jsonify({
            'status': 'success',
            'count': len(stations),
            'data': stations
        }), 200
    except sqlite3.Error as e:
        app.logger.error(f"Database error in /api/police-stations: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to retrieve police stations.', 500)
    except Exception as e:
        app.logger.error(f"Error in /api/police-stations: {e}")
        return make_error_response('INTERNAL_ERROR', f"Police stations retrieval error: {str(e)}", 500)


@app.route('/api/routes', methods=['POST'])
def calculate_routes():
    """
    POST /api/routes
    Calculates multiple candidate routes between start and destination,
    evaluating safety based on street lighting, crime rate, crowd density,
    police proximity, safe/risky zones, and time of day.

    Request Body:
    {
        "start": "Metro Station Central, Gate 3",
        "destination": "Greenfield Heights, Sector 14",
        "time_of_day": "night",  // Optional: "night", "day", "22:30" or omitted for server time
        "start_coords": [28.6328, 77.2155], // Optional
        "dest_coords": [28.6435, 77.2340]   // Optional
    }
    """
    try:
        if request.data and request.data.strip():
            req_data = request.get_json(silent=True)
            if req_data is None or not isinstance(req_data, dict):
                return make_error_response('BAD_REQUEST', 'Invalid JSON body. Expected JSON object.', 400)
        else:
            req_data = {}

        start_name = req_data.get('start', 'Metro Station Central, Gate 3')
        dest_name = req_data.get('destination', 'Greenfield Heights, Sector 14')
        time_of_day = req_data.get('time_of_day', 'auto')

        start_coords = req_data.get('start_coords', [28.6328, 77.2155])
        dest_coords = req_data.get('dest_coords', [28.6435, 77.2340])

        safety_zones = database.get_safety_zones()
        police_stations = database.get_police_stations()

        # Generate candidate routes and evaluate multi-factor safety
        routes = safety_engine.generate_candidate_routes(
            start_name=start_name,
            dest_name=dest_name,
            start_coords=start_coords,
            dest_coords=dest_coords,
            safety_zones=safety_zones,
            police_stations=police_stations,
            time_of_day=time_of_day
        )

        safest_route = routes[0] if routes else None
        time_period = safety_engine.determine_time_period(time_of_day)

        # Nearest police to start location
        nearest_police = safety_engine.find_nearest_police(start_coords[0], start_coords[1], police_stations)

        # --- ML Risk Prediction for each route ---
        for route in routes:
            try:
                ml_pred = ml_predictor.predict_route_risk(route)
                route['ml_risk'] = ml_pred
                # Blend ML confidence into final score
                ml_score_adj = 0
                if ml_pred['risk_label'] == 'LOW':
                    ml_score_adj = +3
                elif ml_pred['risk_label'] == 'HIGH':
                    ml_score_adj = -5
                route['score'] = max(15, min(98, route['score'] + ml_score_adj))
            except Exception as ml_err:
                route['ml_risk'] = {'risk_label': 'UNKNOWN', 'confidence': 0,
                                    'color': '#6B7280', 'icon': '⚪',
                                    'advice': 'ML prediction unavailable.'}


        return jsonify({
            'status': 'success',
            'data': {
                'start': start_name,
                'destination': dest_name,
                'time_period': time_period,
                'safest_route_id': safest_route['id'] if safest_route else None,
                'routes': routes,
                'nearest_police': nearest_police,
                'safety_summary': {
                    'recommended_route': safest_route['name'] if safest_route else '',
                    'safest_score': safest_route['score'] if safest_route else 0,
                    'time_context': f"Safety scores adjusted for {time_period} conditions."
                }
            }
        }), 200
    except sqlite3.Error as e:
        app.logger.error(f"Database error in /api/routes: {e}")
        return make_error_response('DATABASE_ERROR', 'Database error evaluating routes.', 500)
    except Exception as e:
        app.logger.error(f"Error in /api/routes: {e}")
        return make_error_response('INTERNAL_ERROR', f"Route evaluation error: {str(e)}", 500)


@app.route('/api/sos', methods=['POST'])
def trigger_sos():
    """
    POST /api/sos
    Registers an emergency SOS panic alert with real current GPS coordinates.
    Logs incident in SQLite database and finds the nearest police station.

    Request Body:
    {
        "latitude": 28.6315,
        "longitude": 77.2167,
        "accuracy": 15.2,
        "location_name": "Current GPS Location",
        "emergency_type": "PANIC_BUTTON",
        "notes": "Emergency SOS broadcast with real-time GPS."
    }
    """
    try:
        req_data = request.get_json(silent=True)
        if not isinstance(req_data, dict):
            return make_error_response('BAD_REQUEST', 'Invalid request body. Expected JSON object.', 400)

        # 1. Validate latitude presence
        if 'latitude' not in req_data or req_data.get('latitude') is None or req_data.get('latitude') == '':
            return make_error_response('GPS_REQUIRED', 'Missing latitude. Valid GPS coordinates are required.', 400)

        # 2. Validate longitude presence
        if 'longitude' not in req_data or req_data.get('longitude') is None or req_data.get('longitude') == '':
            return make_error_response('GPS_REQUIRED', 'Missing longitude. Valid GPS coordinates are required.', 400)

        # 3. Validate numeric value and bounds for latitude (-90 to +90)
        try:
            lat = float(req_data['latitude'])
            if math.isnan(lat) or math.isinf(lat) or not (-90.0 <= lat <= 90.0):
                raise ValueError()
        except (ValueError, TypeError):
            return make_error_response('INVALID_COORDINATES', 'Invalid latitude. Must be a decimal number between -90 and 90.', 400)

        # 4. Validate numeric value and bounds for longitude (-180 to +180)
        try:
            lng = float(req_data['longitude'])
            if math.isnan(lng) or math.isinf(lng) or not (-180.0 <= lng <= 180.0):
                raise ValueError()
        except (ValueError, TypeError):
            return make_error_response('INVALID_COORDINATES', 'Invalid longitude. Must be a decimal number between -180 and 180.', 400)

        # 5. Optional accuracy in meters
        accuracy = None
        if 'accuracy' in req_data and req_data.get('accuracy') is not None and req_data.get('accuracy') != '':
            try:
                acc_val = float(req_data['accuracy'])
                if not (math.isnan(acc_val) or math.isinf(acc_val) or acc_val < 0):
                    accuracy = acc_val
            except (ValueError, TypeError):
                accuracy = None

        location_name = req_data.get('location_name', f'GPS ({lat:.4f}, {lng:.4f})')
        user_name = req_data.get('user_name', 'SafeHer User')
        phone = req_data.get('phone', 'Unspecified')
        emergency_type = req_data.get('emergency_type', 'PANIC_BUTTON')
        notes = req_data.get('notes', 'Emergency SOS broadcast triggered with verified real-time GPS.')

        # Log into SQLite with verified real GPS
        sos_id, timestamp = database.log_sos(
            latitude=lat,
            longitude=lng,
            location_name=location_name,
            user_name=user_name,
            phone=phone,
            emergency_type=emergency_type,
            notes=notes,
            accuracy=accuracy
        )

        # Locate nearest police unit to the actual current coordinates
        police_stations = database.get_police_stations()
        nearest_police = safety_engine.find_nearest_police(lat, lng, police_stations)

        # Load enabled emergency contacts
        enabled_contacts = database.get_enabled_contacts()

        # Send notification through notification service (never fakes SMS delivery)
        location_data = {
            'latitude': lat,
            'longitude': lng,
            'accuracy': accuracy,
            'location_name': location_name
        }
        notification_results = notification_service.notify_emergency_contacts(
            contacts=enabled_contacts,
            location_data=location_data,
            user_name=user_name
        )

        return jsonify({
            'status': 'success',
            'sos_id': sos_id,
            'latitude': lat,
            'longitude': lng,
            'accuracy': accuracy,
            'message': 'Emergency SOS alert recorded and live GPS shared with emergency network.',
            'timestamp': timestamp,
            'alert_details': {
                'latitude': lat,
                'longitude': lng,
                'accuracy': accuracy,
                'location_name': location_name,
                'emergency_type': emergency_type,
                'emergency_helpline': '112',
                'women_safety_helpline': '1091'
            },
            'nearest_police_dispatch': nearest_police,
            'notifications': notification_results
        }), 201
    except sqlite3.Error as e:
        app.logger.error(f"Database error during SOS trigger: {e}")
        return make_error_response('DATABASE_ERROR', f"Database error recording SOS: {str(e)}", 500)
    except Exception as e:
        app.logger.error(f"Error during SOS trigger: {e}")
        return make_error_response('INTERNAL_ERROR', f"Emergency SOS dispatch error: {str(e)}", 500)


@app.route('/api/sos/<int:sos_id>', methods=['GET'])
def get_sos_endpoint(sos_id):
    """
    GET /api/sos/<sos_id>
    Fetches the details and current status of an SOS incident.
    """
    try:
        alert = database.get_sos_log(sos_id)
        if not alert:
            return make_error_response('NOT_FOUND', f'SOS incident #{sos_id} not found.', 404)
        return jsonify({
            'status': 'success',
            'alert': alert
        }), 200
    except sqlite3.Error as e:
        return make_error_response('DATABASE_ERROR', f'Database error fetching SOS: {str(e)}', 500)
    except Exception as e:
        return make_error_response('INTERNAL_ERROR', f'Internal error fetching SOS: {str(e)}', 500)


@app.route('/api/sos/<int:sos_id>/cancel', methods=['POST'])
def cancel_sos_endpoint(sos_id):
    """
    POST /api/sos/<sos_id>/cancel
    Cancels an active SOS incident.
    """
    try:
        updated = database.cancel_sos(sos_id)
        if not updated:
            return make_error_response('NOT_FOUND', f'SOS incident #{sos_id} not found.', 404)
        return jsonify({
            'status': 'success',
            'sos_id': sos_id,
            'message': f'SOS incident #{sos_id} has been cancelled.'
        }), 200
    except sqlite3.Error as e:
        return make_error_response('DATABASE_ERROR', f'Database error cancelling SOS: {str(e)}', 500)
    except Exception as e:
        return make_error_response('INTERNAL_ERROR', f'Internal error cancelling SOS: {str(e)}', 500)


@app.route('/api/notifications/status', methods=['GET'])
def get_notification_status():
    """
    Returns current configuration status of the emergency notification service.
    """
    configured = notification_service.is_provider_configured()
    provider = notification_service.get_configured_provider()
    provider_name = type(provider).__name__.replace('NotificationProvider', '')
    return jsonify({
        'status': 'success',
        'configured': configured,
        'provider': provider_name if configured else None
    }), 200


@app.route('/api/notifications/test', methods=['POST'])
def test_notification():
    """
    POST /api/notifications/test
    Tests sending an emergency notification to a specific phone number or primary contact.
    Returns:
    - 400 with NOTIFICATION_NOT_CONFIGURED if provider not set up
    - 400 with INVALID_CONTACT if no recipient phone is available
    - 500 with NOTIFICATION_FAILED if sending fails
    - 200 on success
    """
    try:
        if not notification_service.is_provider_configured():
            return make_error_response('NOTIFICATION_NOT_CONFIGURED', 'SMS notification service is not configured.', 400)

        data = request.get_json(silent=True) or {}
        phone = data.get('phone')
        name = data.get('name', 'Test Contact')
        if not phone:
            primary = database.get_primary_contact()
            if primary:
                phone = primary['phone']
                name = primary['name']
            else:
                return make_error_response('INVALID_CONTACT', 'No phone number provided and no primary contact found.', 400)

        result = notification_service.send_emergency_alert(
            contact={'name': name, 'phone': phone},
            location_data=data.get('location', {
                'latitude': 28.6315,
                'longitude': 77.2167,
                'location_name': 'SafeHer Test Location'
            })
        )

        if result.get('success'):
            return jsonify({'status': 'success', 'result': result}), 200
        else:
            return make_error_response('NOTIFICATION_FAILED', result.get('error') or 'Failed to send notification.', 500)
    except Exception as e:
        app.logger.error(f"Error in /api/notifications/test: {e}")
        return make_error_response('NOTIFICATION_FAILED', f"Notification error: {str(e)}", 500)


@app.route('/api/call/emergency', methods=['POST'])
def trigger_emergency_call():
    """
    POST /api/call/emergency
    Places an automated emergency voice call to the primary contact or specified phone.
    """
    try:
        data = request.get_json(silent=True) or {}
        phone = data.get('phone')
        name = data.get('name')
        if not phone:
            primary = database.get_primary_contact()
            if primary:
                phone = primary['phone']
                name = primary['name']
            else:
                return make_error_response('INVALID_CONTACT', 'No primary emergency contact found to call.', 400)

        result = notification_service.send_emergency_call(
            contact={'name': name or 'Emergency Contact', 'phone': phone},
            location_data=data.get('location'),
            user_name=data.get('user_name', 'SafeHer User')
        )
        if result.get('success'):
            return jsonify({'status': 'success', 'call': result}), 200
        else:
            status = result.get('status')
            if status == 'not_configured':
                return make_error_response('NOTIFICATION_NOT_CONFIGURED', result.get('error', 'Voice calling service is not configured.'), 400)
            elif status == 'not_supported':
                return make_error_response('NOT_SUPPORTED', result.get('error', 'Active provider does not support automated voice calls.'), 400)
            else:
                return make_error_response('NOTIFICATION_FAILED', result.get('error', 'Failed to initiate emergency call.'), 500)
    except Exception as e:
        app.logger.error(f"Error in /api/call/emergency: {e}")
        return make_error_response('NOTIFICATION_FAILED', f"Emergency call error: {str(e)}", 500)


@app.route('/api/chat', methods=['POST'])
def safety_chat():
    """
    POST /api/chat
    SafeHer AI Safety Assistant — NLP-powered conversational endpoint.
    Understands natural-language questions and replies with live safety data.

    Request Body:
    {
        "message": "Is the fastest route safe at night?",
        "current_location": [28.6328, 77.2155],  // Optional
        "time_of_day": "night"                    // Optional: 'day', 'night', 'auto'
    }
    """
    try:
        req_data = request.get_json(silent=True)
        if req_data is None:
            req_data = {}
        elif not isinstance(req_data, dict):
            return make_error_response('BAD_REQUEST', 'Invalid request body. Expected JSON object.', 400)

        user_msg = req_data.get('message', '').strip()
        time_of_day = req_data.get('time_of_day', 'auto')
        user_coords = req_data.get('current_location', [28.6328, 77.2155])

        if not user_msg:
            return make_error_response('BAD_REQUEST', 'Message parameter is required.', 400)

        # Load live safety data from database
        safety_zones    = database.get_safety_zones()
        police_stations = database.get_police_stations()

        # Generate candidate routes for context
        routes = safety_engine.generate_candidate_routes(
            start_name='Metro Station Central, Gate 3',
            dest_name='Greenfield Heights, Sector 14',
            start_coords=user_coords,
            dest_coords=[28.6435, 77.2340],
            safety_zones=safety_zones,
            police_stations=police_stations,
            time_of_day=time_of_day
        )

        # Run NLP chatbot engine
        result = chatbot.generate_response(
            message=user_msg,
            routes=routes,
            safety_zones=safety_zones,
            police_stations=police_stations,
            user_coords=user_coords,
            time_of_day=time_of_day
        )

        reply           = result.get('reply', '')
        recommendations = result.get('recommendations', [])
        intent          = result.get('intent', 'general')
        safety_score    = result.get('safety_score', 90)
        show_sos        = result.get('show_sos_button', False)
        period          = safety_engine.determine_time_period(time_of_day)

        # Log interaction in SQLite database
        database.log_chat(user_msg, reply, recommendations)

        return jsonify({
            'status': 'success',
            'reply': reply,
            'recommendations': recommendations,
            'intent': intent,
            'route_safety_score': safety_score,
            'time_period': period,
            'show_sos_button': show_sos
        }), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error in /api/chat: {e}")
        return make_error_response('DATABASE_ERROR', 'Database error during chat query.', 500)
    except Exception as e:
        app.logger.error(f"Error in /api/chat: {e}")
        return make_error_response('INTERNAL_ERROR', f"Chatbot processing error: {str(e)}", 500)


# -------------------------------------------------------------------------
# ML Risk Prediction Endpoints
# -------------------------------------------------------------------------

@app.route('/api/ml-predict', methods=['POST'])
def ml_predict():
    """
    POST /api/ml-predict
    Predict the ML risk level for a specific route segment.

    Request Body (all optional except crime_incidents):
    {
        "crime_incidents":  3,      // Number of reported incidents
        "lighting_pct":     65,     // Street lighting % (0-100)
        "crowd_density":    45,     // Pedestrian activity (0-100)
        "police_dist_m":    700,    // Distance to nearest police (meters)
        "hour_of_day":      22,     // 0-23 (default: current hour)
        "day_of_week":      5,      // 0=Mon ... 6=Sun (default: today)
        "historical_safety": 55     // Past safety score (default: auto-derived)
    }
    """
    try:
        d = request.get_json(silent=True)
        if d is None:
            d = {}
        elif not isinstance(d, dict):
            return make_error_response('BAD_REQUEST', 'Invalid request body. Expected JSON object.', 400)

        result = ml_predictor.predict_risk(
            crime_incidents   = float(d.get('crime_incidents',   3)),
            lighting_pct      = float(d.get('lighting_pct',      65)),
            crowd_density     = float(d.get('crowd_density',     45)),
            police_dist_m     = float(d.get('police_dist_m',    700)),
            hour_of_day       = d.get('hour_of_day',   None),
            day_of_week       = d.get('day_of_week',   None),
            historical_safety = d.get('historical_safety', None)
        )
        return jsonify({'status': 'success', 'prediction': result}), 200
    except (ValueError, TypeError) as e:
        return make_error_response('BAD_REQUEST', f"Invalid numeric parameters for ML predictor: {str(e)}", 400)
    except Exception as e:
        app.logger.error(f"Error in /api/ml-predict: {e}")
        return make_error_response('INTERNAL_ERROR', f"ML prediction error: {str(e)}", 500)


@app.route('/api/ml-info', methods=['GET'])
def ml_info():
    """
    GET /api/ml-info
    Returns ML model metadata, evaluation results, and feature importances.
    Used by the SafeHer UI to display model performance on the info panel.
    """
    try:
        info = ml_predictor.get_model_info()
        return jsonify({'status': 'success', 'ml_info': info}), 200
    except Exception as e:
        app.logger.error(f"Error in /api/ml-info: {e}")
        return make_error_response('INTERNAL_ERROR', f"ML model info error: {str(e)}", 500)


# -------------------------------------------------------------------------
# Emergency Contacts Endpoints
# -------------------------------------------------------------------------

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    """
    GET /api/contacts
    Returns all registered emergency contacts ordered with Primary first.
    """
    try:
        contacts = database.get_all_contacts()
        return jsonify({
            'status': 'success',
            'contacts': contacts
        }), 200
    except sqlite3.Error as e:
        app.logger.error(f"Database error in GET /api/contacts: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to load emergency contacts.', 500)
    except Exception as e:
        app.logger.error(f"Error in GET /api/contacts: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to load emergency contacts.', 500)


@app.route('/api/contacts', methods=['POST'])
def add_contact():
    """
    POST /api/contacts
    Creates a new emergency contact.

    Request Body:
    {
        "name": "Mom",
        "phone": "+91 98765 43210",
        "relationship": "Mother",
        "is_primary": true,
        "enabled": true
    }
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return make_error_response('BAD_REQUEST', 'Invalid request body. Expected JSON object.', 400)

        name = str(data.get('name', '')).strip()
        phone = str(data.get('phone', '')).strip()
        relationship = str(data.get('relationship', '')).strip()
        is_primary = bool(data.get('is_primary', False))
        enabled = bool(data.get('enabled', True))

        is_valid, err_msg, formatted_phone = database.validate_contact_input(name, phone, relationship)
        if not is_valid:
            return make_error_response('INVALID_CONTACT', err_msg, 400)

        contact = database.add_contact(
            name=name,
            phone=formatted_phone,
            relationship=relationship,
            is_primary=is_primary,
            enabled=enabled
        )

        return jsonify({
            'status': 'success',
            'message': 'Contact saved successfully',
            'contact': contact
        }), 201

    except sqlite3.Error as e:
        app.logger.error(f"Database error in POST /api/contacts: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to save emergency contact.', 500)
    except Exception as e:
        app.logger.error(f"Error in POST /api/contacts: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to save emergency contact.', 500)


@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_single_contact(contact_id):
    """
    GET /api/contacts/<id>
    Retrieves a single emergency contact by ID.
    """
    try:
        contact = database.get_contact_by_id(contact_id)
        if not contact:
            return make_error_response('CONTACT_NOT_FOUND', 'Contact not found', 404)
        return jsonify({
            'status': 'success',
            'contact': contact
        }), 200
    except Exception as e:
        app.logger.error(f"Error in GET /api/contacts/{contact_id}: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to load emergency contacts.', 500)


@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    """
    PUT /api/contacts/<id>
    Updates an existing emergency contact.

    Request Body:
    {
        "name": "Mom",
        "phone": "+91 98765 43210",
        "relationship": "Mother",
        "is_primary": true,
        "enabled": true
    }
    """
    try:
        existing = database.get_contact_by_id(contact_id)
        if not existing:
            return make_error_response('CONTACT_NOT_FOUND', 'Contact not found', 404)

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return make_error_response('BAD_REQUEST', 'Invalid request body. Expected JSON object.', 400)

        name = str(data.get('name', existing['name'])).strip()
        phone = str(data.get('phone', existing['phone'])).strip()
        relationship = str(data.get('relationship', existing['relationship'])).strip()
        is_primary = bool(data.get('is_primary', existing['is_primary']))
        enabled = bool(data.get('enabled', existing['enabled']))

        is_valid, err_msg, formatted_phone = database.validate_contact_input(
            name, phone, relationship, contact_id=contact_id
        )
        if not is_valid:
            return make_error_response('INVALID_CONTACT', err_msg, 400)

        updated = database.update_contact(
            contact_id=contact_id,
            name=name,
            phone=formatted_phone,
            relationship=relationship,
            is_primary=is_primary,
            enabled=enabled
        )

        if not updated:
            return make_error_response('CONTACT_NOT_FOUND', 'Contact not found', 404)

        return jsonify({
            'status': 'success',
            'message': 'Contact updated successfully',
            'contact': updated
        }), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error in PUT /api/contacts/{contact_id}: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to save emergency contact.', 500)
    except Exception as e:
        app.logger.error(f"Error in PUT /api/contacts/{contact_id}: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to save emergency contact.', 500)


@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """
    DELETE /api/contacts/<id>
    Deletes an existing emergency contact.
    """
    try:
        deleted = database.delete_contact(contact_id)
        if not deleted:
            return make_error_response('CONTACT_NOT_FOUND', 'Contact not found', 404)

        return jsonify({
            'status': 'success',
            'message': 'Contact deleted successfully'
        }), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error in DELETE /api/contacts/{contact_id}: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to delete emergency contact.', 500)
    except Exception as e:
        app.logger.error(f"Error in DELETE /api/contacts/{contact_id}: {e}")
        return make_error_response('DATABASE_ERROR', 'Unable to delete emergency contact.', 500)


# -------------------------------------------------------------------------
# Test & Error Simulation Endpoints (for resilience testing)
# -------------------------------------------------------------------------

@app.route('/api/test/error/<int:code>', methods=['GET', 'POST'])
def test_error_route(code):
    """Simulates HTTP error status codes with standard error JSON format."""
    code_map = {
        400: ('BAD_REQUEST', 'Simulated 400 Bad Request error'),
        401: ('UNAUTHORIZED', 'Simulated 401 Unauthorized error'),
        403: ('FORBIDDEN', 'Simulated 403 Forbidden error'),
        404: ('NOT_FOUND', 'Simulated 404 Not Found error'),
        500: ('INTERNAL_ERROR', 'Simulated 500 Internal Server error'),
        503: ('SERVICE_UNAVAILABLE', 'Simulated 503 Service Unavailable error')
    }
    if code in code_map:
        err_code, msg = code_map[code]
        return make_error_response(err_code, msg, code)
    return make_error_response('HTTP_ERROR', f'Simulated error {code}', code)


@app.route('/api/test/invalid-json', methods=['GET', 'POST'])
def test_invalid_json_route():
    """Returns invalid/non-JSON content to test frontend JSON parse resilience."""
    from flask import Response
    return Response("<html><body>502 Bad Gateway - Upstream proxy failure</body></html>",
                    status=502,
                    mimetype="text/html")


@app.route('/api/test/timeout', methods=['GET', 'POST'])
def test_timeout_route():
    """Simulates a delayed response to test client timeout with AbortController."""
    import time
    time.sleep(3.5)
    return jsonify({'status': 'success', 'message': 'Delayed response completed'}), 200


# -------------------------------------------------------------------------
# Global Error Handlers (Ensuring JSON error consistency across all routes)
# -------------------------------------------------------------------------

@app.errorhandler(400)
def handle_400(error):
    msg = error.description if hasattr(error, 'description') and error.description else 'Bad request.'
    return make_error_response('BAD_REQUEST', msg, 400)


@app.errorhandler(401)
def handle_401(error):
    return make_error_response('UNAUTHORIZED', 'Authentication credentials are required.', 401)


@app.errorhandler(403)
def handle_403(error):
    return make_error_response('FORBIDDEN', 'Access to this resource is forbidden.', 403)


@app.errorhandler(404)
def handle_404(error):
    if request.path.startswith('/api/'):
        return make_error_response('NOT_FOUND', f"API endpoint '{request.path}' was not found on this server.", 404)
    # For non-API routes, return standard 404
    return error


@app.errorhandler(500)
def handle_500(error):
    return make_error_response('INTERNAL_ERROR', 'An unexpected internal server error occurred.', 500)


@app.errorhandler(503)
def handle_503(error):
    return make_error_response('SERVICE_UNAVAILABLE', 'The SafeHer service is temporarily unavailable.', 503)


@app.errorhandler(Exception)
def handle_general_exception(error):
    if isinstance(error, HTTPException):
        code = error.code or 500
        error_code_map = {
            400: 'BAD_REQUEST',
            401: 'UNAUTHORIZED',
            403: 'FORBIDDEN',
            404: 'NOT_FOUND',
            500: 'INTERNAL_ERROR',
            503: 'SERVICE_UNAVAILABLE'
        }
        return make_error_response(error_code_map.get(code, 'HTTP_ERROR'), error.description or str(error), code)

    if isinstance(error, sqlite3.Error):
        app.logger.error(f"Global handler caught database error: {error}")
        return make_error_response('DATABASE_ERROR', f"Database operation failed: {str(error)}", 500)

    app.logger.error(f"Global handler caught unhandled exception: {error}")
    return make_error_response('INTERNAL_ERROR', f"Internal server error: {str(error)}", 500)


if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    print("=" * 65)
    print("  [SafeHer] Women Safety Navigation Backend Server")
    print(f"  Running on: http://{host}:{port}")
    print("  Available Endpoints:")
    print("      * POST   /api/routes")
    print("      * GET    /api/safety-zones")
    print("      * GET    /api/police-stations")
    print("      * POST   /api/sos")
    print("      * POST   /api/chat")
    print("      * GET    /api/contacts          [Emergency Contacts]")
    print("      * POST   /api/contacts          [Add Contact]")
    print("      * PUT    /api/contacts/<id>     [Update Contact]")
    print("      * DELETE /api/contacts/<id>     [Delete Contact]")
    print("      * POST   /api/call/emergency    [Automated Voice Call]")
    print("      * POST   /api/ml-predict        [ML Risk Classifier]")
    print("      * GET    /api/ml-info           [Model Evaluation]")
    print("      * GET    /api/health")
    print("=" * 65)
    sys.stdout.flush()
    debug_mode = os.environ.get('FLASK_DEBUG', '0').lower() in ('true', '1')
    app.run(host=host, port=port, debug=debug_mode, use_reloader=False, threaded=True)


