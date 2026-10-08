# Execution design: how automated betting could be added later

Written 2026-10-08 (Phase 5). **This is a design. Nothing here is built, and
nothing in the repository places a bet, logs into a bookmaker or stores a
bookmaker login.**

## The short version

- There is no case for building this today. No edge has been shown on any
  venue: not on Bet365 in recent seasons, not yet on SportyBet, and not on the
  exchanges after commission (new test below).
- The gap the project was built around lives on soft bookmakers, and those are
  the ones that forbid automation. Venues that allow automation price close to
  Pinnacle. This document does not resolve that conflict; it states it.
- If an edge is ever shown, the first venue to consider is Cloudbet, because it
  is the only candidate that secondary sources say accepts Nigerian customers,
  and it has play-money betting through its API. That acceptance is not
  confirmed from Cloudbet's own terms.
- Two gates stand before any build, both from the brief: the owner's written
  approval, and at least 300 settled paper picks whose CLV against Pinnacle's
  close is positive with a 95% interval above zero. Today's count is 3 settled
  picks and 0 with a Pinnacle close.

## 1. The conflict, stated plainly

Kairos compares a soft bookmaker's price with Pinnacle's margin-free price and
bets where the soft price is higher. That only works where a bookmaker is slow
or careless with its prices. Those bookmakers (SportyBet, Bet365 and the like)
forbid bots in their terms and restrict winning accounts. Venues that publish a
betting API want sharp, automated customers, and to survive those customers
they keep their prices close to the sharp market. So the place where the gap
exists cannot be automated, and the places that can be automated have little or
no gap.

There is a second problem on exchanges: commission. A 3% gap before a 4% or 5%
commission on winnings is not a gap.

## 2. What the data says about automatable venues (test E1)

Registered in `research/hypotheses.md` before it was run; numbers in
`research/results/e1_automatable.md`.

**Betfair Exchange pre-match price against Pinnacle's fair price, past seasons.**
Betfair is not open to the owner. It is the only exchange with price history in
the files (1,752 matches, one season of five leagues), so it stands in for "an
exchange". Bets where the price after commission beats Pinnacle's fair price
by 3%:

| Commission on winnings | Bets | CLV | 95% interval | Return per bet | 95% interval |
|---|---|---|---|---|---|
| 0% | 248 | +1.3% | -0.7 to +3.5 | -3.2% | -30.4 to +26.2 |
| 2% | 114 | +1.8% | -1.7 to +5.4 | -6.6% | -51.2 to +44.4 |
| 5% | 37 | +0.9% | -6.9 to +9.4 | -54.7% | -100.0 to +22.3 |

Every interval includes zero and no row reaches 300 bets. Reading: **no edge
shown.** I predicted CLV at or below zero; the point figures came out slightly
positive, which is not evidence of anything at these sample sizes.

**Prices in the paper loop's own snapshots, 3 to 8 October 2026** (72 matches,
six second-tier leagues). Counts of single prices that beat Pinnacle's fair
price:

| Venue | Commission assumed | Prices | Above fair | Above fair by 3% | Above fair after commission | By 3% after commission |
|---|---|---|---|---|---|---|
| Matchbook | 4% | 213 | 42 | 8 | 9 | 2 |
| Smarkets | 2% | 210 | 18 | 3 | 10 | 1 |
| Betfair (UK feed) | 5% | 210 | 40 | 4 | 3 | 1 |
| William Hill (for scale) | none | 210 | 1 | 0 | 1 | 0 |
| 1xBet (for scale) | none | 207 | 6 | 3 | 6 | 3 |

Exchange prices beat Pinnacle's fair price fairly often before commission and
almost never by 3% after it: one or two prices out of about 210 per venue in
five days. The feed says nothing about how much money was available at those
prices, so even those few may not have been bettable at any size. This is a
count over a few days, not a test.

**Which edge survives on automatable venues: none that has been shown.** Three
ideas remain untested, and none of them is the current strategy:

1. *Posting offers instead of taking prices.* On an exchange you can offer a
   price slightly better than Pinnacle's fair price and wait to be matched,
   paying less or no commission on some venues. The danger is being matched
   mostly when the price has already moved against you. Testing it needs
   order-book history that the project does not have.
2. *Speed.* Taking an exchange or Cloudbet price in the minutes after Pinnacle
   moves and before the venue follows. This needs the PC online continuously
   and faster price data than the free tier gives. It is the opposite of a PC
   that is not always on.
3. *Cloudbet as a slower book.* Cloudbet is a bookmaker, not an exchange, and
   may lag Pinnacle in smaller leagues. Nobody has measured it. It can be
   measured for free with a read-only key (see section 7).

## 3. The candidate venues

"Confirmed" below means I read it on the venue's own page. "Secondary" means a
third-party site said so and the venue's own terms page was not readable from
here.

| | Cloudbet | SX Bet | Matchbook |
|---|---|---|---|
| Type | Bookmaker, crypto deposits | Peer-to-peer exchange on its own blockchain, bets in USDC | Betting exchange |
| Betting through an API | Yes: a "Trading" key places bets (confirmed) | Yes: orders signed with the account's private key (confirmed) | Yes: logged-in customers can use the API (confirmed) |
| Practice mode without money | Yes: `PLAY_EUR` test funds, issued by support once the account holds about 10 EUR (confirmed) | Yes: a full test network with test USDC from support (confirmed) | None found |
| Cost | Margin in the price; no commission | Fees on winning bets, set per account and read from the API (confirmed); third-party sites say 0% on single bets (secondary) | Commission on net winnings: 4% outside the UK and Ireland by a 2019 announcement (secondary; one site now says 1.5%). API reads: 100 GBP per million in a month (confirmed) |
| Safety feature | Not found in the pages I could read | Heartbeat: if the program stops, all open orders are cancelled (confirmed) | Not checked |
| Open to Nigeria | Secondary sources say yes | Not established. A directory lists the USA, UK, Australia and Ontario as blocked "and several others" (secondary) | Not established. One list of excluded countries does not include Nigeria (secondary) |
| Terms on bots | Publishes the API for this purpose; terms page returned an error | Publishes the API for this purpose; no terms page found | Publishes the API for this purpose; terms not read |

What this means: every "open to Nigeria" answer has to be confirmed by the
owner on the venue's own terms page, while logged in from Nigeria, before
anything is built for that venue. If a venue does not accept Nigerian
customers, it is dropped. No VPN, no proxy, no account in someone else's name.

Nigerian law on betting with offshore operators is also not something I have
checked, and it is not something I can advise on. The owner needs to satisfy
himself on that before approving a build.

## 4. What would have to be true before building

1. The owner approves in writing.
2. The paper record has at least 300 settled picks with CLV against Pinnacle's
   close positive and its 95% interval above zero. Stand-in closing prices do
   not count.
3. That record was made **on the venue to be automated**, using prices and
   stakes that were available there. A paper edge on other bookmakers does not
   transfer.
4. The venue's own terms, read by the owner, allow a Nigerian customer and
   allow automated betting.
5. The money for it is a fixed, separate amount the owner can afford to lose
   entirely, set by the owner in writing.

## 5. Design

### Where it sits

```
paper loop (exists)                      execution module (not built)
  snapshot -> pick -> close -> settle      reads picks.jsonl
                                           -> pre-trade checks
                                           -> venue adapter (dry-run by default)
                                           -> orders.jsonl, fills.jsonl
                                           -> reconcile against the venue
```

The execution module is a separate process and a separate package. It reads the
picks file the paper loop already writes and never writes to it. The paper loop
keeps running unchanged, so every real bet has a paper twin and the two can be
compared. `core/` and `engine/` stay free of any venue code and any credential.

### One venue adapter per venue

Each adapter offers the same five operations and nothing else: read balance,
read the current price and available stake for a selection, place one bet with
a client-chosen reference, read the status of that reference, cancel. No
deposit, withdrawal or account-settings call is ever implemented. A
`DryRunAdapter` implements the same five operations against recorded prices and
is the default.

### Order of work for one pick

1. Read the pick. Refuse it if it is older than a set age or kickoff is closer
   than a set lead.
2. Re-fetch Pinnacle's price and the venue's price now. Recompute the edge on
   the venue's actual price after commission. Refuse if it is below the
   threshold or if the venue price is better than the pick price by a
   suspicious margin (a large "edge" is treated as a data fault, as in the
   engine today).
3. Run every risk control in section 6. Any failure refuses the bet.
4. Write the intended order to `orders.jsonl` with a unique reference *before*
   sending it. Send it with that reference. Never accept a worse price than
   the one checked.
5. Record the venue's answer. An unknown outcome (timeout, lost connection) is
   never retried blindly: the module asks the venue for the status of that
   reference first. This is what stops a double bet when the PC is cut off
   mid-request.
6. On restart, reconcile: every order in the file without a final status is
   looked up at the venue before anything new is sent.

### The PC that is not always on

A real bet that is placed and then left alone is safe: a pre-match single needs
no further action. The risks are a half-sent order (handled by step 5) and
resting offers on an exchange (on SX Bet the heartbeat cancels them; a venue
without that feature only ever gets immediate take-or-cancel orders). The
module never leaves an unmatched offer at a venue that cannot cancel it
automatically.

## 6. Mandatory risk controls

All of these are required, enforced in one place in code that the adapters
cannot bypass, with limits held in a config file that only the owner edits.
The numbers are the owner's to set; the defaults below are deliberately small.

| Control | Rule | Default |
|---|---|---|
| **Dry-run by default** | The module starts in dry-run. Live mode needs a config value *and* a command-line flag *and* a dated approval file written by the owner. A restart goes back to dry-run unless all three are present. | Dry-run |
| **Maximum stake** | A hard ceiling per bet, in the venue's currency, applied after staking. The existing quarter-Kelly and 5% caps in `core/staking.py` still apply underneath it. | The owner's flat stake (about 500 NGN equivalent) |
| **Daily loss cap** | If settled losses plus open stakes placed today reach the cap, no more bets until the next local day. | 4 stakes |
| **Total exposure cap** | Sum of all unsettled stakes may not exceed a share of the execution bankroll. | 15% (the engine's existing limit) |
| **Per-match cap** | All bets on one match together. | 5% of bankroll (existing rule) |
| **Kill switch** | A stop file, checked before every order. When present: no new orders, cancel open offers, exit. The existing `--stop` command creates it. Also triggered automatically by the drawdown and fault rules below. | Off |
| **Drawdown stop** | If the execution bankroll falls a set share below its high point, the kill switch trips and stays tripped until the owner clears it in writing. | 25% |
| **Fault stop** | Three order errors in a row, any mismatch between the order file and the venue, or a balance that differs from the module's own sum, trips the kill switch. | On |
| **Price sanity** | Refuse any bet whose edge exceeds a ceiling. | 10% |
| **No refill** | The module cannot deposit. When the bankroll is gone it stops. | Always |
| **Daily report** | A file listing every order, fill, refusal and the reason, written whether or not anything happened. | On |

Staged rollout, each stage needing the owner's written go-ahead: dry-run
against live prices for four weeks; then the venue's play-money mode where one
exists; then live at the minimum stake the venue allows for 100 bets; only then
the configured stake.

## 7. Credentials

Storing a key that can place bets is storing a bookmaker credential. The
current rule forbids that, so building this requires the owner to change that
rule in writing, for one named venue.

If that happens: the key lives outside the repository (Windows Credential
Manager, not `.env`), is never logged or printed, is never sent to Claude or
included in any prompt, and is for an account holding only the execution
bankroll. On SX Bet the "key" is a wallet's private key, which controls the
funds outright: that wallet must hold the execution bankroll and nothing else.
Claude's judgment pass stays what it is now: a logged opinion that can veto a
pick and can never trigger a bet.

One step needs no rule change and no money: a **read-only Cloudbet Affiliate
key** cannot place bets, and would let the paper loop record Cloudbet's prices
beside Pinnacle's. That is the cheapest way to find out whether idea 3 in
section 2 has anything in it. It was left open in the Phase 4 report.

## 8. What I did not check

- Any venue's own terms page. Cloudbet's returned an error, Matchbook's and
  SX Bet's I could not find or read. Country access is from third-party sites.
- Nigerian law on betting with offshore operators.
- Liquidity on any exchange: how much could actually be staked at a shown price.
- Minimum stakes, bet-acceptance delays and rejection rates on any venue.
- Matchbook's current commission for Nigerian customers (sources disagree).
- Whether the test modes behave like the live ones.
- The exchange price history covers one season of five big leagues; the paper
  snapshots cover five days of second-tier leagues.

## Sources

- [Cloudbet API documentation](https://cloudbet.github.io/wiki/en/docs/sports/api/) and [test funds](https://cloudbet.github.io/wiki/en/docs/sports/api/test_funds/)
- [Cloudbet key types (Jentic)](https://jentic.com/apis/cloudbet.com)
- [Cloudbet countries guide (secondary)](https://worldpokerdeals.com/online-casinos/articles/cloudbet-countries-guide)
- [SX Bet fees](https://docs.sx.bet/developers/fees.md), [heartbeat](https://docs.sx.bet/developers/heartbeat.md), [test network](https://docs.sx.bet/developers/testnet-and-mainnet.md)
- [SX Bet directory entry (secondary)](https://investinglive.com/directory/prediction-market-platforms/sx-bet)
- [Matchbook API pricing](https://developers.matchbook.com/docs/pricing)
- [Matchbook 2019 commission announcement (secondary)](https://europeangaming.eu/portal/press-releases/2019/08/05/51950/matchbook-betting-exchange-have-announced-a-new-commission-structure-of-2-on-all-sports-from-the-7th-of-august/)
- [Matchbook affiliate listing with excluded countries (secondary)](https://statsdrone.com/affiliate-programs/matchbook/)
- [Matchbook 1.5% figure (secondary)](https://oddspapi.io/blog/?p=2848)
