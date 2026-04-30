"""
Smoke test — verifies auth and sends a test email to the configured sender address.

Prereqs:
  pip install msal requests python-dotenv
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.integrations.outlook.core import OutlookAuthConfig, OutlookGraphClient


def main() -> None:
    client_id = os.environ.get("OUTLOOK_CLIENT_ID")
    if not client_id:
        raise SystemExit("OUTLOOK_CLIENT_ID is not set in .env")

    sender = os.environ.get("OUTLOOK_SENDER_EMAIL")
    if not sender:
        raise SystemExit("OUTLOOK_SENDER_EMAIL is not set in .env")

    auth = OutlookAuthConfig(
        client_id=client_id,
        authority=os.environ.get("OUTLOOK_AUTHORITY", "https://login.microsoftonline.com/common"),
        scopes=(os.environ.get("OUTLOOK_SCOPES") or "Mail.Read Mail.Send User.Read").split(),
        sender_email=sender,
    )
    core = OutlookGraphClient(auth)

    print("\n--- Step 1: Authenticate ---")
    token = core.acquire_token()
    print(f"Token acquired: {token[:20]}...")

    print("\n--- Step 2: Check authenticated account ---")
    me = core._request("GET", "/me", params={"$select": "displayName,mail,userPrincipalName"})
    actual_email = me.get("mail") or me.get("userPrincipalName")
    print(f"  Authenticated as : {me.get('displayName')} <{actual_email}>")
    print(f"  OUTLOOK_SENDER_EMAIL: {sender}")
    if actual_email and actual_email.lower() != sender.lower():
        print("  WARNING: sender_email does not match authenticated account — using authenticated account as recipient")
        recipient = actual_email
    else:
        recipient = sender

    print("\n--- Step 3: Read last 3 emails ---")
    result = core.outlook_get_emails(page_size=3)
    emails = result.get("emails", result) if isinstance(result, dict) else result
    for e in emails:
        from_addr = ((e.get("from") or {}).get("emailAddress") or {}).get("address", "?")
        print("  - {} | {} | {}".format(e.get('receivedDateTime'), from_addr, e.get('subject', '')).encode('ascii', errors='replace').decode())

    print("\n--- Step 4: Send test email ---")
    core.outlook_send_email(
        to=[recipient],
        subject="MCP Outlook Integration — Test Email",
        body=(
            "This is an automated test email sent from the Outlook MCP integration.\n\n"
            f"Authenticated account: {actual_email}\n"
            f"Sender configured: {sender}\n"
            "If you received this, sending works correctly!"
        ),
    )
    print(f"Test email sent to {recipient} — check your inbox!")


if __name__ == "__main__":
    main()
