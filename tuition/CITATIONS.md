# Data citations — tuition sub-analysis

Formal citations for every dataset used, identified by the **organization that collected /
published** it. NCES, College Board and the live World Bank inputs below were
retrieved on **14 October 2026**; earlier historical references retain their
original retrieval dates. Each entry notes which figures it supports.

---

## Primary sources

### United States — separate NCES reference (1963–64 → 2023–24)
**National Center for Education Statistics (NCES), Institute of Education Sciences, U.S.
Department of Education.** (2024). *Digest of Education Statistics 2024*, Table 330.10:
“Average undergraduate tuition, fees, room, and board rates charged for full-time students
in degree-granting postsecondary institutions, by level and control of institution:
Selected academic years, 1963-64 through 2023-24.” Washington, DC: U.S. Department of
Education. Retrieved 14 October 2026, from
<https://nces.ed.gov/programs/digest/d24/tables/dt24_330.10.asp>
*Underlying collection instruments:* Higher Education General Information Survey (HEGIS)
and the Integrated Postsecondary Education Data System (IPEDS).
*Supports:* `data/raw/nces_tuition_public4yr.csv`, retained as a separate reference;
not appended to the College Board line in the current chart.

### United States — annual Consumer Price Index (common tuition deflator)
**U.S. Bureau of Labor Statistics (BLS), U.S. Department of Labor.** Consumer Price Index
(CPI-U), U.S. city average, all items, not seasonally adjusted, series
`CUUR0000SA0`, 1982–84 = 100. Retrieved 14 October 2026.
<https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0>
*Supports:* saved annual `M13` observations for 1963–2025 in
`data/raw/bls_us_cpi_annual.csv`; the shared deflator for the snapshot,
market-rate history and PPP tuition history. Ratios use calendar-year 2022 as
base. No monthly observations, partial-year 2026 averages or December substitutes.

For 2025, the API flags October (`M10`) as unavailable due to the lapse in
appropriations. The published annual average (`M13`, **321.943**) equals the
average of the **11 available monthly indexes**. The pipeline uses that published
annual value without imputing October. NCES's separate academic-year
constant-dollar column is retained as a reference only, not used in the
calendar-year comparison.

### United States — tuition, full history and 2025/26 snapshot
**College Board.** (2025). *Trends in College Pricing 2025*, Tables CP-1 and CP-2.
CP-1:
“Average Published Prices (Enrollment-Weighted) for Full-Time Undergraduates,
2024-25 and 2025-26.” Retrieved 14 October 2026.
<https://research.collegeboard.org/media/xlsx/Trends-in_College-Pricing-2025-excel-data.xlsx>
*Supports:* the US snapshot ($11,950 public four-year in-state; $45,000 private
nonprofit reference) in `data/raw/manual_tuition.csv`. College Board publishes
this table. **CP-2**, “Average Published Tuition and Fees and Housing and Food
in Current Dollars and in 2025 Dollars,” supplies the **entire nominal
public four-year in-state tuition-and-fees history, 1971/72–2025/26**, saved in
`data/raw/collegeboard_tuition_public4yr.csv`. Housing/food and publisher
constant-dollar columns are excluded. The chart uses this whole series,
not NCES with College Board endpoints added.

CP-2 notes a source/weighting change: through 1986/87, NCES/IPEDS and
full-time-equivalent weights; from 1987/88, College Board Annual Survey of
Colleges and full-time undergraduate weights. The historical chart breaks
the line at 1987 without removing either observation. The workbook's nominal
section and headers, rather than its stale introductory constant-dollar title,
identify the input.

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

### Exchange rates
**The World Bank Group.** (2024). *World Development Indicators.* Washington, DC: The World
Bank. Retrieved via the World Bank API on 14 October 2026.
- Official exchange rate (LCU per US$, period average) — indicator `PA.NUS.FCRF`: <https://data.worldbank.org/indicator/PA.NUS.FCRF>

*Original data compiler:* **International Monetary Fund (IMF),
*International Financial Statistics*** (and national statistical offices), redistributed by
the World Bank.
*Supports:* market-FX currency conversion of tuition history and snapshots.
History requires exact-year FX; nominal snapshots record any nearby-year FX.
The common inflation adjustment is now sourced directly from BLS, above.

### European Union — nationally sourced fee updates
Retrieved **14 October 2026**. These are published fee schedules or clearly
specified annual equivalents, not harmonized national student averages.

| Entry | Publisher and source | Definition |
|---|---|---|
| France 2026/27 | **Service Public / DILA**, <https://www.service-public.gouv.fr/particuliers/vosdroits/F2865> | Annual licence registration €178; excludes €105 CVEC; scholarship exemptions |
| Ireland 2026/27 | **Irish Statute Book**, *Student Grant Scheme 2026*, S.I. 70/2026, Schedule 4, <https://www.irishstatutebook.ie/eli/2026/si/70/made/en/> | Full student contribution €2,500 before means-tested grants; Free Fees Initiative eligibility; institutional levies excluded |
| Luxembourg 2026/27 | **Ministry of Research and Higher Education**, MengStudien, <https://mengstudien.public.lu/de/actualites/2026/fevrier/uni-lu-registrations.html> | Most University of Luxembourg programmes €400/semester × 2 = €800/year; one-off €100 application fee excluded |
| Netherlands 2026/27 | **Dienst Uitvoering Onderwijs (DUO)**, <https://duo.nl/particulier/tuition-fees.jsp> | Eligible full-time statutory annual fee €2,694, not institutional fees |
| Portugal 2025/26 | **Direção-Geral do Ensino Superior (DGES)**, <https://www.dges.gov.pt/pt/pagina/propinas> | Public first-cycle annual maximum €697 |
| Spain 2024/25 | **Ministry of Science, Innovation and Universities**, *Estadística de Precios Públicos Universitarios*, <https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Precios.html> | €15.37 arithmetic mean first-enrolment credit price × standardized 60 credits = €922.20/year; not enrollment-weighted; repeat credits and administration excluded |

---

## Secondary sources (published summaries of primary reports)

### European Union (EU-27) — domestic tuition fees, 2023/24 snapshot
**European Commission / European Education and Culture Executive Agency (EACEA) /
Eurydice.** (2025). *National Student Fee and Support Systems in European Higher Education —
2023/24* (Eurydice – Facts and Figures). Luxembourg: Publications Office of the European
Union. DOI: **10.2797/2086726**; released 7 March 2025.
<https://op.europa.eu/en/publication-detail/-/publication/ad722572-ffbf-11ef-9503-01aa75ed71a1/language-en>
*Supports:* the 21 still-dated 2023/24 summary entries in
`data/raw/manual_tuition.csv`; Bulgaria remains flagged `APPROXIMATE`.
This citation identifies the underlying primary publication, not an assertion
that every retained secondary-summary value has been reverified.

### Germany — tuition fee history
**Study.eu** (secondary web reference), *The History of Tuition Fees in Germany*.
<https://www.study.eu/article/the-history-of-tuition-fees-in-germany> — corroborated by the
Eurydice report above.
*Supports:* Germany line in `tuition_history_real_usd.png`.

---

*Note on provenance:* the historical US/England series uses the **primary sources**
above (College Board, BLS, UK legislation/Hansard, World Bank/IMF). Germany's sparse zero-fee reference
points use secondary sources and do not imply uninterrupted fee-free education.
The EU-27 cross-sectional
snapshot combines the dated **Eurydice** summary with six national updates; the current US snapshot is taken
directly from College Board Table CP-1.
