# Meeting Response Tool

Send a fixed reminder email to whitelisted addresses, one at a time or in bulk from a JSON file.

---

## Usage

### Single send

```
python main.py "Event Name and Date" "target@email.com"
```

| Argument | Description |
|---|---|
| `"Event Name and Date"` | Free text describing the meeting — appears in the subject and body |
| `"target@email.com"` | Recipient address — must be in `email.txt` |

### Batch send

```
python main.py /path/to/batch.json
```

The JSON file maps event names to one or more recipient addresses:

```json
{
  "Team Sync – 14 May 2026": ["alice@example.com", "bob@example.com"],
  "1:1 with Zhijing – 15 May 2026": "zhijing@example.com"
}
```

- Values can be a single string or a list of strings.
- All addresses are validated against `email.txt` **before** anything is sent. If any address is not whitelisted, the script aborts and lists every bad address.
- After showing the full send plan, the script asks for `y` confirmation.
- Each email after the first is delayed by a **random 30–90 second pause** to avoid triggering spam filters.

---

## Setup

### Credentials (.env)

```bash
cp .env.example .env
# edit .env with your Gmail address and App Password
```

| Variable | Description |
|---|---|
| `GMAIL_USER` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | 16-character Gmail App Password (not your login password) |
| `SENDER_NAME` | Display name in the From field (optional) |

Generate an App Password at <https://myaccount.google.com/apppasswords> (requires 2FA enabled).

### Whitelist (email.txt)

One approved address per line. Lines starting with `#` are ignored.

```
alice@example.com
zhijing@example.com
```

The script refuses to send to any address not on this list.

---

## Error reference

| Message | Fix |
|---|---|
| Address not in approved whitelist | Add it to `email.txt` |
| `Whitelist file not found` | Create `email.txt` |
| `GMAIL_USER and GMAIL_APP_PASSWORD must be set` | Copy `.env.example` → `.env` and fill in credentials |
| `Invalid JSON` | Check your batch file for syntax errors |
| SMTP authentication error | Regenerate the App Password; confirm 2FA is on |

---

## File layout

```
send-note/
├── main.py          # main script
├── email.txt        # approved recipient whitelist
├── .env             # your private credentials (do not commit)
├── .env.example     # credential template — safe to commit
└── SKILL.md         # this file
```
