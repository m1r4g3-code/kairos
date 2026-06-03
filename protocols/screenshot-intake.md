# Sub-protocol — screenshot-intake.md (L0, L10)

> How to read a SportyBet screenshot into clean, structured data. Garbage in = garbage out, so this step ends with an **echo-back** the user can correct before I commit.

## What SportyBet screenshots look like

Common layouts the user may send:
- **Single event page:** one match, many markets (1X2 / Double Chance / O/U lines / BTTS / correct score / handicaps) each with decimal odds.
- **Bet slip / booking:** selections already added, a booking code, total odds, stake box.
- **Coupon / fixtures list:** several matches, usually just the 1X2 (Home/Draw/Away = often shown as 1/X/2) odds per row.
- **Live/in-play:** current score + live odds (note the clock — these decay fast).

## What to extract

For every selection visible:
| Field | Notes |
|---|---|
| Home team / Away team | exact names; resolve abbreviations |
| Competition | league/cup if shown |
| Kickoff date & time | critical for lineup-timing & staleness |
| Market | 1X2, DC, O/U `<line>`, BTTS, CS, AH `<line>` … |
| Selection | Home / Draw / Away / Over / Under / Yes / No / score |
| Decimal odds | the number to beat (de-vig in step 2) |
| Booking code / bet ID | so the user can re-find the slip |
| Live? | if in-play, record current score + minute |

## SportyBet notation cheatsheet
- **1 / X / 2** = Home win / Draw / Away win.
- **1X / 12 / X2** = Double Chance (home-or-draw / home-or-away / draw-or-away).
- **GG / NG** = BTTS Yes (both score) / No.
- **Over/Under** usually with the line (e.g. "Ov 2.5").
- **DNB** = Draw No Bet. **AH** = Asian Handicap.
- Odds are **decimal** by default on SportyBet (e.g. 2.10).

## Reading rules
1. **Transcribe, don't infer.** Read exactly what's on the image. If a digit is ambiguous (1.85 vs 1.95), flag it rather than guess.
2. **Multiple matches:** number them; ask which the user actually wants analysed if it's a long coupon (don't analyse 20 games unasked).
3. **If odds are cut off or blurry:** say so and ask for a clearer shot of that market — bad odds poison the whole value calc.
4. **Currency/stake box:** ignore for analysis; the bankroll comes from the user, not the slip.

## Echo-back (always do this)
Before running the engine, restate the parse compactly:

```
Parsed from your screenshot:
• Arsenal vs Chelsea — Premier League — Sat 19:30
  1X2:    Home 2.10 | Draw 3.40 | Away 3.60
  O/U2.5: Over 1.95 | Under 1.85
  BTTS:   Yes 1.80  | No 1.95
Booking code: ABC123
Is this right? (correct any odds I misread before I analyse)
```

Only proceed once the parse is confirmed (or after a beat if the user clearly just wants the read). This guards against the cheapest, most damaging error: a misread price.
