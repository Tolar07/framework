"""Tennis backtest: xlsx reader, parser (no winner leak), Elo replay, no-peeking split, report. No network."""
from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402


def _xlsx(rows):
    heads = list(rows[0])
    strings = []

    def s(v):
        if v not in strings:
            strings.append(v)
        return strings.index(v)

    def cell(ci, ri, v):
        ref = chr(65 + ci) + str(ri)
        if isinstance(v, str):
            return f'<c r="{ref}" t="s"><v>{s(v)}</v></c>'
        return f'<c r="{ref}"><v>{v}</v></c>'

    body = "".join(f'<row r="{i + 1}">' + "".join(cell(ci, i + 1, r[h]) for ci, h in enumerate(heads) if h in r)
                   + "</row>" for i, r in enumerate([{h: h for h in heads}] + rows))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    sheet = f'<worksheet {ns}><sheetData>{body}</sheetData></worksheet>'
    sst = f'<sst {ns}>' + "".join(f"<si><t>{x}</t></si>" for x in strings) + "</sst>"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)
    return buf.getvalue()


def _row(d, w, lo, pw=1.5, pl=2.6, comment="Completed"):
    return {"Date": d, "Winner": w, "Loser": lo, "Surface": "Hard", "PSW": pw, "PSL": pl, "AvgW": pw, "AvgL": pl,
            "Comment": comment}


def test_read_and_parse_skips_bad_rows():
    blob = _xlsx([_row(44000, "Zed", "Abe"), _row(44001, "Abe", "Zed", comment="Retired"),
                  _row(44002, "Abe", "Zed", pw=0.5), _row(44003, "Cy", "Abe")])
    g = tb.parse(tb.read_xlsx(blob), "ATP")
    assert len(g) == 2
    assert g[0]["a"] == "Abe" and g[0]["b"] == "Zed" and g[0]["y"] == 0.0     # sides by name, winner Zed is side b
    assert g[1]["a"] == "Abe" and g[1]["b"] == "Cy" and g[1]["y"] == 0.0        # Cy won, Cy is side b


def test_devig_sums_to_one():
    assert abs(tb.devig(1.5, 2.6) + tb.devig(2.6, 1.5) - 1) < 1e-12


def _games(n=900):
    names = ["A", "B", "C", "D", "E"]
    out = []
    for i in range(n):
        a, b = names[i % 5], names[(i + 1 + i // 5 % 3) % 5]
        if a == b:
            b = names[(i + 2) % 5]
        y = 1.0 if a < b else 0.0
        out.append({"day": f"{2019 + i // 130}-01-{1 + i % 28:02d}", "tour": "ATP", "surface": "Hard", "a": a, "b": b,
                    "y": y, "pa": 1.9, "pb": 1.9, "qa": 1.9, "qb": 1.9, "year": 2019 + i // 130, "mkt": 0.5})
    return out


def test_replay_no_lookahead_and_min_games():
    g = _games()
    p1 = tb.replay(g, 32.0, 0.5)
    assert p1[0] is None and any(p is not None for p in p1)
    g2 = [dict(x) for x in g]
    g2[-1]["y"] = 1.0 - g2[-1]["y"]
    assert tb.replay(g2, 32.0, 0.5)[:-1] == p1[:-1]


def test_run_reports_heldout():
    text = tb.run(_games())
    assert "reported on **2023-2025 only**" in text and "Record only" in text
