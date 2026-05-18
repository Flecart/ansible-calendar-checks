# Calendar Automation

Ansible playbook that provisions the **overleaf** server with:

- A dedicated `calendar` Linux user
- [`google-calendar-mcp`](https://github.com/nspady/google-calendar-mcp) — Google Calendar MCP server (Node.js)
- [`nanobot`](https://github.com/HKUDS/nanobot) — lightweight AI agent (Python)
- Local skills copied to `~/.nanobot/workspace/skills`

## Prerequisites

| Requirement | Detail |
|---|---|
| Ansible ≥ 2.14 | `pip install ansible` |
| SSH access | `~/.ssh/overleaf.pem` key available |
| GCP credentials | `~/google-calendar-mcp/credentials.json` on this machine |
| API key | Copy `secrets.yml.example` → `secrets.yml` and set `nanobot_api_key` (or run `make setup-secrets` then edit) |

The credentials file must exist locally before running the playbook — Ansible copies it to the remote at `/home/calendar/gcp-oauth.keys.json` and wires `GOOGLE_OAUTH_CREDENTIALS` into the `calendar` user's `.bashrc`.

## Running

```bash
# Verify connectivity
make ping

# Dry-run (no changes applied)
make check

# Full deploy
make deploy
```

Targeting a different host:

```bash
make deploy HOST=someother
```

## What the playbook does

1. **base** — installs `git`, `python3-pip`, `nodejs` (LTS via NodeSource)
2. **calendar_user** — creates the `calendar` system user with a home directory
3. **google_calendar_mcp**
   - Clones the repo to `/home/calendar/google-calendar-mcp`
   - Runs `npm install && npm run build`
   - Copies `~/google-calendar-mcp/credentials.json` → `/home/calendar/gcp-oauth.keys.json` (mode 600)
   - Adds `export GOOGLE_OAUTH_CREDENTIALS=...` to `/home/calendar/.bashrc`
4. **nanobot**
   - Clones `https://github.com/HKUDS/nanobot.git` to `/home/calendar/nanobot`
   - Runs `pip install -e .` as the `calendar` user
   - Copies local `skills/` → `/home/calendar/.nanobot/workspace/skills/`

## Post-deploy: first-time Google auth

SSH into the machine as the `calendar` user and run the OAuth flow once:

```bash
ssh overleaf
sudo -u calendar -i
cd ~/google-calendar-mcp
node dist/index.js   # follow the printed OAuth URL in a browser
```

After completing the browser flow the token is stored automatically and subsequent runs are non-interactive.

## Adding skills

Drop a new skill directory under `skills/` locally, then re-run `make deploy`.
The playbook copies the whole `skills/` tree idempotently.

## Inventory

Target host is defined in `inventory/hosts.yml`.
Host-specific paths live in `host_vars/overleaf.yml`.
