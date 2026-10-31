# UNIVERSE: the fence (widened Sat Oct 31, 2026)

Aaron's order: "Make the fence pretty wide but not like too much of
penny stocks." The standing covered universe in scanner.py grew
from 55 to **150 unique names**. Every covered name gets a WATCHER,
a SHADOW, and two RIVAL bots (RAIDER breakout, ANCHOR mean
reversion) minted by bot_factory.py, plus sector patch coverage.

## The rule for standing coverage

A name earns standing coverage when it is a real stock: price
generally above $5, real daily dollar volume, a name the sim can
fill cleanly. Microcap squeeze names do not get standing coverage.

## Excluded (penny fence)

Explicitly EXCLUDED from standing coverage, scan only (the
marketwide big move scan and the capped day trade sleeve may still
see them; no watcher, shadow, rival or sniper is minted on them):

- UMAC, ONDS, AMPX (five month old drone rumor names)
- NUWE, BRAI (microcap squeeze names from the Oct 28 watch)
- and anything similar: sub $5 microcaps without real volume

The list lives in scanner.py as EXCLUDED_PENNY next to UNIVERSE.

## The 150, by group (scanner.py UNIVERSE)

- tech (20): AAPL MSFT GOOGL AMZN META PLTR NOW CRM ORCL ADBE CSCO
  PANW CRWD SNOW NET DDOG IBM AKAM LOGI CRSR
- semis (20): NVDA AVGO AMD MU SMCI INTC MRVL QCOM TXN AMAT LRCX
  KLAC ADI TSM ARM ASML ANET CDNS SNPS SNDK
- crypto_fintech (9): COIN MSTR RIOT HOOD SOFI MARA CLSK PYPL AFRM
- high_beta (6): TSLA RKLB IONQ RDDT RBLX CVNA
- nuclear (9): OKLO SMR NNE CCJ UUUU DNN CEG VST BWXT
- energy (9): XOM CVX LNG COP OXY SLB EOG WMB KMI
- defense (8): KTOS LMT RTX NOC GD BA AVAV HII
- banks (8): JPM BAC WFC C GS MS SCHW USB
- payments (6): GPN V MA AXP FIS COF
- healthcare_biotech (12): REGN LLY UNH MRNA ABBV AMGN GILD VRTX
  BIIB MRK PFE ISRG
- retail (14): WMT COST CPRI HD LOW TGT NKE SBUX MCD CMG LULU KO
  PEP MNST
- travel (10): DAL UAL AAL LUV MAR BKNG ABNB CCL RCL EXPE
- industrials (8): CAT DE GE HON UPS FDX EMR ETN
- media_telecom (6): DIS NFLX T VZ TMUS CMCSA
- materials (5): FCX NEM AA STLD NUE (STLD replaced X: US Steel
  was delisted after its acquisition, its chart feed is dead)
- pairs_watch (KO, PEP; already counted in retail)

Total unique: 150 (was 55; 95 added).

Founder's exception (Sat Oct 31, 2026): CRSR (Corsair Gaming) is a
small cap trading near the penny fence line, covered anyway by
Aaron's direct order ("Also watch logi and Corsair"). It is NOT in
EXCLUDED_PENNY. LOGI (Logitech) and CRSR both sit in the tech group
and report to the CIRCUIT patch (hardware), not STACK.
