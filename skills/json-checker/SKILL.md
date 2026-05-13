# json-checker

Validates a batch-send JSON file before passing it to `send-note`. Outputs structured JSON — exit code and output are both designed to be consumed by LLM agents.

## Usage

```
python main.py /path/to/batch.json
```

## Expected input format

```json
{
  "Event Name and Date": ["email1@example.com", "email2@example.com"],
  "Another Event":        "single@example.com"
}
```

- Top-level must be an object.
- Each key is a non-empty event name string.
- Each value is either a single email string or a list of email strings.

## Output schema

```json
{
  "valid":    true | false,
  "summary":  "Human-readable one-liner.",
  "errors":   ["..."],
  "warnings": ["..."],
  "stats":    { "events": 2, "recipients": 3 }
}
```

- `errors` — structural or type problems that must be fixed before sending.
- `warnings` — values that look suspicious (e.g. malformed email address) but are not blocking.
- `stats` — only present when `valid` is `true`.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | File is valid — safe to pass to `send-note` |
| `1`  | Invalid — do not send |

## LLM agent usage pattern

Run this tool first, parse the JSON output, and act on `valid` + `errors`/`warnings` before invoking `send-note`. Example flow:

```
1. python json-checker/main.py batch.json   → check output["valid"]
2. If false: show output["errors"] to user, stop.
3. If true but warnings exist: surface output["warnings"], ask user to confirm.
4. If valid: python send-note/main.py batch.json
```
