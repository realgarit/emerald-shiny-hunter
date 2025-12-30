#!/usr/bin/env python3
"""
Test Discord webhook notifications.
"""

import os
import sys
from pathlib import Path
import urllib.request
import urllib.parse
import json
from datetime import datetime

# Get project root directory (parent of src/, which is parent of debug/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env file from project root
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[+] Loaded .env file from: {env_path}")
    else:
        print(f"[!] .env file not found at: {env_path}")
except ImportError:
    print("[!] python-dotenv not installed, using environment variables only")

def send_discord_notification(message, title="Shiny Hunter - Test", color=0x00ff00):
    """Send Discord webhook notification"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("[!] ERROR: DISCORD_WEBHOOK_URL not set!")
        print("[!] Make sure you have:")
        print("    1. Created a .env file with DISCORD_WEBHOOK_URL=...")
        print("    2. Or set the environment variable: export DISCORD_WEBHOOK_URL=...")
        return False
    
    print(f"[+] Webhook URL found: {webhook_url[:50]}...")
    
    try:
        # Create embed payload
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        payload = {
            "embeds": [embed]
        }
        
        # Convert to JSON
        data = json.dumps(payload).encode('utf-8')
        
        # Create request with User-Agent header (some services require it)
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'ShinyHunter/1.0'
            }
        )
        
        print("[+] Sending test message to Discord...")
        
        # Send request
        with urllib.request.urlopen(req, timeout=10) as response:
            response_data = response.read()
            status_code = response.getcode()
            
            if status_code == 204:
                print("[+] ✓ SUCCESS! Test message sent to Discord!")
                print("[+] Check your Discord channel to see the test message.")
                return True
            else:
                print(f"[!] Unexpected status code: {status_code}")
                print(f"[!] Response: {response_data}")
                return False
                
    except urllib.error.HTTPError as e:
        print(f"[!] HTTP Error: {e.code} - {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"[!] Error details: {error_body}")
        except:
            pass
        return False
    except urllib.error.URLError as e:
        print(f"[!] URL Error: {e}")
        print("[!] Check your internet connection and webhook URL")
        return False
    except Exception as e:
        print(f"[!] Failed to send Discord notification: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Discord Webhook Test")
    print("=" * 60)
    print()
    
    # Send a test message
    test_message = (
        "🧪 **Test Message** 🧪\n\n"
        "This is a test notification from the Shiny Hunter script.\n"
        "If you see this message, your Discord webhook is working correctly!\n\n"
        "**Test Details:**\n"
        f"- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "- Status: Webhook connection successful ✓"
    )
    
    success = send_discord_notification(
        test_message,
        title="🧪 Webhook Test - Shiny Hunter",
        color=0x0099ff  # Blue color for test messages
    )
    
    print()
    if success:
        print("=" * 60)
        print("✓ Test completed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("✗ Test failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(1)

