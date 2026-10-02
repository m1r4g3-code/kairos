# Kairos — Phase 1 research

Date: 2026-10-02. Branch: `dev/phase-1-research`. No engine code was changed.

## How to read this

Every claim about the outside world carries a source number in square brackets; the list is at the end. For most papers I read the abstract or a summary of it, not the full text. Where a number comes from a secondary summary instead of the paper itself, the source list says so. Nothing here describes the internals of a private syndicate: no public source I found does, and I have not guessed.

The three target measures, in order, are closing-line value (CLV), return per bet with an interval, and calibration.

## Summary

1. **The soft-versus-sharp idea has public support, but in a different form from how Kairos uses it.** Two public studies made 3–5% per bet by taking the best price among *many* bookmakers when it beat a consensus or Pinnacle fair price [1][2][3]. Kairos checks *one* bookmaker. The Phase 0 diagnostic found one mainstream bookmaker beats Pinnacle's same-time fair price by 2% on about 0.3% of outcomes. Nobody has published this measurement for SportyBet or any Nigerian bookmaker.
2. **A better goal model is unlikely to beat the closing price in major leagues.** A 2026 study over 19 Serie A seasons fitted the best blend of a Dixon-Coles model and the closing price; the weight on the model came out as 0.000 [4]. Differences between goal models are in the fourth decimal place of the score [5].
3. **The model is still useful for one job:** turning a sharp 1X2 and totals price into fair prices for the related markets SportyBet offers (double chance, other goal lines, handicaps).
4. **No evidence says a language model beats a sharp price on football.** In two live 2026 World Cup studies, frontier models (including Claude) did not beat the market, and web access helped only slightly [6][7]. Its value has to be measured forward, and cannot be backtested honestly [8].
5. **Winners get limited.** UK regulator data: 4.31% of accounts restricted, and restricted customers were nearly twice as likely to be in profit [9]. The one academic team that ran this strategy with real money was limited within months [1][10].
6. **One data source must be dropped.** Understat's `robots.txt` disallows all automated access [11]. Under the brief's rule the Understat adapter should not be used.

---

## 1. Rating and goal models

**What is public**

- **Dixon and Coles (1997)** added two things to the plain Poisson model: a correction for low scores, and a time decay so recent matches count more [12]. Kairos has the first and not the second; it has no fitted ratings at all, only numbers typed into a spec.
- **Time weighting is where the gain is.** A rolling test on ten Eredivisie seasons scored six goal models between 0.1914 and 0.1916 (ranked probability score, lower is better). Adding time decay to Dixon-Coles improved it to 0.1891 [5]. Model family barely matters; recency does.
- **Bivariate Poisson** did best of ten rating models in a comparison by Ley et al., with independent Poisson close behind, all fitted by time-weighted likelihood [13]. The Eredivisie test above ranked it last by a hair [5]. Read together: no reliable difference.
- **Dynamic ratings.** Koopman and Lit let attack and defence strengths move over time in a state-space model [14]; Rue and Salvesen did the same in a Bayesian setting and applied it to betting [15]. Simpler update-per-match systems are Elo for football [16] and pi-ratings, which their authors report beat that Elo version [17]. Pi-ratings plus gradient-boosted trees gave the best score in the 2017 Soccer Prediction Challenge after the competition closed (RPS 0.2063) [18].
- **Hierarchical models** share strength across teams; Baio and Blangiardo found plain pooling shrinks the best and worst teams too far towards the middle and needed a mixture to fix it [19].
- **Shots and expected goals carry more signal than goals.** Mead et al. found xG predicted the next result better than goals or shots in the five big leagues in 2017-18 (for example 52.1% against 49.5% in England) [20]. Wheatcroft's ratings built on shots and corners, not goals, earned about 0.8% per bet on over/under 2.5 across ten leagues and twelve years [21].
- **Lineups.** Arntzen and Hvattum found player-based ratings of the starting eleven predicted about as well as team Elo, not better [22].

**What it means for Kairos**

A fitted, time-weighted model would be a real improvement over hand-typed expected goals. It would still lose to the closing price in covered leagues (section 3). Shots and corners are already in the Football-Data files Kairos caches (`HS`, `AS`, `HST`, `AST`, `HC`, `AC`), so shot-based ratings need no new data source.

**Where the trail ends**

How betting syndicates build ratings is not public. Lineup-adjusted models need player data that I found no free, terms-clean source for.

## 2. Reading the market

- **De-vig method.** Štrumbelj found Shin's method gives more accurate probabilities than simple normalisation [23]. Clarke, Kovalchik and Ingram found the power method beat the multiplicative one in three sports and matched or beat Shin [24]. Kairos uses power in `edge.py` and proportional in `run.py`. Neither paper is on Pinnacle football specifically, so this needs testing on our own data.
- **How good is the closing line?** Buchdahl reports that across 87,960 odds pairs the ratio of an earlier price to Pinnacle's closing price predicted returns almost one for one [25]. Pinnacle's opening prices were nearly as efficient as its closing ones on 147,629 matches [26].
- **Individual bookmakers ignore each other.** Across 51 bookmakers and 16,000 English matches, odds were unbiased overall, but each bookmaker's odds failed to use information in its competitors' odds [27]. This is the academic basis for soft-versus-sharp.
- **Favourite-longshot bias** exists in some European leagues and not others [28]; Elaad et al. found none in England [27].
- **Weighting several sharp sources.** I found no public study that fits weights across sharp books. Kaunitz et al. used a plain mean of all bookmakers [1][10]; Buchdahl uses Pinnacle alone [2]. The trail ends there.

## 3. Combining model and market

- **Log opinion pool with a fitted weight.** Pitcan (2026) fitted the weight on a Dixon-Coles model against the margin-free closing price over 7,220 Serie A matches. The fitted weight was 0.000, and the market won in all seven test seasons (RPS 0.1905 against 0.1972) [4].
- **Recalibrated pools.** Ranjan and Gneiting showed a weighted average of calibrated forecasts is itself uncalibrated and proposed a beta-transformed pool with weights fitted by likelihood [29].
- **Odds inside the model.** Egidi, Pauli and Torelli made scoring rates a mix of history and bookmaker odds [30].
- **Be different, not just accurate.** Hubáček, Šourek and Železný got higher returns by training a model to be *less correlated* with the bookmaker than by maximising accuracy [31]. A follow-up argues a model worse than the market can still profit if its errors differ from the market's [32].

**What it means for Kairos:** the blend weight is a number to fit on history, and the honest prior is that it is zero in major leagues. The audit showed `run.py` gives the model a weight of one.

## 4. Calibration

- Platt scaling and isotonic regression are the standard corrections; isotonic needs more data [33]. Beta calibration is a three-parameter improvement on Platt [34].
- Walsh and Joshi selected NBA models by calibration instead of accuracy and report +34.69% average ROI against −35.17% [35]. The size of that gap is from one sport and one bookmaker; the direction is the useful part.

## 5. Staking

- Kelly with an uncertain probability over-bets; Baker and McHale show the stake should be shrunk and give a simple correction [36].
- An experimental review across horse racing, basketball and football found fractional Kelly best or near best in most tests, provided the fraction is tuned [37].
- For many bets at once, Whitrow gives algorithms that generalise Kelly [38].

Kairos already uses quarter Kelly with caps. The gaps are the ones in the audit: same-match bets are sized as if independent, and the fraction was never tuned.

## 6. Evaluation

- **Which score.** Constantinou and Fenton argued for the ranked probability score [39]; Wheatcroft argued against it and for the log score [40]. The brief asks for Brier and log loss; I would report both and not RPS.
- **CLV.** The evidence that beating Pinnacle's close predicts profit is Buchdahl's [25]. He also shows its limit: for bets that were outliers against Pinnacle, expected yield was 4.13% at bet time and 2.88% by closing odds, with actual 4.90% over 26,960 bets [3]. CLV can understate or overstate; it needs an interval and a second measure beside it.
- **Timing traps.** Buchdahl's own opening-price study found bet365 opened before Pinnacle in 48 of 50 sampled matches and had moved by the time Pinnacle opened, so the "simultaneous" comparison was not simultaneous [26]. This is the same fault found in `backtest.py`.
- **Testing many ideas on one history.** The probability of backtest overfitting and the deflated Sharpe ratio adjust for the number of variants tried [41][42]. A betting example: a published tennis strategy's profit came largely from one bet at an erroneous price; after cleaning, most profit vanished and nothing survived out of sample [43].

## 7. Language-model judgment in forecasting

- **General forecasting.** A retrieval-based system scored Brier 0.179 against 0.149 for the human crowd [44]. On ForecastBench, superforecasters scored 0.093 and the best model 0.111 [45]. An ensemble of twelve models matched a human crowd on 31 questions [46].
- **Football specifically.** Over all 104 matches of the 2026 World Cup, four frontier models (Claude Opus 4.8, GPT-5.5, Gemini 3.1 Pro, Grok) did not beat the market on Brier score; a flat stake on the market favourite out-earned all four; their betting returns ranged from −18% to +10% [6]. A second study of seven models found web access improved Brier by only 0.023 [7].
- **Measurement.** Backtests of language models leak the future through training data, search results and question selection [8]. A historical test of Claude's judgment would not be trustworthy.

**What it means for Kairos:** there is no evidence the judgment layer improves on a sharp price, and some that it does not. The only valid test is forward: log the probability before and after judgment and compare.

## 8. Where individuals win

- **Outlier prices at soft bookmakers.** Kaunitz, Zhong and Kreiner bet when one bookmaker's odds beat the cross-bookmaker average by a margin: 56,435 simulated bets at 3.5% return, 407 paper bets at 5.5%, 265 real bets at 8.5% [10]. Buchdahl's version against Pinnacle: 26,960 bets, 4.90% [3].
- **Totals from shot data:** about 0.8% per bet [21].
- **Lower leagues and news speed.** I found betting blogs asserting these are softer and no study measuring it. Treat as unproven.

## 9. Practical limits

- **Account restrictions.** Kaunitz et al. had stakes cut or bets sent for manual review after a few months [1][10]. In UK data on 14.9 million accounts, 4.31% were restricted; 46.78% of restricted customers were in profit against 25.42% of all customers; 58.6% of stake-limited accounts were cut to under 10% of normal [9]. The regulator will not intervene [9].
- **Sharp venues.** Pinnacle is widely described as not limiting winners [47]; I could not read its own policy page. Betfair charges 5% commission on net winnings in most regions [48]; secondary sources say it does not accept Nigerian customers [49], which I did not confirm with Betfair. No workaround is proposed.
- **SportyBet's own practice** on limiting winners: not found.

---

## Data-source terms (question 5)

| Source | What I found | Consequence |
|---|---|---|
| The Odds API | Terms permit storing data indefinitely, research and model training; forbid redistributing it as a data product [50]. Free plan 500 credits a month; a call costs regions × markets; historical odds are paid only [51]. | Fine to use and cache. A `uk,eu` 1X2 call costs 2 credits, so 250 calls a month. Do not publish raw odds dumps. |
| Football-Data.co.uk | `notes.txt` states odds are collected Friday afternoon for weekend games and Tuesday afternoon for midweek [52]. It contains no terms. The site returned HTTP 429 after three quick requests from me. | Collection time confirms the audit's look-ahead finding. Download each file once and reuse the cache. Terms not found. |
| Understat | `robots.txt` is `User-agent: * / Disallow: /` (fetched 2026-10-02) [11]. | Do not use `sources/understat.py` against the live site. Use shots and corners from Football-Data instead. |
| Club Elo | API page redirected and then refused the connection. | Terms unknown. Do not rely on it until checked. |

## Unattended Claude Code (question 3)

Tested on 2026-10-02. A Windows scheduled task ran `claude -p` with `--allowedTools Read`, logged in through the claude.ai subscription (Pro plan, no API key). It read `KAIROS.md`, returned the right answer, and exited 0 in 48 seconds. The test task was deleted afterwards.

Limits found:
- The task ran in "Interactive only" mode, so it runs only while the owner is logged in to Windows.
- Default power settings stop it on battery.
- It used the default model (Opus). A scheduled job should name a smaller model to stay inside Pro usage limits.
- Not tested: after a reboot, after the login token expires, or when the usage limit is reached.

---

## Ranked proposals

Preconditions, not proposals: the defects in audit section 5a must be fixed first, and Phase 2 must exist before any of the tests below can run.

One warning for Phase 2: the ten league-seasons used in the audit (five leagues, 2023/24 and 2024/25) have now been looked at. They cannot serve as holdout.

### A. Testable on history

| Rank | Proposal | Evidence | Expected effect (CLV / return / calibration) | Cost | Test that confirms or kills it |
|---|---|---|---|---|---|
| 1 | **Checked sharp reference.** Use Pinnacle only when it agrees with the median of other books within a set gap, require a minimum book count, and never fall back to a lone soft book. | [1][27]; audit 5a #9 | CLV up by removing false positives; fewer bets; calibration of the reference slightly up | Small | Walk-forward on Football-Data: log loss of the reference against results for Pinnacle alone, market average alone, and the checked blend. Keep the gate only if holdout log loss is no worse and flagged-bet CLV is higher. Kill if the interval on the difference includes zero. |
| 2 | **De-vig bake-off.** Add Shin; compare proportional, power and Shin on Pinnacle closing prices. | [23][24] | Calibration: small. CLV and return: indirect, through more accurate EV on longshots | Small | Holdout log loss by league and by odds band. Adopt the winner only if its bootstrap interval excludes the others. Otherwise keep power. |
| 3 | **Price cousin markets from the sharp line.** Fit expected goals to Pinnacle's 1X2 and total, then price double chance, other goal lines and handicaps with correct quarter-line settlement. | [4][5]; audit 5a #4 | Makes value checks possible on markets with no sharp feed. Calibration of those prices is the measure | Medium | Fit from Pinnacle 1X2 only; predict over 2.5. Compare log loss with Pinnacle's own de-vigged over/under price and with Bet365's. Kill if the derived price is worse than Bet365's own, because then it cannot find value at a soft book. |
| 4 | **Same-match exposure and Kelly shrinkage.** Group bets by match; shrink the fraction for uncertain edges. | [36][37][38] | No effect on CLV. Lower drawdown; return per bet unchanged | Small | Bootstrap bankroll paths on the holdout bet set: median growth and worst drawdown against flat stakes and current quarter Kelly. Keep if drawdown falls with no loss of median growth. |
| 5 | **Fitted time-weighted ratings, blended with the market by a fitted weight.** | [12][5][4][29] | Honest expectation: weight near zero in covered leagues, so no change to any measure. Possible use only where no sharp line exists | Large. Likely needs numpy/scipy, which I would ask for | Fit the log-pool weight walk-forward. Merge only if the weight's interval excludes zero and holdout log loss improves. I expect this to be killed. |
| 6 | **Shot-and-corner ratings for totals.** | [21][20] | Public result is 0.8% per bet, thin against a 5–6% soft-book margin | Medium | Over/under 2.5 on holdout: CLV against Pinnacle closing total with an interval. Kill if the interval includes zero. |
| 7 | **Calibration layer** (beta or Platt) on model-path probabilities. | [33][34][35] | Calibration up; only relevant if 5 or 6 survives | Small | Holdout log loss before and after. |

### B. Forward-only (cannot be backtested)

| Rank | Proposal | Evidence | Expected effect | Cost | Test |
|---|---|---|---|---|---|
| F1 | **SportyBet gap census.** For every SportyBet price seen, log it with Pinnacle's fair price at that moment and again at close. | [1][2][27]; audit 3c | None directly. It is the only way to learn whether the edge exists at this bookmaker | Small, but SportyBet prices arrive by screenshot | After 1,000 logged prices: share beating Pinnacle fair by 2%+, and their CLV with an interval. Kill the single-book strategy if the share is under 1% and the CLV interval includes zero. |
| F2 | **Measure the judgment layer.** Log probability before and after Claude's adjustment. Limit Claude to flags and vetoes until the data says otherwise. | [6][7][8] | Unknown; the public evidence leans towards none | Small | Over 300 settled picks: log loss and CLV of adjusted against raw. Drop adjustments if adjusted is not better. |
| F3 | **Timing.** Record SportyBet against Pinnacle at fixed times before kickoff. | [26]; margins in audit 3c | Could raise CLV if SportyBet lags after news | Medium; limited by 250 calls a month | Gap frequency and CLV by time window. Kill if no window differs. |

**The most important item is F1.** Every public result that made money did it by picking outliers across many bookmakers. Kairos has one. Whether that one is soft enough is unmeasured, and no engine change substitutes for measuring it.

## What I did not check

- Full text of most papers; I worked from abstracts and summaries.
- Buchdahl's main "Wisdom of the Crowd" paper (the site rate-limited me); its figures here come from his two blog posts and a secondary summary.
- Pinnacle's and Betfair's own policy pages, and whether Betfair accepts Nigerian customers.
- SportyBet's terms, margins or limiting practice.
- Terms of use for Football-Data.co.uk and Club Elo.
- The Odds API's credit rule in its own documentation (taken from secondary sources).
- Cloudbet, SX Bet and NaijaBet-Api, which the brief assigns to Phase 4.
- Whether lower leagues are softer: no study found.

## Sources

1. Kaunitz, Zhong, Kreiner (2017), "Beating the bookies with their own numbers". https://arxiv.org/abs/1710.02824
2. Buchdahl, "Using the wisdom of the crowd to find value in a football match betting market". https://www.football-data.co.uk/The_Wisdom_of_the_Crowd_updated.pdf (not read; rate-limited)
3. Buchdahl, "What is the true expected profit for the Wisdom of the Crowd betting system?". https://football-data.co.uk/blog/wisdom_of_crowd_betting_system_closing_odds.php
4. Pitcan (2026), "Does a structural model add anything to the closing price?". https://arxiv.org/abs/2608.11505
5. Eastwood (2025), "Which model should you use to predict football matches?". https://pena.lt/y/2025/03/10/which-model-should-you-use-to-predict-football-matches/
6. Ding, Guo, Xu (2026), "FIFA World Cup 2026 as a contamination-free benchmark for LLM forecasting agents". https://arxiv.org/abs/2607.17765
7. Schröder et al. (2026), "LLM-SoccerArena". https://arxiv.org/abs/2607.24573
8. Paleka et al. (2025), "Pitfalls in evaluating language model forecasters". https://arxiv.org/abs/2506.00723
9. UK Gambling Commission (2025), "Commercial restrictions by betting operators". https://www.gamblingcommission.gov.uk/blog/post/commercial-restrictions-by-betting-operators
10. MIT Technology Review (2017), "The secret betting strategy that beats online bookmakers" (source of the Kaunitz figures). https://www.technologyreview.com/2017/10/19/67760/the-secret-betting-strategy-that-beats-online-bookmakers/
11. https://understat.com/robots.txt
12. Dixon, Coles (1997), JRSS C 46(2). https://eprints.lancs.ac.uk/id/eprint/19492/
13. Ley, Van de Wiele, Van Eetvelde (2019), Statistical Modelling 19(1). https://orbilu.uni.lu/handle/10993/57869
14. Koopman, Lit (2015), JRSS A 178(1). https://doi.org/10.1111/rssa.12042
15. Rue, Salvesen (2000), The Statistician. https://academia.kaust.edu.sa/en/publications/prediction-and-retrospective-analysis-of-soccer-matches-in-a-leag
16. Hvattum, Arntzen (2010), Int. J. Forecasting. https://www.sciencedirect.com/science/article/abs/pii/S0169207009001708
17. Constantinou, Fenton (2013), pi-ratings; summary at https://penaltyblog.readthedocs.io/en/latest/ratings/pi.html
18. 2017 Soccer Prediction Challenge results, summarised in https://arxiv.org/pdf/2403.07669 (secondary)
19. Baio, Blangiardo (2010), J. Applied Statistics. https://discovery.ucl.ac.uk/16040/
20. Mead, O'Hare, McMenemy (2023), PLoS One. https://pmc.ncbi.nlm.nih.gov/articles/PMC10075453/
21. Wheatcroft (2020), Int. J. Forecasting 36(3). https://eprints.lse.ac.uk/103712
22. Arntzen, Hvattum (2021), Statistical Modelling 21(5). https://journals.sagepub.com/doi/abs/10.1177/1471082X20929881
23. Štrumbelj (2014), Int. J. Forecasting 30(4). https://www.sciencedirect.com/science/article/abs/pii/S0169207014000533
24. Clarke, Kovalchik, Ingram (2017), American J. Sports Science 5(6). https://www.sciencepublishinggroup.com/article/10.11648/j.ajss.20170506.12
25. Buchdahl's closing-line analysis, as summarised at https://howprosbet.com/what-is-closing-line-value/ (secondary)
26. Buchdahl, "Market efficiency of opening betting odds at Pinnacle compared to bet365". https://www.football-data.co.uk/blog/opening_price_wisdom.php
27. Elaad, Reade, Singleton (2020), Finance Research Letters 35. https://centaur.reading.ac.uk/86111/1/betting_efficiency_elaad_reade_singleton.pdf
28. Angelini, De Angelis (2019), Int. J. Forecasting 35(2). https://doi.org/10.2139/ssrn.3070329
29. Ranjan, Gneiting (2010), JRSS B 72(1). https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9868.2009.00726.x
30. Egidi, Pauli, Torelli (2018), Statistical Modelling 18. https://arxiv.org/pdf/1802.08848
31. Hubáček, Šourek, Železný (2019), Int. J. Forecasting 35(2). http://ida.felk.cvut.cz/zelezny/pubs/ijf.2019.pdf
32. Hubáček, Šír (2023), Int. J. Forecasting 39(2). https://arxiv.org/pdf/2010.12508
33. Niculescu-Mizil, Caruana (2005). https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf
34. Kull, Silva Filho, Flach (2017). https://proceedings.mlr.press/v54/kull17a.html
35. Walsh, Joshi (2024), Machine Learning with Applications. https://arxiv.org/pdf/2303.06021
36. Baker, McHale (2013), Decision Analysis 10(3). https://pubsonline.informs.org/doi/10.1287/deca.2013.0271
37. Uhrín, Šourek, Hubáček, Železný (2021). https://arxiv.org/abs/2107.08827
38. Whitrow (2007), JRSS C 56(5). https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9876.2007.00594.x
39. Constantinou, Fenton (2012), J. Quantitative Analysis in Sports 8(1) (title and venue from search results)
40. Wheatcroft (2021), J. Quantitative Analysis in Sports 17(4). https://arxiv.org/pdf/1908.08980
41. Bailey, Borwein, López de Prado, Zhu (2015). http://ssrn.com/abstract=2326253
42. Bailey, López de Prado (2014). http://ssrn.com/abstract=2460551
43. Clegg, Cartlidge (2023), "Not feeling the buzz". https://arxiv.org/abs/2306.01740
44. Halawi et al. (2024). https://arxiv.org/pdf/2402.18563
45. Karger et al., ForecastBench. https://arxiv.org/html/2409.19839v5
46. Schoenegger et al. (2024), Science Advances 10(45). https://arxiv.org/abs/2402.19379v1
47. https://www.completesports.com/pinnacles-winners-welcome-policy/ (secondary)
48. Betfair support, "What is commission and how is it calculated?". https://support.betfair.com/app/answers/detail/413-exchange-what-is-commission-and-how-is-it-calculated/ (figures from search summary)
49. https://betfairsquare.com/blog/betfair-by-country-availability-guide-2026 (secondary)
50. The Odds API terms. https://the-odds-api.com/terms-and-conditions.html
51. https://oddspapi.io/blog/odds-api-pricing-2026-comparison/ (secondary)
52. https://www.football-data.co.uk/notes.txt
