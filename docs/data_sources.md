# Data sources

> Generated from `data/facts/*.yaml` on 2026-10-04 by
> `scripts/generate_data_sources.py`. Every fact Ruko can display, its primary
> source, our check notes and its verification status. In production
> (`show_unverified_facts: false`) a fact is shown only after a person on the team
> has checked it against its source and set `verified_by_human: true`.

## Group statistics (`data/facts/base_rates.yaml`)

| Fact ID | Value | Year | as_of | Source | Verified | Check note | TODO |
|---|---|---|---|---|---|---|---|
| `base_rates:eds_fy26_loss_makers_all` | 87.7 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | Quote checked verbatim against the SEBI PDF on 2026-10-04. |  |
| `base_rates:eds_fy26_loss_makers_age_lt_30` | 88.55 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | 2026-10-04: sentence checked verbatim on p. 68 and the value in the age-wise table on p. 69 of the SEBI PDF; the executive summary (p. 6) rounds it to 89%. |  |
| `base_rates:eds_fy26_loss_makers_age_30_40` | 88.05 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | Value checked in the age-wise table on p. 69 of the SEBI PDF on 2026-10-04 (the table label 'Table 26' itself was not located in the extracted text). |  |
| `base_rates:eds_fy26_loss_makers_age_40_50` | 87.8 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | Value checked in the age-wise table on p. 69 of the SEBI PDF on 2026-10-04 (the table label 'Table 26' itself was not located in the extracted text). |  |
| `base_rates:eds_fy26_loss_makers_age_50_60` | 85.29 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | Value checked in the age-wise table on p. 69 of the SEBI PDF on 2026-10-04 (the table label 'Table 26' itself was not located in the extracted text). |  |
| `base_rates:eds_fy26_loss_makers_age_gt_60` | 80.95 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | Value checked in the age-wise table on p. 69 of the SEBI PDF on 2026-10-04 (the table label 'Table 26' itself was not located in the extracted text). |  |
| `base_rates:eds_fy26_cost_share_of_losses` | 35 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | yes | Sentence checked verbatim on p. 66 of the SEBI PDF on 2026-10-04. |  |
| `base_rates:intraday_fy23_loss_makers_all` | 71 | FY23 | 2023-03-31 | [SEBI Study: Analysis of Intraday Trading by Individuals in Equity Cash Segment](https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html) | yes | Quote checked verbatim against the SEBI PDF on 2026-10-04. |  |
| `base_rates:intraday_fy23_loss_makers_age_lt_30` | 76 | FY23 | 2023-03-31 | [SEBI Study: Analysis of Intraday Trading by Individuals in Equity Cash Segment](https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html) | yes | Quote checked verbatim against the SEBI PDF on 2026-10-04. |  |
| `base_rates:intraday_fy23_costs_added_to_losses` | 57 | FY23 | 2023-03-31 | [SEBI Study: Analysis of Intraday Trading by Individuals in Equity Cash Segment](https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html) | yes | Quote checked verbatim against the SEBI PDF on 2026-10-04. |  |

Each statistic is shown only as a group statistic with SEBI's non-causal caveat (or
Ruko's generic "group, not a prediction" caveat where the study has none).

## Regulatory facts (`data/facts/regulatory.yaml`)

| Fact ID | as_of | Source | Verified | Check note | TODO |
|---|---|---|---|---|---|
| `regulatory:upi_validated_handles` | 2025-06-11 | [SEBI circular SEBI/HO/DEPA-II/DEPA-II_SRG/P/CIR/2025/86: Adoption of Standardised, Validated and Exclusive UPI IDs for Payment Collection by SEBI Registered Intermediaries from Investors](https://www.sebi.gov.in/legal/circulars/jun-2025/adoption-of-standardised-validated-and-exclusive-upi-ids-for-payment-collection-by-sebi-registered-intermediaries-from-investors_94535.html) | yes | 2026-10-04: circular number and date confirmed on sebi.gov.in. Format (@valid<bank>, e.g. abc.brk@validhdfc, xyz.mf@validicici), the green-triangle thumbs-up, the 1 Oct 2025 start and "investors can continue using NEFT, RTGS, IMPS, or cheques" confirmed only via secondary sources (Business Today 11 Jun 2025; Motilal Oswal MF). The ten category suffixes, the format, the icon, "investors can choose their preferred mode of payment, such as UPI, IMPS, NEFT, RTGS, or Cheques" and "available ... w.e.f. October 01, 2025" were checked against a full-text reproduction of the circular (lexibox.in) on 2026-10-04; all ten suffixes match this file. |  |
| `regulatory:sebi_check_upi` | 2026-10-03 | [SEBI investor website: UPI ID Verification (SEBI Check)](https://investor.sebi.gov.in/upi-verification.html) | yes |  |  |
| `regulatory:registration_lookup` | 2026-10-03 | [SEBI: Recognised Intermediaries](https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes) | yes |  |  |
| `regulatory:official_domains` | 2026-10-03 | [Official websites of the listed institutions](https://www.sebi.gov.in) | yes |  |  |
| `regulatory:capital_gains_listed_equity` | 2024-07-23 | [Income Tax Department: Tax on short-term / long-term capital gains; CBDT FAQs on the new capital gains regime (Union Budget 2024-25)](https://www.incometaxindia.gov.in/w/tax-on-long-term-capital-gains%E2%80%8B) | no | 2026-10-04: Income-tax Act, 2025, section 196 ("Tax on short-term capital gains in certain cases") on incometaxindia.gov.in gives 20% for STT-paid listed equity, equity-oriented fund and business trust units. Also confirmed on incometaxindia.gov.in pages "Tax on short-term capital gains" ("STCG covered under section 111A is charged to tax at the rate of 20%" from 23-07-2024) and "Tax on long-term capital gains" (12.5% above Rs 1,25,000; 12-month holding for listed shares). Those pages describe the Income-tax Act, 1961 "as amended by the Finance Act, 2026". | TODO_VERIFY |
| `regulatory:derivatives_loss_can_exceed_margin` | 2026-10-04 | [SEBI: Annexure 4, Combined Risk Disclosure Document for Capital Market/Cash Segment and Futures & Options Segment](https://www.sebi.gov.in/sebi_data/commondocs/ann4_p.pdf) | yes | Quote checked verbatim against the PDF on 2026-10-04. The document carries no version date; as_of is the check date. |  |
| `regulatory:ia_no_assured_returns` | 2026-10-04 | [SEBI investor website: Securities Market Investment: Understanding Investment Advisors (code of conduct)](https://investor.sebi.gov.in/investment_advisor.html) | yes | Quote checked on the live SEBI page on 2026-10-04. Supporting detail (not shown to users): SEBI circular SEBI/HO/IMD/DF1/CIR/P/2020/182 (23 Sep 2020), Annexure A para 2(b), says advisers "shall not ... hold out any investment advice implying any assured returns or minimum returns or target return or percentage accuracy" (checked via a reproduction at lexibox.in). Scope: this rule is about investment advisers, so cards must not extend it to every registered entity. |  |
| `regulatory:sebi_investor_website` | 2026-10-03 | [SEBI Investor Website](https://investor.sebi.gov.in) | no | 2026-10-04: site confirmed live. It has no stable per-term pages for most glossary terms (its glossary page renders no entries without interaction). Topic pages that do exist and could be linked: IPO via ASBA (https://investor.sebi.gov.in/ipo_through_asba.html), Nomination (https://investor.sebi.gov.in/market-nomination.html), scam guides (beware-fake-trading-app-scam, stock-market-guru-scams, spot-any-scam), and SEBI's own calculators (calculators/index.html). | TODO_VERIFY |

## SEBI investor pages (`data/facts/investor_pages.yaml`)

Linked from glossary entries (IPO, nomination).

| Fact ID | as_of | Source | Verified | TODO |
|---|---|---|---|---|
| `investor_pages:ipo_through_asba` | 2026-10-04 | [SEBI Investor Website: IPO through ASBA](https://investor.sebi.gov.in/ipo_through_asba.html) | yes |  |
| `investor_pages:market_nomination` | 2026-10-04 | [SEBI Investor Website: Nomination](https://investor.sebi.gov.in/market-nomination.html) | yes |  |
| `investor_pages:fake_trading_app_scam` | 2026-10-04 | [SEBI Investor Website: Beware of Fake Trading App scam](https://investor.sebi.gov.in/beware-fake-trading-app-scam.html) | yes |  |
| `investor_pages:stock_market_guru_scams` | 2026-10-04 | [SEBI Investor Website: "Stock Market Guru" Scams](https://investor.sebi.gov.in/stock-market-guru-scams.html) | yes |  |
| `investor_pages:spot_any_scam` | 2026-10-04 | [SEBI Investor Website: How to Spot a Scam](https://investor.sebi.gov.in/spot-any-scam.html) | yes |  |
| `investor_pages:sebi_calculators` | 2026-10-04 | [SEBI Investor Website: Calculators](https://investor.sebi.gov.in/calculators/index.html) | yes |  |

## Recovery routes (`data/facts/recovery_routes.yaml`)

| Fact ID | Contact | as_of | Source | Verified | Check note | TODO |
|---|---|---|---|---|---|---|
| `recovery_routes:helpline_1930` | 1930 | 2025-03-12 | [PIB, Ministry of Home Affairs, 12 Mar 2025: Cyber Crime Reporting Systems](https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2110801) | yes | Quotes checked against the PIB release on 2026-10-04; confirmed by the team. |  |
| `recovery_routes:cybercrime_portal` | https://cybercrime.gov.in | 2026-10-03 | [National Cyber Crime Reporting Portal, Indian Cybercrime Coordination Centre, MHA](https://cybercrime.gov.in) | yes |  |  |
| `recovery_routes:bank` | (differs per bank / broker) | 2017-07-06 | [RBI circular RBI/2017-18/15 DBR.No.Leg.BC.78/09.07.005/2017-18 (6 Jul 2017): Customer Protection - Limiting Liability of Customers in Unauthorised Electronic Banking Transactions](https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id=11040) | yes | Circular reference and date checked on 2026-10-04. CAUTION: the circular's zero / limited liability rules cover UNAUTHORISED transactions (for example reported within three working days). A payment the user made themselves to a scammer is usually not "unauthorised". Ruko must never promise a refund or zero liability; it only says to contact the bank fast. |  |
| `recovery_routes:broker_grievance` | (differs per bank / broker) | 2026-10-03 | [SEBI SCORES: investors shall first take up grievances with the entity concerned](https://scores.sebi.gov.in) | yes |  |  |
| `recovery_routes:sebi_scores` | https://scores.sebi.gov.in | 2026-10-03 | [SEBI Complaint Redressal System (SCORES)](https://scores.sebi.gov.in) | yes |  |  |
| `recovery_routes:smart_odr` | https://smartodr.in | 2026-10-03 | [SEBI SCORES page linking the SMART ODR Portal](https://scores.sebi.gov.in) | yes |  |  |

## Open TODO_VERIFY items

- `regulatory:capital_gains_listed_equity`: TODO_VERIFY: the long-term rate (12.5% above Rs 1,25,000) is confirmed on the Income Tax Department's 1961-Act page and by secondary sources for the 2025 Act, but its 2025-Act section was not opened. Ruko states no section numbers and gives no personal tax computation.
- `regulatory:sebi_investor_website`: TODO_VERIFY: the glossary definitions in data/templates/*.yaml are Ruko's own wording and still need a human read; they are not quotes from SEBI.

## Not yet used

- `data/facts/charges.yaml`: statutory trading charges for the cost calculator. Every
  value is TODO_VERIFY and the file is disabled; the calculator uses only the user's own
  or clearly hypothetical cost assumptions until it is filled from primary sources.

## Other content that needs human review

- Every Hindi and Kannada template (`data/templates/hi.yaml`, `kn.yaml`), lexicon
  (`data/lexicon/`), stage pattern (`data/stages/`) and number-word file
  (`data/language/`) is a draft for native-speaker review.
- Glossary definitions (`glossary.*` templates) are Ruko's own wording, not SEBI quotes.
  IPO and nomination link to SEBI topic pages; the other terms cite the investor website
  home page (it has no stable per-term pages).
- Policy numbers in `data/policy/intervention.yaml` and the example rates in
  `data/policy/calculators.yaml` are proposals (see `docs/open_questions.md`).
