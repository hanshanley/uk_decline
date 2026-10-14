# Data citations — tuition sub-analysis

Formal citations for every dataset used, identified by the **organization that collected /
published** it. NCES, College Board and the live World Bank inputs below were
retrieved on **14 October 2026**; earlier historical references retain their
original retrieval dates. Each entry notes which figures it supports.

---

## Primary sources

### United States — tuition, historical series (1963–64 → 2023–24)
**National Center for Education Statistics (NCES), Institute of Education Sciences, U.S.
Department of Education.** (2024). *Digest of Education Statistics 2024*, Table 330.10:
“Average undergraduate tuition, fees, room, and board rates charged for full-time students
in degree-granting postsecondary institutions, by level and control of institution:
Selected academic years, 1963-64 through 2023-24.” Washington, DC: U.S. Department of
Education. Retrieved 14 October 2026, from
<https://nces.ed.gov/programs/digest/d24/tables/dt24_330.10.asp>
*Underlying collection instruments:* Higher Education General Information Survey (HEGIS)
and the Integrated Postsecondary Education Data System (IPEDS).
*Supports:* US line in `tuition_history_real_usd.png`; `data/raw/nces_tuition_public4yr.csv`.

### United States — Consumer Price Index (used for NCES constant dollars)
**U.S. Bureau of Labor Statistics (BLS), U.S. Department of Labor.** Consumer Price Index
(CPI-U). NCES uses the BLS CPI to express Table 330.10 in constant 2023–24 dollars.
*Supports:* the inflation adjustment embedded in the NCES constant-dollar column.
That academic-year column is retained with an explicit base label in the raw
CSV; the historical comparison instead deflates both countries using the same
calendar-year World Bank US CPI.

### United States — tuition, 2025/26 snapshot
**College Board.** (2025). *Trends in College Pricing 2025*, Table CP-1,
“Average Published Prices (Enrollment-Weighted) for Full-Time Undergraduates,
2024-25 and 2025-26.” Retrieved 14 October 2026.
<https://research.collegeboard.org/media/xlsx/Trends-in_College-Pricing-2025-excel-data.xlsx>
*Supports:* the US snapshot ($11,950 public four-year in-state; $45,000 private
nonprofit reference) in `data/raw/manual_tuition.csv`. College Board publishes
this table; the separate historical line remains on NCES rather than splicing
the two collections.

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

**House of Commons Hansard**, 1 March 2013, column 748W, *Students: Per Capita Costs*,
written answer by David Willetts to Chris Ruane (question 145020).
<https://publications.parliament.uk/pa/cm201213/cmhansrd/cm130301/text/130301w0003.htm#13030166000152>
The table gives each academic year's maximum fee for new entrants, including annual
upratings from £1,000 to £1,175 (1998–2005) and £3,000 to £3,375 (2006–2011).
*Supports:* corrected annual caps in `data/raw/tuition_history_manual.csv`.

**Department for Education / Student Finance England.** *Changes to tuition fees:
2026 to 2027 academic year and 2027 to 2028 academic year*. Retrieved 14 October 2026.
<https://www.gov.uk/government/publications/tuition-fees-and-student-support-2026-to-2027-academic-year/changes-to-tuition-fees-2026-to-2027-academic-year-and-2027-to-2028-academic-year>
The standard full-time cap at approved fee-cap providers with a TEF award and
an access and participation plan is **£9,790 in 2026/27**. The announced
**£10,050 for 2027/28** is a future policy rate, not a current-year observation.
*Supports:* the nominal England cap figure and overview endpoint.

### Inflation and exchange rates
**The World Bank Group.** (2024). *World Development Indicators.* Washington, DC: The World
Bank. Retrieved via the World Bank API on 14 October 2026.
- Consumer price index (2010 = 100) — indicator `FP.CPI.TOTL`: <https://data.worldbank.org/indicator/FP.CPI.TOTL>
- Official exchange rate (LCU per US$, period average) — indicator `PA.NUS.FCRF`: <https://data.worldbank.org/indicator/PA.NUS.FCRF>

*Original data compiler for both indicators:* **International Monetary Fund (IMF),
*International Financial Statistics*** (and national statistical offices), redistributed by
the World Bank.
*Supports:* GBP→USD conversion and common calendar-2022 deflation of US/England
tuition history and eligible snapshot figures. NCES's academic-year constant-dollar
column is retained as raw source data but not mixed with the calendar-year series.

---

## Secondary sources (published summaries of primary reports)

### European Union (EU-27) — domestic tuition fees, 2023/24 snapshot
**European Commission / European Education and Culture Executive Agency (EACEA) /
Eurydice.** (2023). *National Student Fee and Support Systems in European Higher Education —
2023/24* (Eurydice – Facts and Figures). Luxembourg: Publications Office of the European
Union. <https://eurydice.eacea.ec.europa.eu/publications/national-student-fee-and-support-systems-european-higher-education-202324>
*Supports:* EU-27 rows in `data/raw/manual_tuition.csv` (rows flagged `APPROXIMATE` are not
pinned to an exact primary figure and should be verified against the primary report).

### Germany — tuition fee history
**Study.eu** (secondary web reference), *The History of Tuition Fees in Germany*.
<https://www.study.eu/article/the-history-of-tuition-fees-in-germany> — corroborated by the
Eurydice report above.
*Supports:* Germany line in `tuition_history_real_usd.png`.

---

*Note on provenance:* the historical US/England series uses the **primary sources**
above (NCES, UK legislation/Hansard, World Bank/IMF). Germany's sparse zero-fee reference
points use secondary sources and do not imply uninterrupted fee-free education.
The EU-27 cross-sectional
snapshot rests on the **Eurydice** summary; the current US snapshot is taken
directly from College Board Table CP-1.
