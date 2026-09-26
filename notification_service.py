"""
notification_service.py - Emergency Notification Architecture for SafeHer

Implements a clean provider-agnostic notification service:
SOS API -> Notification Service -> Configured Notification Provider

Follows strict guidelines:
- Never fakes SMS delivery.
- Uses .env configuration for credentials (never hard-coded).
- Returns status 'not_configured' when credentials or provider are missing.
- Provides clean abstraction: send_emergency_alert(contact, location_data).
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Lightweight .env file loader (Zero external dependency requirement)
# ---------------------------------------------------------------------------
def load_env_file(base_dir: Optional[Path] = None) -> None:
    """
    Loads key=value pairs from a .env file in the workspace directory into os.environ.
    Does not overwrite existing environment variables.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent

    env_path = base_dir / '.env'
    if not env_path.is_file():
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        # Silently pass on read error to prevent crashing startup
        pass


# Load .env immediately on module import
load_env_file()


# ---------------------------------------------------------------------------
# Provider Interface and Implementations
# ---------------------------------------------------------------------------
class BaseNotificationProvider:
    """Abstract base class for all SMS / emergency notification providers."""

    def is_configured(self) -> bool:
        """Returns True if the provider has all required credentials configured."""
        raise NotImplementedError

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS message to a single phone number.
        Returns:
            {
                "success": bool,
                "status": "sent" | "failed" | "not_configured",
                "message_id": Optional[str],
                "error": Optional[str]
            }
        """
        raise NotImplementedError


class NullNotificationProvider(BaseNotificationProvider):
    """Fallback provider used when no valid SMS provider is configured."""

    def is_configured(self) -> bool:
        return False

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "status": "not_configured",
            "message_id": None,
            "error": "SMS notification service is not configured."
        }


class TwilioNotificationProvider(BaseNotificationProvider):
    """
    Real Twilio SMS Provider.
    Requires:
      - TWILIO_ACCOUNT_SID (or SMS_API_KEY)
      - TWILIO_AUTH_TOKEN  (or SMS_API_SECRET)
      - TWILIO_FROM_NUMBER (or SMS_FROM_NUMBER)
    Uses Python standard 'requests' library to call Twilio REST API.
    """

    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID') or os.getenv('SMS_API_KEY') or ''
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN') or os.getenv('SMS_API_SECRET') or ''
        self.from_number = os.getenv('TWILIO_FROM_NUMBER') or os.getenv('SMS_FROM_NUMBER') or ''

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "success": False,
                "status": "not_configured",
                "message_id": None,
                "error": "Twilio credentials incomplete in environment."
            }

        try:
            import requests
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            data = {
                "From": self.from_number,
                "To": to_phone,
                "Body": message
            }
            resp = requests.post(url, data=data, auth=(self.account_sid, self.auth_token), timeout=10)

            if resp.status_code in (200, 201):
                res_data = resp.json()
                return {
                    "success": True,
                    "status": "sent",
                    "message_id": res_data.get("sid"),
                    "error": None
                }
            else:
                err_text = resp.text
                try:
                    err_json = resp.json()
                    err_text = err_json.get('message', err_text)
                except Exception:
                    pass
                return {
                    "success": False,
                    "status": "failed",
                    "message_id": None,
                    "error": f"Twilio API error ({resp.status_code}): {err_text}"
                }
        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "message_id": None,
                "error": f"Twilio connection exception: {str(e)}"
            }

    def make_call(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Places an automated emergency voice call using Twilio Programmable Voice.
        """
        if not self.is_configured():
            return {
                "success": False,
                "status": "not_configured",
                "call_id": None,
                "error": "Twilio credentials incomplete in environment."
            }

        try:
            import requests
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json"
            twiml_content = f"<Response><Say voice='alice'>{message}</Say></Response>"
            data = {
                "From": self.from_number,
                "To": to_phone,
                "Twiml": twiml_content
            }
            resp = requests.post(url, data=data, auth=(self.account_sid, self.auth_token), timeout=10)

            if resp.status_code in (200, 201):
                res_data = resp.json()
                return {
                    "success": True,
                    "status": "initiated",
                    "call_id": res_data.get("sid"),
                    "error": None
                }
            else:
                err_text = resp.text
                try:
                    err_text = resp.json().get('message', err_text)
                except Exception:
                    pass
                return {
                    "success": False,
                    "status": "failed",
                    "call_id": None,
                    "error": f"Twilio Voice error ({resp.status_code}): {err_text}"
                }
        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "call_id": None,
                "error": f"Twilio Voice connection exception: {str(e)}"
            }


class Fast2SMSNotificationProvider(BaseNotificationProvider):
    """
    Fast2SMS Provider for sending SMS in India.
    Requires: FAST2SMS_API_KEY
    """

    def __init__(self):
        self.api_key = (os.getenv('FAST2SMS_API_KEY') or '').strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "success": False,
                "status": "not_configured",
                "message_id": None,
                "error": "Fast2SMS API key missing in environment."
            }

        # Fast2SMS expects 10-digit Indian numbers
        digits = re.sub(r'\D', '', to_phone)
        if digits.startswith('91') and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith('0') and len(digits) == 11:
            digits = digits[1:]

        if len(digits) != 10:
            return {
                "success": False,
                "status": "failed",
                "message_id": None,
                "error": f"Fast2SMS requires a valid 10-digit Indian mobile number, got {to_phone}"
            }

        try:
            import requests
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {
                "authorization": self.api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "route": "q",
                "message": message,
                "language": "english",
                "flash": 0,
                "numbers": digits
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json() if resp.status_code == 200 else {}
            if resp.status_code == 200 and data.get("return") is True:
                req_id = data.get("request_id") or "F2SMS-SENT"
                return {
                    "success": True,
                    "status": "sent",
                    "message_id": str(req_id),
                    "error": None
                }
            else:
                err_msg = data.get("message")
                if isinstance(err_msg, list):
                    err_msg = ", ".join(str(m) for m in err_msg)
                elif not err_msg:
                    err_msg = resp.text
                return {
                    "success": False,
                    "status": "failed",
                    "message_id": None,
                    "error": f"Fast2SMS API error: {err_msg}"
                }
        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "message_id": None,
                "error": f"Fast2SMS connection exception: {str(e)}"
            }


class MockNotificationProvider(BaseNotificationProvider):
    """
    Mock Provider used solely for automated tests and sandbox verification.
    Activated only when SMS_PROVIDER is explicitly set to 'mock' or 'test'.
    Allows simulating successful sends and controlled failure scenarios.
    """

    def __init__(self):
        self.simulated_failure_numbers = set(
            filter(None, [n.strip() for n in os.getenv('MOCK_FAIL_NUMBERS', '+91-9999999999').split(',')])
        )

    def is_configured(self) -> bool:
        return True

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        clean_phone = re.sub(r'[\s\-()]', '', to_phone)
        for fail_pattern in self.simulated_failure_numbers:
            clean_pattern = re.sub(r'[\s\-()]', '', fail_pattern)
            if clean_pattern and clean_pattern in clean_phone:
                return {
                    "success": False,
                    "status": "failed",
                    "message_id": None,
                    "error": f"Simulated delivery failure for {to_phone}"
                }

        import uuid
        return {
            "success": True,
            "status": "sent",
            "message_id": f"MOCK-{uuid.uuid4().hex[:12].upper()}",
            "error": None
        }

    def make_call(self, to_phone: str, message: str) -> Dict[str, Any]:
        import uuid
        return {
            "success": True,
            "status": "initiated",
            "call_id": f"CA_MOCK_{uuid.uuid4().hex[:12].upper()}",
            "error": None
        }


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------
def get_configured_provider() -> BaseNotificationProvider:
    """
    Factory that instantiates the active provider based on environment variables.
    Returns NullNotificationProvider if SMS_PROVIDER is not set or credentials missing.
    """
    # Reload environment to catch dynamic runtime configurations
    load_env_file()

    provider_name = (os.getenv('SMS_PROVIDER') or '').strip().lower()

    if provider_name == 'twilio':
        provider = TwilioNotificationProvider()
        if provider.is_configured():
            return provider
        return NullNotificationProvider()

    elif provider_name == 'fast2sms':
        provider = Fast2SMSNotificationProvider()
        if provider.is_configured():
            return provider
        return NullNotificationProvider()

    elif provider_name in ('mock', 'test'):
        return MockNotificationProvider()

    # Automatic detection if SMS_PROVIDER is not explicitly specified:
    if os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
        provider = TwilioNotificationProvider()
        if provider.is_configured():
            return provider

    if os.getenv('FAST2SMS_API_KEY'):
        provider = Fast2SMSNotificationProvider()
        if provider.is_configured():
            return provider

    # If no recognized provider or SMS_PROVIDER is blank:
    return NullNotificationProvider()


def is_provider_configured() -> bool:
    """Checks whether a valid, authenticated SMS provider is currently active."""
    provider = get_configured_provider()
    return provider.is_configured()


# ---------------------------------------------------------------------------
# Core Notification Service Methods
# ---------------------------------------------------------------------------
def format_emergency_message(contact: Dict[str, Any], location_data: Dict[str, Any], user_name: str = 'SafeHer User') -> str:
    """
    Builds the emergency SMS message body with real-time GPS coordinates and Google Maps link.
    """
    lat = location_data.get('latitude')
    lng = location_data.get('longitude')
    accuracy = location_data.get('accuracy')
    location_name = location_data.get('location_name') or f"Lat {lat}, Lng {lng}"

    acc_str = f" (±{round(accuracy)}m)" if accuracy is not None else ""
    maps_link = f"https://maps.google.com/?q={lat},{lng}"

    return (
        f"🚨 SafeHer EMERGENCY ALERT: {user_name} has triggered an SOS panic alert! "
        f"Location: {location_name}{acc_str}. "
        f"Live Map: {maps_link} - Please assist immediately or contact emergency services (112)."
    )


def send_emergency_alert(contact: Dict[str, Any], location_data: Dict[str, Any], user_name: str = 'SafeHer User') -> Dict[str, Any]:
    """
    Clean abstraction to send an emergency alert to a single contact.

    Args:
        contact: dict with keys {'id', 'name', 'phone', 'relationship', 'enabled'}
        location_data: dict with keys {'latitude', 'longitude', 'accuracy', 'location_name'}
        user_name: string user identifier

    Returns:
        {
            "success": bool,
            "status": "sent" | "failed" | "not_configured",
            "message_id": Optional[str],
            "error": Optional[str]
        }
    """
    provider = get_configured_provider()
    if not provider.is_configured():
        return {
            "success": False,
            "status": "not_configured",
            "message_id": None,
            "error": "SMS notification service is not configured."
        }

    phone = (contact.get('phone') or '').strip()
    if not phone:
        return {
            "success": False,
            "status": "failed",
            "message_id": None,
            "error": "Contact has no phone number specified."
        }

    # Verify contact is enabled
    if not contact.get('enabled', True):
        return {
            "success": False,
            "status": "failed",
            "message_id": None,
            "error": "Contact is currently disabled."
        }

    message_body = format_emergency_message(contact, location_data, user_name)
    return provider.send_sms(to_phone=phone, message=message_body)


def notify_emergency_contacts(contacts: List[Dict[str, Any]], location_data: Dict[str, Any], user_name: str = 'SafeHer User') -> Dict[str, Any]:
    """
    Sends emergency alerts to all provided (enabled) emergency contacts and collects results.

    Returns:
        {
            "attempted": int,
            "successful": int,
            "failed": int,
            "status": "sent" | "partial" | "failed" | "not_configured" | "no_contacts",
            "details": List[dict]
        }
    """
    # Filter to enabled contacts only
    active_contacts = [c for c in contacts if c.get('enabled', True)]

    # 1. Check if provider is configured
    if not is_provider_configured():
        return {
            "attempted": len(active_contacts),
            "successful": 0,
            "failed": 0,
            "status": "not_configured",
            "details": [
                {
                    "contact_id": c.get('id'),
                    "name": c.get('name'),
                    "phone": c.get('phone'),
                    "status": "not_configured",
                    "error": "SMS notification service is not configured."
                }
                for c in active_contacts
            ]
        }

    # 2. Check if no contacts exist
    if not active_contacts:
        return {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "status": "no_contacts",
            "details": []
        }

    # 3. Dispatch to all contacts and collect actual results
    attempted = len(active_contacts)
    successful = 0
    failed = 0
    details = []

    for contact in active_contacts:
        res = send_emergency_alert(contact, location_data, user_name)
        detail_record = {
            "contact_id": contact.get('id'),
            "name": contact.get('name'),
            "phone": contact.get('phone'),
            "status": res.get("status"),
            "message_id": res.get("message_id"),
            "error": res.get("error")
        }
        details.append(detail_record)

        if res.get("success"):
            successful += 1
        else:
            failed += 1

    # 4. Determine aggregate status
    if successful == attempted:
        aggregate_status = "sent"
    elif successful > 0 and failed > 0:
        aggregate_status = "partial"
    else:
        aggregate_status = "failed"

    return {
        "attempted": attempted,
        "successful": successful,
        "failed": failed,
        "status": aggregate_status,
        "details": details
    }


def send_emergency_call(contact: Dict[str, Any], location_data: Optional[Dict[str, Any]] = None, user_name: str = 'SafeHer User') -> Dict[str, Any]:
    """
    Places an automated emergency voice call to the designated contact using the active voice provider.

    Returns:
        {
            "success": bool,
            "status": "initiated" | "failed" | "not_supported" | "not_configured",
            "call_id": Optional[str],
            "error": Optional[str]
        }
    """
    provider = get_configured_provider()
    if not provider.is_configured():
        return {
            "success": False,
            "status": "not_configured",
            "call_id": None,
            "error": "Voice calling provider is not configured."
        }

    if not hasattr(provider, 'make_call'):
        return {
            "success": False,
            "status": "not_supported",
            "call_id": None,
            "error": "Configured provider does not support automated voice calls."
        }

    phone = (contact.get('phone') or '').strip()
    if not phone:
        return {
            "success": False,
            "status": "failed",
            "call_id": None,
            "error": "Contact has no phone number."
        }

    message = (
        f"Emergency Alert from SafeHer. {user_name} has activated the emergency panic SOS. "
        f"Live GPS coordinates have been sent to your phone via SMS. Please check your SMS immediately."
    )
    return provider.make_call(to_phone=phone, message=message)

