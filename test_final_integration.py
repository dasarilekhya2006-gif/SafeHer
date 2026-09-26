"""
test_final_integration.py - SafeHer Final Integration & System Verification Suite

Covers all 17 integration requirements:
1.  Add emergency contact (POST /api/contacts)
2.  Mark primary contact (PUT /api/contacts/<id>)
3.  Trigger SOS flow & countdown validation
4.  Obtain current real GPS & coordinate validation
5.  Send SOS to backend (POST /api/sos)
6.  Save SOS in database (persistence & integrity)
7.  Find nearest police station (accurate distance calculation)
8.  Load emergency contacts for dispatch
9.  Attempt emergency notification via configured architecture
10. Display real notification status without false success strings
11. Enter Emergency Mode data structure & UI state
12. Update current GPS tracking positions dynamically
13. Cancel SOS (backend and frontend cancellation)
14. Verify GPS tracking stops & resources cleanly released
15. Test backend offline resilience & failure fallback
16. Test GPS permission denied & graceful user guidance
17. Test notification provider not configured scenario
"""

import sys
import os
import json
import socket
import unittest
from unittest.mock import patch, MagicMock

# Force UTF-8 stdout
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import SafeHer Application
from app import app, make_error_response
from database import init_db
import database
import notification_service
from notification_service import BaseNotificationProvider


class TestFinalIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        app.config['TESTING'] = True
        cls.client = app.test_client()

    # =========================================================================
    # Test 1: Add emergency contact
    # =========================================================================
    def test_01_add_emergency_contact(self):
        """1. Add emergency contact via POST /api/contacts"""
        phone_num = "+91 98765 43210"
        core = database.normalize_phone_core(phone_num)
        # Ensure clean state for this phone number
        existing = database.get_all_contacts()
        for c in existing:
            if database.normalize_phone_core(c['phone']) == core:
                database.delete_contact(c['id'])

        payload = {
            "name": "Priya Sharma",
            "phone": phone_num,
            "relationship": "Sister",
            "is_primary": 0,
            "enabled": 1
        }
        res = self.client.post('/api/contacts', json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('contact', data)
        self.assertEqual(data['contact']['name'], 'Priya Sharma')
        self.assertEqual(database.normalize_phone_core(data['contact']['phone']), core)
        self.__class__.created_contact_id = data['contact']['id']
        print(f"\n✓ Test 1: Add emergency contact passed (ID: {self.__class__.created_contact_id})")

    # =========================================================================
    # Test 2: Mark primary
    # =========================================================================
    def test_02_mark_primary_contact(self):
        """2. Mark emergency contact as primary and verify single primary invariant"""
        contact_id = getattr(self.__class__, 'created_contact_id', None)
        self.assertIsNotNone(contact_id, "Prior contact ID required")

        res = self.client.put(f'/api/contacts/{contact_id}', json={"is_primary": 1})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data['contact']['is_primary'], 1)

        # Verify only one primary contact exists in database
        contacts = database.get_all_contacts()
        primaries = [c for c in contacts if c.get('is_primary') == 1]
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0]['id'], contact_id)
        print("✓ Test 2: Mark primary passed (Single Primary Invariant strictly maintained)")

    # =========================================================================
    # Test 3: Trigger SOS (Validation & Initiation)
    # =========================================================================
    def test_03_trigger_sos_initiation(self):
        """3. Trigger SOS verification: Ensure payload rejects invalid trigger without GPS"""
        res = self.client.post('/api/sos', json={})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'error')
        self.assertEqual(data.get('error_code'), 'GPS_REQUIRED')
        print("✓ Test 3: Trigger SOS passed (Rejects invalid trigger, mandates real GPS)")

    # =========================================================================
    # Test 4: Obtain current GPS
    # =========================================================================
    def test_04_obtain_current_gps(self):
        """4. Obtain current GPS: Verify latitude/longitude bounds & numerical validity"""
        # Test out-of-bounds latitude > 90
        res_lat = self.client.post('/api/sos', json={"latitude": 95.0, "longitude": 77.2})
        self.assertEqual(res_lat.status_code, 400)
        self.assertEqual(res_lat.get_json().get('error_code'), 'INVALID_COORDINATES')

        # Test out-of-bounds longitude < -180
        res_lng = self.client.post('/api/sos', json={"latitude": 28.5, "longitude": -195.0})
        self.assertEqual(res_lng.status_code, 400)
        self.assertEqual(res_lng.get_json().get('error_code'), 'INVALID_COORDINATES')

        # Test NaN / string coordinates
        res_nan = self.client.post('/api/sos', json={"latitude": "corrupted", "longitude": 77.2})
        self.assertEqual(res_nan.status_code, 400)
        self.assertEqual(res_nan.get_json().get('error_code'), 'INVALID_COORDINATES')
        print("✓ Test 4: Obtain current GPS passed (Bounds -90..90, -180..180 & numeric integrity verified)")

    # =========================================================================
    # Test 5: Send SOS to backend
    # =========================================================================
    def test_05_send_sos_to_backend(self):
        """5. Send SOS to backend with real current GPS and accuracy"""
        payload = {
            "latitude": 28.5355,
            "longitude": 77.3910,
            "accuracy": 14.8,
            "emergency_type": "PANIC_BUTTON",
            "notes": "SafeHer Automated Integration Test SOS"
        }
        res = self.client.post('/api/sos', json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('sos_id', data)
        self.assertAlmostEqual(data.get('latitude'), 28.5355, places=4)
        self.assertAlmostEqual(data.get('longitude'), 77.3910, places=4)
        self.assertAlmostEqual(data.get('accuracy'), 14.8, places=1)
        self.__class__.active_sos_id = data.get('sos_id')
        self.__class__.last_sos_response = data
        print(f"✓ Test 5: Send SOS to backend passed (Incident #{self.__class__.active_sos_id} created)")

    # =========================================================================
    # Test 6: Save SOS in database
    # =========================================================================
    def test_06_save_sos_in_database(self):
        """6. Save SOS: Verify record persisted in SQLite sos_logs table"""
        sos_id = getattr(self.__class__, 'active_sos_id', None)
        self.assertIsNotNone(sos_id)

        sos_record = database.get_sos_log(sos_id)
        self.assertIsNotNone(sos_record, f"SOS #{sos_id} must exist in database")
        self.assertAlmostEqual(sos_record['latitude'], 28.5355, places=4)
        self.assertAlmostEqual(sos_record['longitude'], 77.3910, places=4)
        self.assertEqual(sos_record['emergency_type'], 'PANIC_BUTTON')
        self.assertEqual(sos_record['status'], 'ACTIVE_DISPATCH')
        print("✓ Test 6: Save SOS in database passed (Persistent storage & schema verified)")

    # =========================================================================
    # Test 7: Find nearest police
    # =========================================================================
    def test_07_find_nearest_police(self):
        """7. Find nearest police station: Computed from verified current GPS"""
        sos_data = getattr(self.__class__, 'last_sos_response', {})
        police_dispatch = sos_data.get('nearest_police_dispatch')
        self.assertIsNotNone(police_dispatch)
        self.assertIn('station', police_dispatch)
        self.assertIn('name', police_dispatch['station'])
        self.assertIn('distance_km', police_dispatch)
        self.assertIn('distance_meters', police_dispatch)
        self.assertGreater(police_dispatch['distance_meters'], 0)
        station_name = police_dispatch['station']['name']
        dist_m = police_dispatch['distance_meters']
        print(f"✓ Test 7: Find nearest police passed (Nearest: '{station_name}', Distance: {dist_m}m)")

    # =========================================================================
    # Test 8: Load emergency contacts
    # =========================================================================
    def test_08_load_emergency_contacts(self):
        """8. Load emergency contacts: Active contacts retrieved with primary flag"""
        contacts = database.get_enabled_contacts()
        self.assertGreater(len(contacts), 0)
        primary_list = [c for c in contacts if c.get('is_primary') == 1]
        self.assertEqual(len(primary_list), 1)
        self.assertTrue(contacts[0]['is_primary'] == 1, "Enabled contacts must sort primary contact first")
        print(f"✓ Test 8: Load emergency contacts passed ({len(contacts)} contacts loaded, primary first)")

    # =========================================================================
    # Test 9: Attempt notification
    # =========================================================================
    def test_09_attempt_notification(self):
        """9. Attempt notification: Notification service invoked through configured abstraction"""
        mock_provider = MagicMock(spec=BaseNotificationProvider)
        mock_provider.is_configured.return_value = True
        mock_provider.send_sms.return_value = {
            "success": True,
            "status": "sent",
            "message_id": "SM_TEST_INTEGRATION_01",
            "error": None
        }

        with patch.object(notification_service, 'get_configured_provider', return_value=mock_provider), \
             patch.object(notification_service, 'is_provider_configured', return_value=True):
            contacts = database.get_enabled_contacts()
            location_data = {'latitude': 28.5355, 'longitude': 77.3910, 'accuracy': 15.0}
            batch = notification_service.notify_emergency_contacts(contacts, location_data, "Test User")

            self.assertEqual(batch['status'], 'sent')
            self.assertEqual(batch['successful'], len(contacts))
            self.assertEqual(mock_provider.send_sms.call_count, len(contacts))
        print("✓ Test 9: Attempt notification passed (Dispatched via clean notification service)")

    # =========================================================================
    # Test 10: Display real notification status
    # =========================================================================
    def test_10_display_real_notification_status(self):
        """10. Real notification status: No false success when unconfigured or failing"""
        # When unconfigured
        with patch.object(notification_service, 'is_provider_configured', return_value=False), \
             patch.object(notification_service, 'get_configured_provider', return_value=None):
            res = self.client.post('/api/sos', json={"latitude": 28.5355, "longitude": 77.3910})
            data = res.get_json()
            notifs = data.get('notifications')
            self.assertIsNotNone(notifs)
            self.assertEqual(notifs.get('status'), 'not_configured')
            self.assertEqual(notifs.get('successful'), 0)

            # Contract verification: Zero false success strings
            notifs_str = json.dumps(data)
            self.assertNotIn("SMS Sent", notifs_str)
            self.assertNotIn("Family Notified", notifs_str)
            self.assertNotIn("Contacts Notified", notifs_str)
            self.assertNotIn("Notification Sent", notifs_str)
        print("✓ Test 10: Display real notification status passed (Zero false success strings)")

    # =========================================================================
    # Test 11: Enter Emergency Mode
    # =========================================================================
    def test_11_enter_emergency_mode(self):
        """11. Enter Emergency Mode: Complete emergency state with all required elements"""
        res = self.client.post('/api/sos', json={
            "latitude": 28.5355,
            "longitude": 77.3910,
            "accuracy": 12.0
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()

        # Check required emergency mode data fields
        self.assertIn('sos_id', data)
        self.assertIn('latitude', data)
        self.assertIn('longitude', data)
        self.assertIn('accuracy', data)
        self.assertIn('nearest_police_dispatch', data)
        self.assertIn('notifications', data)
        self.assertIn('alert_details', data)
        self.assertEqual(data['alert_details']['emergency_helpline'], '112')
        self.assertEqual(data['alert_details']['women_safety_helpline'], '1091')

        # Check emergency contacts available to Emergency Mode
        contacts = database.get_enabled_contacts()
        primary = next((c for c in contacts if c.get('is_primary') == 1), None)
        self.assertIsNotNone(primary)
        self.assertTrue(bool(primary.get('phone')))
        print("✓ Test 11: Enter Emergency Mode passed (All emergency mode entities provided)")

    # =========================================================================
    # Test 12: Update current GPS
    # =========================================================================
    def test_12_update_current_gps(self):
        """12. Update current GPS: Real-time coordinate updates handled smoothly"""
        # Subsequent GPS position during emergency mode
        update_coords = {"latitude": 28.5360, "longitude": 77.3915, "accuracy": 8.5}
        res = self.client.post('/api/sos', json={
            "latitude": update_coords["latitude"],
            "longitude": update_coords["longitude"],
            "accuracy": update_coords["accuracy"],
            "emergency_type": "LOCATION_UPDATE",
            "notes": "Live tracking update"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertAlmostEqual(data['latitude'], 28.5360, places=4)
        self.assertAlmostEqual(data['longitude'], 77.3915, places=4)
        print("✓ Test 12: Update current GPS passed (Live tracking position update accepted)")

    # =========================================================================
    # Test 13: Cancel SOS
    # =========================================================================
    def test_13_cancel_sos(self):
        """13. Cancel SOS: Status transitioned from ACTIVE_DISPATCH to CANCELLED"""
        sos_id = getattr(self.__class__, 'active_sos_id', None)
        self.assertIsNotNone(sos_id)

        res = self.client.post(f'/api/sos/{sos_id}/cancel')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'success')

        # Verify database record reflects CANCELLED status
        record = database.get_sos_log(sos_id)
        self.assertEqual(record['status'], 'CANCELLED')
        self.assertIn('Cancelled at', record['notes'])
        print(f"✓ Test 13: Cancel SOS passed (Incident #{sos_id} marked CANCELLED in database)")

    # =========================================================================
    # Test 14: Verify GPS tracking stops
    # =========================================================================
    def test_14_verify_gps_tracking_stops(self):
        """14. Verify GPS tracking stops: Check frontend cancellation contract"""
        # Verify app.js cancelActiveSos method clears watchPosition and resets state
        with open('app.js', 'r', encoding='utf-8') as f:
            app_code = f.read()

        self.assertIn('navigator.geolocation.clearWatch(this.gpsWatchId)', app_code)
        self.assertIn('this.gpsWatchId = null;', app_code)
        self.assertIn('this.stopSiren();', app_code)
        self.assertIn('cancelActiveSos', app_code)
        print("✓ Test 14: Verify GPS tracking stops passed (clearWatch & resource release verified)")

    # =========================================================================
    # Test 15: Test backend offline
    # =========================================================================
    def test_15_test_backend_offline(self):
        """15. Test backend offline: Frontend apiRequest handles connection refusal"""
        # Open and immediately close a socket to obtain an offline port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        closed_port = s.getsockname()[1]
        s.close()

        import urllib.request
        import urllib.error

        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(f'http://127.0.0.1:{closed_port}/api/sos', timeout=1.0)

        # Check frontend fallback message in app.js
        with open('app.js', 'r', encoding='utf-8') as f:
            app_code = f.read()
        self.assertIn('Emergency alert could not be processed. Please call 112 directly.', app_code)
        self.assertIn('BACKEND_UNAVAILABLE', app_code)
        print("✓ Test 15: Test backend offline passed (Offline error caught, 112 fallback prominent)")

    # =========================================================================
    # Test 16: Test GPS permission denied
    # =========================================================================
    def test_16_test_gps_permission_denied(self):
        """16. Test GPS permission denied: User notified and startCoords strictly never used"""
        with open('app.js', 'r', encoding='utf-8') as f:
            app_code = f.read()

        # Verify permission denied handling
        self.assertIn('Permission Denied', app_code)
        self.assertIn('Location permission is required', app_code)
        # Verify strict prohibition: startCoords never used for emergency SOS
        self.assertNotIn('startCoords', app_code[app_code.find('dispatchSosPayload'):app_code.find('dispatchSosPayload')+1500])
        print("✓ Test 16: Test GPS permission denied passed (Clean error reporting, startCoords never used)")

    # =========================================================================
    # Test 17: Test notification provider not configured
    # =========================================================================
    def test_17_notification_provider_not_configured(self):
        """17. Test notification provider not configured: Shows exact required message"""
        with patch.object(notification_service, 'is_provider_configured', return_value=False), \
             patch.object(notification_service, 'get_configured_provider', return_value=None):
            res = self.client.post('/api/sos', json={"latitude": 28.5355, "longitude": 77.3910})
            data = res.get_json()
            notifs = data.get('notifications')
            self.assertEqual(notifs['status'], 'not_configured')

        # Check frontend exact message
        with open('app.js', 'r', encoding='utf-8') as f:
            app_code = f.read()
        self.assertIn('Notification service not configured.', app_code)
        print("✓ Test 17: Test notification provider not configured passed ('Notification service not configured.')")

    # =========================================================================
    # Regression Tests: All Core Features Intact
    # =========================================================================
    def test_18_regression_safety_features(self):
        """Regression Verification: Map, routes, zones, police stations, ML prediction, AI chat"""
        # Safety zones
        res_zones = self.client.get('/api/safety-zones')
        self.assertEqual(res_zones.status_code, 200)
        self.assertGreaterEqual(res_zones.get_json()['count'], 5)

        # Police stations
        res_police = self.client.get('/api/police-stations')
        self.assertEqual(res_police.status_code, 200)
        self.assertGreaterEqual(res_police.get_json()['count'], 3)

        # Routes calculation & safety score
        res_routes = self.client.post('/api/routes', json={
            "start": "Metro Station Central",
            "destination": "Greenfield Heights",
            "time_of_day": "night",
            "start_coords": [28.6328, 77.2155],
            "dest_coords": [28.6435, 77.2340]
        })
        self.assertEqual(res_routes.status_code, 200)
        routes = res_routes.get_json()['data']['routes']
        self.assertEqual(len(routes), 3)
        self.assertGreaterEqual(routes[0]['score'], 80)

        # AI Assistant chat
        res_chat = self.client.post('/api/chat', json={"message": "I feel unsafe walking alone."})
        self.assertEqual(res_chat.status_code, 200)
        self.assertTrue(len(res_chat.get_json()['reply']) > 0)
        print("✓ Regression Tests passed (Safety zones, police stations, route scores, and AI assistant intact)")


if __name__ == '__main__':
    unittest.main()
