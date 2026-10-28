# WhatsApp → Obsidian

Keeps WhatsApp chats in an Obsidian vault automatically. No exporting, no copy-paste.

Every 15 minutes it reads the WhatsApp for Mac app's local database (read-only) and writes:

```
<vault>/WhatsApp/
  Chats/<Chat name>/<Chat name> 2026-10.md   one note per chat per month, a heading per day
  Daily/2026-10-09.md                        optional: Claude's summary of the day + follow-up tasks
```

Chat notes are rebuilt from WhatsApp, so **don't edit them**: write your own notes elsewhere and
link to them (`[[Lucía Pérez 2026-10#2026-10-09 (Friday)]]`).

## Requirements

- A Mac with **WhatsApp for Mac** (App Store version) installed, linked to the phone and kept running
  or opened regularly. It only holds what it has synced from the phone. Older history may need one
  manual export.
- Python 3.10+ (`python3 --version`).
- Voice-note transcription needs an Apple Silicon Mac (M1 or later).

## Install

```bash
./install.sh                      # first run creates config.json
```

Edit `config.json`: set `"vault"` to the vault folder and `"me"` to the name to show for your own
messages. Then:

```bash
./install.sh                      # plain sync, nothing leaves the Mac
./install.sh --voice              # + transcribe voice notes locally
./install.sh --summaries          # + daily summaries (see Privacy)
```

The installer opens **Full Disk Access** in System Settings and prints the exact Python path to add.
The background job can't read WhatsApp's data without it. Check it with:

```bash
launchctl kickstart -k gui/$(id -u)/local.whatsapp-vault-sync; sleep 5; tail logs/sync.log
```

To bring in older messages once: `.venv/bin/python wa_sync.py --since 2026-01-01`.

## Config

| key | meaning |
|---|---|
| `include_chats` / `exclude_chats` | chat names or JIDs. Empty include = all chats. `--list-chats` prints names |
| `groups`, `include_archived` | include group chats and archived chats |
| `voice_notes.transcribe` | transcribe voice notes with Whisper on this Mac (needs `--voice`) |
| `summaries.enabled` | write a daily note per finished day (needs `--summaries` + API key) |
| `summaries.exclude_chats` | chats synced but never sent for summarising |
| `summaries.max_input_chars` | daily size cap. The largest chats are left out, and named in the note |

Daily summaries start from the day before they're switched on. For an earlier day:
`.venv/bin/python wa_sync.py --summarize 2026-10-01`.

## API key (summaries only)

The key is kept in the macOS Keychain, not in a file:

```bash
security add-generic-password -s whatsapp-vault-sync -a anthropic -w
```

Paste the key when prompted. A day costs roughly a few cents to $0.40 depending on volume
(Claude Opus 5.5, capped by `max_input_chars`). Set `"model": "claude-sonnet-5-5"` to spend less.

## Privacy

- Chats are read in place, read-only. The sync is local and makes no network calls.
- Chats WhatsApp marks as hidden, status updates and broadcasts are never written.
- With **summaries on**, each finished day's message text (including what other people wrote) is
  sent to the Anthropic API. Leave it off, or list sensitive chats in `summaries.exclude_chats`.
- Voice transcription runs on the Mac. The Whisper model is downloaded once from Hugging Face.

## Limits

- Uses WhatsApp's private desktop database, not an official API. A WhatsApp update can change it.
  If the sync fails after an update, `--doctor` and `logs/sync.log` show where.
- Polls, reactions and some newer message types are not shown. Calls and group events are left out on purpose.
- Photos, videos and documents appear as a line (file name, caption). The files themselves aren't copied.
- A message that arrives after its day was summarised appears in the chat note but not in that daily note.

## Uninstall

`./uninstall.sh` stops the schedule. Notes in the vault are kept.

## Tests

```bash
python3 tests/test_sync.py                 # synthetic database, no real chats
.venv/bin/python tests/test_summary.py     # summary path, mocked API (needs --summaries)
```
