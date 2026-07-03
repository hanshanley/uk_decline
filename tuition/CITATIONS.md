# Data citations — tuition sub-analysis

Formal citations for every dataset used, identified by the **organization that collected /
published** it. Access dates reflect when the data was retrieved for this analysis
(3 July 2026). Each entry notes which figures it supports.

---

## Primary sources

### United States — tuition, historical series (1963–64 → 2022–23)
**National Center for Education Statistics (NCES), Institute of Education Sciences, U.S.
Department of Education.** (2023). *Digest of Education Statistics 2023*, Table 330.10:
“Average undergraduate tuition, fees, room, and board rates charged for full-time students
in degree-granting postsecondary institutions, by level and control of institution:
Selected academic years, 1963-64 through 2022-23.” Washington, DC: U.S. Department of
Education. Retrieved 3 July 2026, from
<https://nces.ed.gov/programs/digest/d23/tables/dt23_330.10.asp>
*Underlying collection instruments:* Higher Education General Information Survey (HEGIS)
and the Integrated Postsecondary Education Data System (IPEDS).
*Supports:* US line in `tuition_history_real_usd.png`; `data/raw/nces_tuition_public4yr.csv`.

### United States — Consumer Price Index (used for NCES constant dollars)
**U.S. Bureau of Labor Statistics (BLS), U.S. Department of Labor.** Consumer Price Index
(CPI-U). NCES uses the BLS CPI to express Table 330.10 in constant 2022–23 dollars.
*Supports:* the inflation adjustment embedded in the NCES constant-dollar column.

### United Kingdom — statutory tuition fee caps (England)
Primary legislation, published by **The National Archives (legislation.gov.uk) on behalf of
the UK Government / King’s Printer of Acts of Parliament:**
- **Teaching and Higher Education Act 1998**, c. 30. <https://www.legislation.gov.uk/ukpga/1998/30> (introduced £1,000 fees, 1998/99).
- **Higher Education Act 2004**, c. 8. <https://www.legislation.gov.uk/ukpga/2004/8> (variable fees up to £3,000, 2006/07).
- **The Higher Education (Higher Amount) (England) Regulations 2010**, SI 2010/3021. <https://www.legislation.gov.uk/uksi/2010/3021> (£9,000 cap, 2012/13).
- **The Higher Education (Basic Amount and Higher Amount) (England) Regulations 2016**, SI 2016/1206. <https://www.legislation.gov.uk/uksi/2016/1206> (£9,250 cap, 2017/18).

Compiled cross-reference: **House of Commons Library, UK Parliament.** (2024). *Higher
education tuition fees in England* (Research Briefing CBP-8151).
<https://commonslibrary.parliament.uk/research-briefings/cbp-8151/>
*Supports:* UK line in `tuition_history_real_usd.png`; `data/raw/tuition_history_manual.csv`.

### Inflation and exchange rates
**The World Bank Group.** (2024). *World Development Indicators.* Washington, DC: The World
Bank. Retrieved via the World Bank API on 3 July 2026.
- Consumer price index (2010 = 100) — indicator `FP.CPI.TOTL`: <https://data.worldbank.org/indicator/FP.CPI.TOTL>
- Official exchange rate (LCU per US$, period average) — indicator `PA.NUS.FCRF`: <https://data.worldbank.org/indicator/PA.NUS.FCRF>

*Original data compiler for both indicators:* **International Monetary Fund (IMF),
*International Financial Statistics*** (and national statistical offices), redistributed by
the World Bank.
*Supports:* GBP→USD conversion and constant-2022 deflation of UK/EU figures.

---

## Secondary sources (published summaries of primary reports)

### European Union (EU-27) — domestic tuition fees, 2023/24 snapshot
**European Commission / European Education and Culture Executive Agency (EACEA) /
Eurydice.** (2023). *National Student Fee and Support Systems in European Higher Education —
2023/24* (Eurydice – Facts and Figures). Luxembourg: Publications Office of the European
Union. <https://eurydice.eacea.ec.europa.eu/publications/national-student-fee-and-support-systems-european-higher-education-202324>
*Supports:* EU-27 rows in `data/raw/manual_tuition.csv` (rows flagged `APPROXIMATE` are not
pinned to an exact primary figure and should be verified against the primary report).

### United States — tuition, 2024/25 snapshot
**College Board.** (2024). *Trends in College Pricing and Student Aid 2024.* New York:
College Board. <https://research.collegeboard.org/trends/college-pricing>
*Supports:* the US snapshot figure ($11,610 in-state public, 2024/25) in
`data/raw/manual_tuition.csv`. (The fully primary-sourced US figure used in the historical
series is the NCES series above.)

### Germany — tuition fee history
**Study.eu** (secondary web reference), *The History of Tuition Fees in Germany*.
<https://www.study.eu/article/the-history-of-tuition-fees-in-germany> — corroborated by the
Eurydice report above.
*Supports:* Germany line in `tuition_history_real_usd.png`.

---

*Note on provenance:* the historical US/UK/Germany series is built entirely from the
**primary sources** above (NCES, UK legislation, World Bank/IMF). The EU-27 cross-sectional
snapshot rests on the **Eurydice** summary and College Board (secondary), as noted.
