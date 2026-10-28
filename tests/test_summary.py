"""Daily-summary path with the real Anthropic SDK and a mocked HTTP endpoint. No network, no spend.

    .venv/bin/python tests/test_summary.py      (needs: ./install.sh --summaries)
"""

import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import anthropic
try:
    import httpx2 as httpx  # anthropic 1.x
except ImportError:
    import httpx

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]
from test_sync import make_db  # noqa: E402

captured = {}


def fake_api(request):
    captured["headers"] = dict(request.headers)
    captured["body"] = json.loads(request.content)
    return httpx.Response(200, json={
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "## Summary\n- **Lucía Pérez**: jueves 10:00, trae el contrato.\n\n"
                                             "## Follow-ups\n- [ ] Lucía: traer el contrato (jueves)"}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 40},
    })


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wa, home, vault = tmp / "wa", tmp / "home", tmp / "vault"
        for d in (wa, home, vault):
            d.mkdir()
        db, now = make_db(wa / "ChatStorage.sqlite")
        (home / "config.json").write_text(json.dumps({"vault": str(vault), "me": "Yo",
                                                      "summaries": {"enabled": True}}))
        os.environ.update(WA_SYNC_HOME=str(home), WA_SYNC_WA_DIR=str(wa))
        import wa_sync

        real = anthropic.Anthropic
        anthropic.Anthropic = lambda **kw: real(api_key="test", http_client=httpx.Client(
            transport=httpx.MockTransport(fake_api)))
        wa_sync.api_key = lambda: None

        cfg = wa_sync.load_config()
        con = wa_sync.open_db()
        state = wa_sync.new_state(date.today())
        day = date.today() - timedelta(days=1)
        assert wa_sync.summarize_day(con, wa_sync.load_chats(con, cfg), day, state, cfg, {})

        body, headers = captured["body"], captured["headers"]
        assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
        assert body["output_config"] == {"effort": "medium"}
        assert "server-side-fallback-2026-07-01" in headers["anthropic-beta"]
        prompt = body["messages"][0]["content"]
        assert "Traigo el contrato" in prompt and "HIDDEN-SHOULD-NOT-APPEAR" not in prompt
        note = (vault / "WhatsApp/Daily" / f"{day:%Y-%m-%d}.md").read_text()
        print(note)
        assert "- [ ] Lucía: traer el contrato" in note
        assert f"[[Lucía Pérez {day:%Y-%m}#{day:%Y-%m-%d} ({day:%A})|Lucía Pérez]]" in note
        db.close()
        print("SUMMARY TEST PASSED")


if __name__ == "__main__":
    main()
