#!/usr/bin/env python3
"""Check Google Calendar for pending RSVPs and send reminder emails."""

import argparse
import os
import random
import smtplib
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import textwrap

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── config ────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent


def _load_env(path: Path) -> None:
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_env(_HERE / '.env')

GMAIL_USER         = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
SENDER_NAME        = os.environ.get('SENDER_NAME', '')
LOOKAHEAD_DAYS     = int(os.environ.get('LOOKAHEAD_DAYS', '7'))
CREDENTIALS_PATH   = Path(os.environ.get('GOOGLE_CREDENTIALS_PATH', str(_HERE / 'credentials.json')))
TOKEN_PATH         = Path(os.environ.get('GOOGLE_TOKEN_PATH', str(_HERE / 'token.json')))
INCLUDE_TENTATIVE  = os.environ.get('INCLUDE_TENTATIVE', 'false').lower() == 'true'

EMAIL_WHITELIST_PATH  = _HERE / 'email.txt'
EVENTS_WHITELIST_PATH = _HERE / 'events.txt'

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

REMINDER_SUBJECT = 'Jinesis Lab Event Reminder: please respond'
REMINDER_BODY = textwrap.dedent("""
Hi,

This is a reminder to RSVP to the upcoming lab event on Google Calendar, so we can keep track of attendance, as per our lab policy.

You can respond directly via the event link below:
<a href="{event_link}">{event_name}</a>

Please select whether you'll be attending at your earliest convenience using the default option. Thank you!

Best,
Jinesis Bot
    """).replace('\n', '<br>')

# ── Google Calendar ───────────────────────────────────────────────────────────

def get_calendar_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                _die(
                    f"Credentials file not found: {CREDENTIALS_PATH}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build('calendar', 'v3', credentials=creds)


def find_pending(
    service, email_whitelist: set, event_patterns: list[str], lookahead: int
) -> list[tuple[str, str, list[str]]]:
    """Return one row per event: (event_display_name, html_link, whitelisted attendee emails needing RSVP)."""
    now      = datetime.now(timezone.utc)
    time_max = now + timedelta(days=lookahead)

    result = service.events().list(
        calendarId='primary',
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy='startTime',
    ).execute()

    pending: dict[str, tuple[str, set[str]]] = {}

    for event in result.get('items', []):
        title = event.get('summary', '(no title)')

        if event_patterns and not any(p.lower() in title.lower() for p in event_patterns):
            continue

        attendees = event.get('attendees', [])
        if not attendees:
            continue

        start     = event.get('start', {})
        start_str = start.get('dateTime', start.get('date', ''))
        try:
            dt         = datetime.fromisoformat(start_str)
            date_label = dt.strftime('%Y-%m-%d %H:%M') if 'T' in start_str else start_str
        except ValueError:
            date_label = start_str

        display   = f"{title} ({date_label})"
        html_link = event.get('htmlLink', '')
        if not html_link:
            continue

        if html_link not in pending:
            pending[html_link] = (display, set())

        _, emails = pending[html_link]

        for attendee in attendees:
            if attendee.get('self'):
                continue
            status = attendee.get('responseStatus', 'needsAction')
            email  = attendee.get('email', '').lower()
            needs  = status == 'needsAction' or (INCLUDE_TENTATIVE and status == 'tentative')
            if needs and email in email_whitelist:
                emails.add(email)

    return [
        (display, link, sorted(emails))
        for link, (display, emails) in pending.items()
        if emails
    ]

# ── email ─────────────────────────────────────────────────────────────────────

def load_lines(path: Path, label: str) -> list[str]:
    if not path.exists():
        _die(f"{label} file not found: {path}")
    return [l.strip() for l in path.read_text().splitlines()
            if l.strip() and not l.strip().startswith('#')]


def send_email(to_addrs: list[str], subject: str, body: str) -> None:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        _die("GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env")
    if not to_addrs:
        return
    from_field = f"{SENDER_NAME} <{GMAIL_USER}>" if SENDER_NAME else GMAIL_USER
    msg            = MIMEMultipart()
    msg['From']    = from_field
    msg['To']      = ', '.join(to_addrs)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo()
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to_addrs, msg.as_string())

# ── helpers ───────────────────────────────────────────────────────────────────

def _die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)

# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description='Send calendar RSVP reminders.')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Print what would be sent without actually sending.')
    parser.add_argument('--days', type=int, default=LOOKAHEAD_DAYS,
                        help=f'Days ahead to check (default: {LOOKAHEAD_DAYS}).')
    args = parser.parse_args()

    dry_run   = args.dry_run
    lookahead = args.days

    email_whitelist = set(load_lines(EMAIL_WHITELIST_PATH, 'Email whitelist'))

    if EVENTS_WHITELIST_PATH.exists():
        event_patterns = load_lines(EVENTS_WHITELIST_PATH, 'Events whitelist')
    else:
        print(f"Warning: {EVENTS_WHITELIST_PATH} not found — checking all upcoming events.")
        event_patterns = []

    print(f"Checking Google Calendar (next {lookahead} day(s))…")
    service = get_calendar_service()
    sends   = find_pending(service, email_whitelist, event_patterns, lookahead)

    if not sends:
        print("No pending RSVPs found.")
        return

    n_recipients = sum(len(emails) for _, _, emails in sends)
    print(f"\nFound {len(sends)} event reminder(s) ({n_recipients} recipient(s)):")
    for display, _, emails in sends:
        who = ', '.join(emails)
        print(f"  {display!r:55s} → {who}")

    if dry_run:
        print("\nDry run — nothing sent.")
        return

    print()
    total = len(sends)
    for i, (display, html_link, emails) in enumerate(sends, 1):
        body = REMINDER_BODY.format(event_link=html_link, event_name=display)
        send_email(emails, REMINDER_SUBJECT, body)
        who = ', '.join(emails)
        print(f"[{i}/{total}] Sent to {who} for: {display}")
        if i < total:
            delay = random.randint(30, 90)
            print(f"      Waiting {delay}s…")
            time.sleep(delay)

    print(f"\nDone — {total} reminder(s) sent.")


if __name__ == '__main__':
    main()
