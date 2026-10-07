# TURKISH CUP STUDY

Written by `backtest/cup_study.py` from `data/cups/results.json` (Flashscore, archived by every daily run). Divisions are read from the same week's league results.

27 ties, 2026-10-06 to 2026-10-07 — TURKEY: Turkish Cup - Qualification.

## What happened

- Level after 90 minutes (extra time / penalties): 3/27 = 11% (95% range 4%–28%)
- Home side won in 90: 16/27 = 59% (95% range 41%–75%)
- Away side won in 90: 8/27 = 30% (95% range 16%–48%)
- Goals per 90 minutes (ties decided in 90): 3.38
- Over 1.5: 20/24 = 83% (95% range 64%–93%)
- Over 2.5: 13/24 = 54% (95% range 35%–72%)
- Both teams scored: 10/24 = 42% (95% range 24%–61%)
- Half-time leader won: 14/15 = 93% (95% range 70%–99%)

## Division gaps

Ties between different divisions (a club in no league table counted lowest): 11. Higher division won in 90: 5, lost: 4, level after 90: 2.

| Date | Home (division) | Score | Away (division) | |
|---|---|---|---|---|
| 2026-10-06 | Bitlis 1916 (3. Lig) | 6–0 | Silifke (3. Lig) |  |
| 2026-10-06 | Karsiyaka (3. Lig) | 3–1 | Afyonkarahisaspor (no league table (amateur?)) |  |
| 2026-10-06 | Kirklarelispor (2. Lig) | 1–0 (incl. ET) | Bayburtspor (no league table (amateur?)) | level after 90 |
| 2026-10-06 | Sakaryaspor (2. Lig) | 2–0 | Arit Kayadibi (no league table (amateur?)) |  |
| 2026-10-07 | Adanaspor AS (3. Lig) | 0–2 | Adana Adaletgucu (3. Lig) |  |
| 2026-10-07 | Bigaspor (3. Lig) | 0–3 | Balikesirspor (3. Lig) |  |
| 2026-10-07 | Bursa Yildirimspor (3. Lig) | 2–0 | Amasyaspor (3. Lig) |  |
| 2026-10-07 | Eskisehir Anadolu (3. Lig) | 4–2 | Kepez Bld. (3. Lig) |  |
| 2026-10-07 | Gaziemirspor (3. Lig) | 0–2 | Fethiyespor (2. Lig) |  |
| 2026-10-07 | Gemlikspor (3. Lig) | 2–0 | Usak Belediyespor (3. Lig) |  |
| 2026-10-07 | Golcukspor (3. Lig) | 2–0 | Yozgat (3. Lig) |  |
| 2026-10-07 | Hakkari Zap (no league table (amateur?)) | 6–1 | Adana Demirspor (2. Lig) |  |
| 2026-10-07 | Hatayspor (2. Lig) | 1–2 | Karakopru (3. Lig) |  |
| 2026-10-07 | Karabuk Idmanyurdu (3. Lig) | 1–0 | Beykoz Anadolu (3. Lig) |  |
| 2026-10-07 | Karacabey Bld. (2. Lig) | 3–2 (incl. ET) | Galata (3. Lig) | level after 90 |
| 2026-10-07 | Kars 36 Spor (no league table (amateur?)) | 1–0 | Fatsa Bld. (3. Lig) |  |
| 2026-10-07 | Kucukcekmece (3. Lig) | 5–1 | Buyukcekmece Gucu (3. Lig) |  |
| 2026-10-07 | Malatya (3. Lig) | 3–1 | Gelecek Siirt (no league table (amateur?)) |  |
| 2026-10-07 | Mazidagi (3. Lig) | 1–0 | Kirsehir SK (3. Lig) |  |
| 2026-10-07 | Nigde Bld. (3. Lig) | 0–2 | Agri 1970 (3. Lig) |  |
| 2026-10-07 | Osmaniyespor (3. Lig) | 0–3 | Yeni Mersin Idmanyurdu (3. Lig) |  |
| 2026-10-07 | Pazarspor (3. Lig) | 3–1 | Erbaaspor (2. Lig) |  |
| 2026-10-07 | Silivrispor (3. Lig) | 3–2 | Bulvarspor (3. Lig) |  |
| 2026-10-07 | Soke 1970 (3. Lig) | 1–2 (incl. ET) | Ayvalikgucu (3. Lig) | level after 90 |
| 2026-10-07 | Soma Spor (2. Lig) | 4–2 | Alanya 1221 (3. Lig) |  |
| 2026-10-07 | Tokat (3. Lig) | 1–5 | Etimesgut (3. Lig) |  |
| 2026-10-07 | Zonguldak (3. Lig) | 0–1 | Duzcespor (3. Lig) |  |

## What it can and can't do yet

- The framework does not price the Turkish Cup (only the Super Lig is covered), and SportyBet did not list most qualification ties — they could not have been bet.
- A sample this small sets priors, not a model: the 95% ranges above are wide. Each daily run adds the week's ties; the rounds with Super Lig clubs (which SportyBet does list) are the ones that matter for picks.

