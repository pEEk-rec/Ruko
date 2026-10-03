# Data sources

> Generated from `data/facts/*.yaml` on 2026-10-03. Every fact Ruko can display, its primary
> source and its verification status. **Nothing is verified by a human yet**: in production
> (`show_unverified_facts: false`) none of these are shown until the owner verifies them.

## Group statistics (`data/facts/base_rates.yaml`)

| Fact ID | Value | Year | as_of | Source | Verified | TODO |
|---|---|---|---|---|---|---|
| `base_rates:eds_fy26_loss_makers_all` | 87.7 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:eds_fy26_loss_makers_age_lt_30` | 88.55 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:eds_fy26_loss_makers_age_30_40` | 88.05 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:eds_fy26_loss_makers_age_40_50` | 87.8 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:eds_fy26_loss_makers_age_50_60` | 85.29 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:eds_fy26_loss_makers_age_gt_60` | 80.95 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:eds_fy26_cost_share_of_losses` | 35 | FY26 | 2026-03-31 | [SEBI Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html) | no | |
| `base_rates:intraday_fy23_loss_makers_all` | 71 | FY23 | 2023-03-31 | [SEBI Study: Analysis of Intraday Trading by Individuals in Equity Cash Segment](https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html) | no | |
| `base_rates:intraday_fy23_loss_makers_age_lt_30` | 76 | FY23 | 2023-03-31 | [SEBI Study: Analysis of Intraday Trading by Individuals in Equity Cash Segment](https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html) | no | |
| `base_rates:intraday_fy23_costs_added_to_losses` | 57 | FY23 | 2023-03-31 | [SEBI Study: Analysis of Intraday Trading by Individuals in Equity Cash Segment](https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html) | no | |

Each statistic is shown only as a group statistic with SEBI's non-causal caveat (or Ruko's
generic "group, not a prediction" caveat where the study has none).

## Regulatory facts (`data/facts/regulatory.yaml`)

| Fact ID | as_of | Source | Verified | TODO |
|---|---|---|---|---|
| `regulatory:upi_validated_handles` | 2025-06-11 | [SEBI circular SEBI/HO/DEPA-II/DEPA-II_SRG/P/CIR/2025/86: Adoption of Standardised, Validated and Exclusive UPI IDs for Payment Collection by SEBI Registered Intermediaries from Investors](https://www.sebi.gov.in/legal/circulars/jun-2025/adoption-of-standardised-validated-and-exclusive-upi-ids-for-payment-collection-by-sebi-registered-intermediaries-from-investors_94535.html) | no |  |
| `regulatory:sebi_check_upi` | 2026-10-03 | [SEBI investor website: UPI ID Verification (SEBI Check)](https://investor.sebi.gov.in/upi-verification.html) | no |  |
| `regulatory:registration_lookup` | 2026-10-03 | [SEBI: Recognised Intermediaries](https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes) | no |  |
| `regulatory:official_domains` | 2026-10-03 | [Official websites of the listed institutions (to be confirmed by the repo owner)](https://www.sebi.gov.in) | no |  |
| `regulatory:capital_gains_listed_equity` | 2024-07-23 | [Income Tax Department: Tax on short-term / long-term capital gains; CBDT FAQs on the new capital gains regime (Union Budget 2024-25)](https://www.incometaxindia.gov.in/w/tax-on-long-term-capital-gains%E2%80%8B) | no | TODO_VERIFY |
| `regulatory:derivatives_loss_can_exceed_margin` | 2026-10-03 | [SEBI: Combined Risk Disclosure Document for Capital Market/Cash and Derivatives Segments (Annexure 4)](https://www.sebi.gov.in/sebi_data/commondocs/ann4_p.pdf) | no | TODO_VERIFY |
| `regulatory:ia_no_assured_returns` | 2026-10-03 | [SEBI (Investment Advisers) Regulations, 2013 (as amended); SEBI investor page: Understanding Investment Advisors](https://investor.sebi.gov.in/investment_advisor.html) | no | TODO_VERIFY |
| `regulatory:sebi_investor_website` | 2026-10-03 | [SEBI Investor Website](https://investor.sebi.gov.in) | no | TODO_VERIFY |

## Recovery routes (`data/facts/recovery_routes.yaml`)

| Fact ID | Contact | as_of | Source | Verified | TODO |
|---|---|---|---|---|---|
| `recovery_routes:helpline_1930` | 1930 | 2026-10-03 | [Indian Cybercrime Coordination Centre (I4C), MHA: National Cybercrime Reporting Portal and Citizen Financial Cyber Fraud Reporting and Management System](https://i4c.mha.gov.in/ncrp.aspx) | no | TODO_VERIFY |
| `recovery_routes:cybercrime_portal` | https://cybercrime.gov.in | 2026-10-03 | [National Cyber Crime Reporting Portal, Indian Cybercrime Coordination Centre, MHA](https://cybercrime.gov.in) | no |  |
| `recovery_routes:bank` | (differs per bank / broker) | 2026-10-03 | [Reserve Bank of India: customer protection in unauthorised electronic banking transactions](https://www.rbi.org.in) | no | TODO_VERIFY |
| `recovery_routes:broker_grievance` | (differs per bank / broker) | 2026-10-03 | [SEBI SCORES: investors shall first take up grievances with the entity concerned](https://scores.sebi.gov.in) | no |  |
| `recovery_routes:sebi_scores` | https://scores.sebi.gov.in | 2026-10-03 | [SEBI Complaint Redressal System (SCORES)](https://scores.sebi.gov.in) | no |  |
| `recovery_routes:smart_odr` | https://smartodr.in | 2026-10-03 | [SEBI SCORES page linking the SMART ODR Portal](https://scores.sebi.gov.in) | no |  |

## Other content that needs human review

- Every Hindi and Kannada template (`data/templates/hi.yaml`, `kn.yaml`), lexicon
  (`data/lexicon/`), stage pattern (`data/stages/`) and number-word file (`data/language/`) is
  a draft for native-speaker review.
- Glossary definitions (`glossary.*` templates) are general explanations written for Ruko and
  cite only the SEBI investor website home page (TODO_VERIFY: link each term's page).
- Policy numbers in `data/policy/intervention.yaml` are proposals (see `docs/open_questions.md`).
