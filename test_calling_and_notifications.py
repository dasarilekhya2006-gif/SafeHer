"""
Test Suite: SafeHer Emergency Calling & Notification Architecture
Tests:
- Native direct dialing (tel: links)
- Fast2SMS Indian SMS provider
- Twilio Programmable Voice & SMS
- Mock Notification & Calling Provider
- Automated Emergency Call API endpoint (/api/call/emergency)
"""

import unittest
import os
import json
from unittest.mock import patch, MagicMock

import app
import database
import notification_service


class TestCallingAndNotifications(unittest.TestCase):

    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True

    def test_mock_provider_sms_and_voice(self):
        """Verify Mock provider handles both emergency SMS and automated Voice calls."""
        with patch.dict(os.environ, {'SMS_PROVIDER': 'mock'}):
            provider = notification_service.get_configured_provider()
            self.assertTrue(provider.is_configured())

            # Test SMS
            sms_res = provider.send_sms('+91 93929 57232', 'SafeHer Emergency Test')
            self.assertTrue(sms_res['success'])
            self.assertEqual(sms_res['status'], 'sent')
            self.assertTrue(sms_res['message_id'].startswith('MOCK-'))

            # Test Automated Call
            call_res = provider.make_call('+91 93929 57232', 'SafeHer Voice Alert')
            self.assertTrue(call_res['success'])
            self.assertEqual(call_res['status'], 'initiated')
            self.assertTrue(call_res['call_id'].startswith('CA_MOCK_'))

    def test_fast2sms_provider_formatting(self):
        """Verify Fast2SMS handles Indian 10-digit mobile number normalization."""
        provider = notification_service.Fast2SMSNotificationProvider()
        # Missing key should return not_configured
        res = provider.send_sms('+91 93929 57232', 'Test alert')
        self.assertFalse(res['success'])
        self.assertEqual(res['status'], 'not_configured')

        # With key but invalid non-10 digit number
        with patch.dict(os.environ, {'FAST2SMS_API_KEY': 'fake_test_key'}):
            prov = notification_service.Fast2SMSNotificationProvider()
            self.assertTrue(prov.is_configured())
            invalid_res = prov.send_sms('123', 'Test alert')
            self.assertFalse(invalid_res['success'])
            self.assertIn('10-digit Indian mobile number', invalid_res['error'])

    @patch('requests.post')
    def test_fast2sms_provider_success(self, mock_post):
        """Verify Fast2SMS REST call structure and payload."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "return": True,
            "request_id": "REQ_F2SMS_12345",
            "message": ["SMS sent successfully"]
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {'FAST2SMS_API_KEY': 'live_test_api_key'}):
            provider = notification_service.Fast2SMSNotificationProvider()
            res = provider.send_sms('+91 93929 57232', 'SafeHer SOS Alert')
            self.assertTrue(res['success'])
            self.assertEqual(res['status'], 'sent')
            self.assertEqual(res['message_id'], 'REQ_F2SMS_12345')

    def test_twilio_provider_missing_credentials(self):
        """Verify Twilio safely reports not_configured when credentials are absent."""
        with patch.dict(os.environ, {'SMS_PROVIDER': 'twilio', 'TWILIO_ACCOUNT_SID': '', 'TWILIO_AUTH_TOKEN': '', 'TWILIO_FROM_NUMBER': ''}, clear=True):
            provider = notification_service.TwilioNotificationProvider()
            self.assertFalse(provider.is_configured())
            res = provider.send_sms('+91 93929 57232', 'Test')
            self.assertFalse(res['success'])
            self.assertEqual(res['status'], 'not_configured')

            call_res = provider.make_call('+91 93929 57232', 'Test')
            self.assertFalse(call_res['success'])
            self.assertEqual(call_res['status'], 'not_configured')

    @patch('requests.post')
    def test_twilio_voice_call_success(self, mock_post):
        """Verify Twilio Programmable Voice call REST request and TwiML generation."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "sid": "CA1234567890abcdef1234567890abcdef",
            "status": "queued"
        }
        mock_post.return_value = mock_resp

        env_vars = {
            'TWILIO_ACCOUNT_SID': 'AC_MOCK_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN': 'AUTH_MOCK_TOKEN',
            'TWILIO_FROM_NUMBER': '+15551234567'
        }
        with patch.dict(os.environ, env_vars):
            provider = notification_service.TwilioNotificationProvider()
            self.assertTrue(provider.is_configured())

            call_res = provider.make_call('+91 93929 57232', 'Emergency alert: Help needed')
            self.assertTrue(call_res['success'])
            self.assertEqual(call_res['status'], 'initiated')
            self.assertEqual(call_res['call_id'], 'CA1234567890abcdef1234567890abcdef')

            # Verify POST payload sent to Twilio
            called_url = mock_post.call_args[0][0]
            called_data = mock_post.call_args[1]['data']
            self.assertIn('AC_MOCK_ACCOUNT_SID/Calls.json', called_url)
            self.assertEqual(called_data['From'], '+15551234567')
            self.assertEqual(called_data['To'], '+91 93929 57232')
            self.assertIn('<Response><Say voice=\'alice\'>', called_data['Twiml'])

    def test_emergency_call_endpoint_mock_mode(self):
        """Verify POST /api/call/emergency initiates emergency voice call in mock mode."""
        with patch.dict(os.environ, {'SMS_PROVIDER': 'mock'}):
            response = self.app.post('/api/call/emergency',
                                     data=json.dumps({
                                         'phone': '+91 93929 57232',
                                         'name': 'mom',
                                         'user_name': 'SafeHer User'
                                     }),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'success')
            self.assertEqual(data['call']['status'], 'initiated')

    def test_emergency_call_endpoint_not_configured(self):
        """Verify POST /api/call/emergency returns 400 when no provider is set."""
        with patch.dict(os.environ, {'SMS_PROVIDER': '', 'TWILIO_ACCOUNT_SID': '', 'FAST2SMS_API_KEY': ''}, clear=True):
            response = self.app.post('/api/call/emergency',
                                     data=json.dumps({
                                         'phone': '+91 93929 57232',
                                         'name': 'mom'
                                     }),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 400)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'error')
            self.assertEqual(data['error_code'], 'NOTIFICATION_NOT_CONFIGURED')


if __name__ == '__main__':
    unittest.main()
