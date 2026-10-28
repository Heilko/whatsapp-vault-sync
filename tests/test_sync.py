"""End-to-end test against a synthetic WhatsApp database. No real chats, no network.

    python3 tests/test_sync.py
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "wa_sync.py"
EPOCH = 978307200


def apple(dt):
    return dt.timestamp() - EPOCH


def make_db(path):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")  # like the real app
    con.executescript("""
    CREATE TABLE ZWACHATSESSION (Z_PK INTEGER PRIMARY KEY, ZCONTACTJID TEXT, ZPARTNERNAME TEXT,
        ZSESSIONTYPE INTEGER, ZARCHIVED INTEGER, ZREMOVED INTEGER, ZHIDDEN INTEGER);
    CREATE TABLE ZWAGROUPMEMBER (Z_PK INTEGER PRIMARY KEY, ZCONTACTNAME TEXT, ZFIRSTNAME TEXT, ZMEMBERJID TEXT);
    CREATE TABLE ZWAMEDIAITEM (Z_PK INTEGER PRIMARY KEY, ZMEDIALOCALPATH TEXT, ZTITLE TEXT, ZMOVIEDURATION INTEGER,
        ZVCARDNAME TEXT, ZLATITUDE REAL, ZLONGITUDE REAL);
    CREATE TABLE ZWAMESSAGE (Z_PK INTEGER PRIMARY KEY, ZCHATSESSION INTEGER, ZISFROMME INTEGER, ZMESSAGEDATE REAL,
        ZMESSAGETYPE INTEGER, ZTEXT TEXT, ZPUSHNAME TEXT, ZFROMJID TEXT, ZGROUPMEMBER INTEGER, ZMEDIAITEM INTEGER);
    INSERT INTO ZWACHATSESSION VALUES
        (1, '34600000001@s.whatsapp.net', 'Lucía Pérez', 0, 0, 0, 0),
        (2, '120363000@g.us', 'Proyecto / Obra: Fase 2', 1, 0, 0, 0),
        (3, '34600000003@s.whatsapp.net', 'Lucía Pérez', 0, 1, 0, 0),
        (4, '34600000004@s.whatsapp.net', 'Secret', 0, 0, 0, 1),
        (5, 'status@broadcast', 'Status', 2, 0, 0, 0);
    INSERT INTO ZWAGROUPMEMBER VALUES (1, 'Marco', 'Marco', '111@lid');
    INSERT INTO ZWAMEDIAITEM VALUES
        (1, 'Media/voice.opus', NULL, 75, NULL, NULL, NULL),
        (2, 'Media/plan.pdf', 'plano-final.pdf', 0, NULL, NULL, NULL),
        (3, NULL, NULL, 0, NULL, 40.4168, -3.7038);
    """)
    now = datetime.now().replace(second=0, microsecond=0)
    y = (now - timedelta(days=1)).replace(minute=0)
    rows = [
        # pk, chat, me, date, type, text, push, from, member, media
        (1, 1, 0, apple(y.replace(hour=9)), 0, "¿Quedamos el jueves a las 10?\nTraigo el contrato.", "Lu", None, None, None),
        (2, 1, 1, apple(y.replace(hour=9, minute=5)), 0, "Perfecto, jueves 10:00", None, None, None, None),
        (3, 1, 0, apple(y.replace(hour=9, minute=6)), 3, None, "Lu", None, None, 1),
        (4, 2, 0, apple(y.replace(hour=11)), 8, None, "Marco", "120363000@g.us", 1, 2),
        (5, 2, 0, apple(y.replace(hour=11, minute=1)), 5, None, "Marco", "120363000@g.us", 1, 3),
        (6, 2, 0, apple(y.replace(hour=11, minute=2)), 6, "Marco added you", None, None, None, None),
        (7, 2, 0, apple(y.replace(hour=11, minute=3)), 0, "Sin miembro", "Ana B", "999@lid", None, None),
        (8, 3, 0, apple(y.replace(hour=12)), 0, "otra Lucía", None, None, None, None),
        (9, 4, 0, apple(y.replace(hour=12)), 0, "HIDDEN-SHOULD-NOT-APPEAR", None, None, None, None),
        (10, 5, 0, apple(y.replace(hour=12)), 0, "STATUS-SHOULD-NOT-APPEAR", None, None, None, None),
    ]
    con.executemany("INSERT INTO ZWAMESSAGE VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return con, now


def run(env, *args):
    r = subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wa, home, vault = tmp / "wa", tmp / "home", tmp / "vault"
        for d in (wa, home, vault):
            d.mkdir()
        db, now = make_db(wa / "ChatStorage.sqlite")  # kept open: messages stay in the WAL, as in real use
        (home / "config.json").write_text(json.dumps({"vault": str(vault), "me": "Yo"}))
        env = {**os.environ, "WA_SYNC_HOME": str(home), "WA_SYNC_WA_DIR": str(wa)}

        y = now - timedelta(days=1)
        print(run(env, "--dry-run", "--since", f"{y:%Y-%m-%d}").strip())
        print(run(env, "--since", f"{y:%Y-%m-%d}").strip())

        notes = sorted(p.relative_to(vault) for p in vault.rglob("*.md"))
        print("\n".join(map(str, notes)))
        all_text = "".join(p.read_text() for p in vault.rglob("*.md"))
        assert "HIDDEN-SHOULD-NOT-APPEAR" not in all_text and "STATUS-SHOULD-NOT-APPEAR" not in all_text
        assert "Marco added you" not in all_text, "system events must be skipped"
        names = {p.parts[2] for p in notes}
        assert names == {"Lucía Pérez", "Lucía Pérez (2)", "Proyecto Obra Fase 2"}, names

        lucia = (vault / "WhatsApp/Chats/Lucía Pérez" / f"Lucía Pérez {y:%Y-%m}.md").read_text()
        print("-" * 40 + "\n" + lucia)
        assert "**Yo:** Perfecto" in lucia and "\n  Traigo el contrato." in lucia
        assert "🎤 voice note (1:15)" in lucia
        group = next(vault.rglob("Proyecto*")).glob("*.md").__next__().read_text()
        assert "**Marco:** 📄 plano-final.pdf" in group and "maps.apple.com/?ll=40.416800,-3.703800" in group
        assert "**Ana B:** Sin miembro" in group, "falls back to push name"

        # Incremental: a new message only re-renders its chat; an unchanged run writes nothing.
        out = run(env)
        assert out.startswith("0 note(s) updated from 0 month(s)"), out
        db.execute("INSERT INTO ZWAMESSAGE VALUES (11, 1, 1, ?, 0, 'Nuevo mensaje', NULL, NULL, NULL, NULL)",
                   (apple(now),))
        db.commit()
        out = run(env)
        assert out.startswith("1 note(s) updated from 1 month(s)"), out
        assert "Nuevo mensaje" in (vault / "WhatsApp/Chats/Lucía Pérez" / f"Lucía Pérez {now:%Y-%m}.md").read_text()

        # Renaming a chat keeps its folder.
        db.execute("UPDATE ZWACHATSESSION SET ZPARTNERNAME='Lucía (trabajo)' WHERE Z_PK=1")
        db.execute("INSERT INTO ZWAMESSAGE VALUES (12, 1, 0, ?, 0, 'tras renombrar', 'Lu', NULL, NULL, NULL)",
                   (apple(now) + 1,))
        db.commit()
        run(env)
        assert not (vault / "WhatsApp/Chats/Lucía (trabajo)").exists()
        db.close()
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
