# lawsuit-parser_TgBot

Telegram bot that watches Russian companies by INN, periodically checks them through the parser API, and notifies subscribed users in Russian about any changes.

Runs as a separate process next to the parser API. Communicates only over HTTP.

## What it does

- Whitelist-based access: only users approved by the admin can use the bot
- Users subscribe to INNs with `/watch`
- Per-user schedule: daily, weekly, or monthly
- The bot checks subscribed INNs on schedule via the parser API
- On change, sends a Russian-language diff message
- On no change, stays silent
- Manual check via `/check <INN>` works on demand

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/yourusername/company-info-bot.git
cd company-info-bot

python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Configure:

```bash
cp .env.example .env
```

Edit `.env`:

- `BOT_TOKEN` — from @BotFather
- `ADMIN_TELEGRAM_ID` — your Telegram user ID (get it from @userinfobot)
- `PARSER_API_URL` — where the parser API runs (e.g. `http://127.0.0.1:8000`)
- `PARSER_API_KEY` — if the parser API requires one

## Run

Make sure the parser API is running first.

```bash
python -m src.main
```

The bot initializes its SQLite database, verifies parser API reachability, starts the scheduler, and begins polling for updates.

To stop: `Ctrl+C`.

## Commands

| Command | Purpose |
|---------|---------|
| `/start` | Register and show the menu |
| `/watch <ИНН> [название]` | Subscribe to changes for an INN |
| `/unwatch <ИНН>` | Remove a subscription |
| `/list` | Show all subscriptions |
| `/check <ИНН>` | Trigger a manual check and receive a diff message |
| `/schedule` | Change the frequency (daily / weekly / monthly) |
| `/help` | Show help |

## Whitelist management

The admin (`ADMIN_TELEGRAM_ID`) is automatically allowed.

To allow others, use the bot's database directly:

```bash
sqlite3 bot_data.db "UPDATE users SET is_allowed = 1 WHERE telegram_id = <ID>;"
```

Or add an admin-only command in the handlers if you prefer.

## Architecture

```
┌────────────────────┐          HTTP          ┌────────────────────┐
│  Telegram Bot      │ ─────────────────────► │  Parser API        │
│  (this repo)       │                        │  (separate repo)   │
│                    │                        │                    │
│  - aiogram         │                        │  - FastAPI         │
│  - APScheduler     │                        │  - parsers         │
│  - SQLite/Postgres │                        │  - PostgreSQL      │
└────────────────────┘                        └────────────────────┘
```

Both run as parallel processes on the same server. The bot never touches the parser's database.

## Database

By default uses SQLite at `./bot_data.db`. To use PostgreSQL:

```env
BOT_DB_URL=postgresql://user:password@localhost:5432/bot_db
```

Tables are created automatically on startup.

## License

MIT