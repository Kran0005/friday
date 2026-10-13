from __future__ import print_function
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import datetime
from .paths import PRIVATE_DIR, ensure_data_dirs

# --- If modifying SCOPES, delete token.json ---
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def main():
    creds = None
    # Use your actual credentials file name here
    ensure_data_dirs()
    credentials_path = PRIVATE_DIR / 'calendar_credentials.json'
    token_path = PRIVATE_DIR / 'token.json'

    # Check if token.json exists (saved after first login)
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no valid credentials are found, run login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the token for next time
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    # Now call Google Calendar API
    service = build('calendar', 'v3', credentials=creds)

    # Get next 10 events
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' = UTC
    print('🗓️  Getting the upcoming 10 events...')
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print("No upcoming events found.")
        return

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f"- {start} — {event['summary']}")

if __name__ == '__main__':
    main()
