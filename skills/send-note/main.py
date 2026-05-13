#!/usr/bin/env python3
"""Send a non-interactive reminder so the recipient can pick a meeting response."""

import json
import os
import random
import sys
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


# ── env loader ───────────────────────────────────────────────────────────────

def _load_env(path: Path) -> None:
    """Minimal .env loader — no external deps required."""
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)
    except FileNotFoundError:
        pass


_HERE = Path(__file__).parent
_load_env(_HERE / '.env')

GMAIL_USER         = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
SENDER_NAME        = os.environ.get('SENDER_NAME', '')

WHITELIST_PATH = _HERE / 'email.txt'

REMINDER_SUBJECT = 'Reminder: please respond — {event}'

REMINDER_BODY = (
    "Hi,\n\n"
    "This is a quick reminder about the following invitation:\n"
    "  {event}\n\n"
    "The bot (me 🤖) noticed that you haven't responded yet. If you are ready, please choose how you would like to respond:\n\n"
    "  1. Accept — you plan to attend.\n"
    "  2. Decline — you cannot attend this time.\n"
    "  3. Note to Zhijing — you prefer not to be included for this type of meeting "
    "(including going forward).\n\n"
    "Reply to this message (or follow up as you usually do) with 1, 2, or 3 so we know if you will attend.\n"
    "As always, have a nice day :D\n\n"
    "Thank you,\n{sender}\n"
)


# ── helpers ───────────────────────────────────────────────────────────────────

def load_whitelist() -> set:
    if not WHITELIST_PATH.exists():
        _die(f"Whitelist file not found: {WHITELIST_PATH}\nCreate it and add one approved email per line.")
    emails = set()
    for line in WHITELIST_PATH.read_text().splitlines():
        line = line.strip().lower()
        if line and not line.startswith('#'):
            emails.add(line)
    return emails


def send_email(to: str, subject: str, body: str) -> None:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        _die(
            "GMAIL_USER and GMAIL_APP_PASSWORD must be set.\n"
            f"Copy {_HERE / '.env.example'} to {_HERE / '.env'} and fill in your credentials."
        )
    from_field = f"{SENDER_NAME} <{GMAIL_USER}>" if SENDER_NAME else GMAIL_USER
    msg = MIMEMultipart()
    msg['From']    = from_field
    msg['To']      = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo()
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())


def _die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


# ── batch helpers ─────────────────────────────────────────────────────────────

def _parse_batch(json_path: str) -> list[tuple[str, str]]:
    """Return a flat list of (event, email) pairs from the JSON file."""
    path = Path(json_path)
    if not path.exists():
        _die(f"JSON file not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        _die(f"Invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        _die("JSON must be an object: {\"event\": [\"email\"] | \"email\", ...}")

    pairs: list[tuple[str, str]] = []
    for event, recipients in data.items():
        if isinstance(recipients, str):
            recipients = [recipients]
        if not isinstance(recipients, list):
            _die(f"Recipients for '{event}' must be a string or list of strings.")
        for addr in recipients:
            pairs.append((event.strip(), addr.strip().lower()))
    return pairs


def _send_batch(pairs: list[tuple[str, str]], whitelist: set) -> None:
    bad = [addr for _, addr in pairs if addr not in whitelist]
    if bad:
        _die(
            "The following addresses are not in the approved whitelist:\n"
            + "\n".join(f"  {a}" for a in sorted(set(bad)))
            + f"\nAdd them to {WHITELIST_PATH} to allow sending."
        )

    sender = SENDER_NAME or GMAIL_USER
    total  = len(pairs)
    print(f"\nBatch: {total} email(s) to send.")
    for event, addr in pairs:
        print(f"  {event!r:40s} → {addr}")
    print()
    confirm = input(f"Send all {total} email(s) with 30–90 s delays? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Aborted — nothing sent.")
        sys.exit(0)

    print()
    for i, (event, addr) in enumerate(pairs, 1):
        subject = REMINDER_SUBJECT.format(event=event)
        body    = REMINDER_BODY.format(event=event, sender=sender)
        send_email(addr, subject, body)
        print(f"[{i}/{total}] Sent to {addr} for: {event}")

        if i < total:
            delay = random.randint(30, 90)
            print(f"      Waiting {delay}s before next send…")
            time.sleep(delay)

    print(f"\nDone — {total} email(s) sent.")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if len(args) == 1 and args[0].endswith('.json'):
        # Batch mode: python main.py batch.json
        whitelist = load_whitelist()
        pairs = _parse_batch(args[0])
        _send_batch(pairs, whitelist)

    elif len(args) == 2:
        # Single mode: python main.py "Event" "email"
        event  = args[0].strip()
        target = args[1].strip().lower()

        whitelist = load_whitelist()
        if target not in whitelist:
            _die(
                f"'{target}' is not in the approved email whitelist.\n"
                f"Add it to {WHITELIST_PATH} to allow sending."
            )

        sender  = SENDER_NAME or GMAIL_USER
        subject = REMINDER_SUBJECT.format(event=event)
        body    = REMINDER_BODY.format(event=event, sender=sender)

        send_email(target, subject, body)
        print(f"Reminder sent to {target} for: {event}")

    else:
        print('Usage:')
        print('  Single : python main.py "Event Name and Date" "target@email.com"')
        print('  Batch  : python main.py /path/to/batch.json')
        sys.exit(1)


if __name__ == '__main__':
    main()
