#!/usr/bin/env python
"""
Test script for Twilio SMS, voice, and email integration.

Usage:
    export TWILIO_ACCOUNT_SID="your_account_sid"
    export TWILIO_AUTH_TOKEN="your_auth_token"
    export TWILIO_PHONE_NUMBER="+15551234567"
    export SMTP_USER="your_email@gmail.com"
    export SMTP_PASSWORD="your_app_password"
    python scripts/test_twilio.py

Note:
- Twilio trial accounts can only send to verified numbers
- Add your phone number in Twilio console first
- SMTP assumes Gmail; update SMTP_SERVER/.env if using different provider
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from backend.app.agents.twilio_multichannel import make_voice_call, send_email, send_sms


def run_twilio_test():
    """Run Twilio integration tests."""
    print("=" * 72)
    print("TWILIO INTEGRATION TEST")
    print("=" * 72)

    # Get test number from user
    print("\nEnter your phone number for testing (e.g., +15551234567 or 5551234567):")
    test_phone = input("Phone: ").strip()

    test_email = input("Enter your email for testing (or press Enter to skip): ").strip()

    if not test_phone:
        print("Phone number required. Aborting.")
        return 1

    print("\n" + "=" * 72)
    print("Running tests...")
    print("=" * 72)

    # Test 1: SMS
    print("\n[1/3] Testing SMS...")
    result = send_sms(test_phone, "Hello from Imperial Cars AI! This is a test SMS.")
    print(f"Result: {result}")
    if result.get("status") == "sent":
        print("✓ SMS test passed")
    else:
        print("✗ SMS test failed")

    # Test 2: Voice call
    print("\n[2/3] Testing voice call...")
    result = make_voice_call(test_phone, "This is a test call from Imperial Cars AI.")
    print(f"Result: {result}")
    if result.get("status") == "initiated":
        print("✓ Voice call test initiated")
    else:
        print("✗ Voice call test failed")

    # Test 3: Email (optional)
    if test_email:
        print("\n[3/3] Testing email...")
        result = send_email(
            test_email,
            "Test from Imperial Cars AI",
            "<h2>Hello!</h2><p>This is a test email from Imperial Cars AI.</p>"
        )
        print(f"Result: {result}")
        if result.get("status") == "sent":
            print("✓ Email test passed")
        else:
            print("✗ Email test failed")
    else:
        print("\n[3/3] Email test skipped (no email provided)")

    print("\n" + "=" * 72)
    print("Tests complete!")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(run_twilio_test())
