# Day One source verification

Verified 2026-09-06. Primary sources only. These notes verify context; the prototype does not establish a financial or clinical effect.

## Business claims

- **~$70 PMPM: supported as management's description, not a measured effect of this prototype.** Andrew Toy described typical year-one to year-two cohort gross-profit improvement on August 5, 2026 (transcript p. 3). The same discussion links maturation to understanding conditions, physician action, and care over time. [Q2 2026 earnings-call transcript](https://investors.cloverhealth.com/static-files/8940df35-b935-4f1d-b6e6-d931c1b7f885).
- **157,309: supported for June 30, 2026 membership.** This is quarter-end insurance membership, not the quarterly average, which was 156,840. Published August 5, 2026. [Q2 2026 earnings release, SEC exhibit](https://www.sec.gov/Archives/edgar/data/1801170/000180117026000196/a2q26exx991xearningsrelease.htm).
- **AI in plan operations: supported as management's stated direction.** On August 5, Toy discussed expanding AI into back-office insurance functions, member support, claims processing, and administrative efficiency (transcript pp. 7–8). It does not establish a commitment to this intake workflow. [Q2 2026 earnings-call transcript](https://investors.cloverhealth.com/static-files/8940df35-b935-4f1d-b6e6-d931c1b7f885).
- **Clover live on Kno2 in March 2026: supported with narrower scope.** Use the **updated March 10 release**, which corrected a March 4 release. Clover responds to patient-directed requests for clinical and claims data; Kno2 routes the requests and Counterpart powers standardized exchange. This does not establish comprehensive inbound record retrieval at enrollment, complete coverage, or this prototype's integration. [Updated Clover announcement](https://investors.cloverhealth.com/news-releases/news-release-details/updated-moving-pledge-production-clover-health-now-live-kno2/).
- **CMS pledgee: supported.** CMS lists Clover Health under payer pledgees committing to participate in a CMS Aligned Network; page updated September 1, 2026. This is a pledge listing, not a certification of universal exchange coverage. [CMS payer pledgees](https://www.cms.gov/initiatives/health-technology-ecosystem/overview/early-adopters-all-pledgees/payers-their-delegated-technology).
- **The gap is mostly information: unsupported.** Clover's August 20 Q&A describes earlier identification, intervention, and care management working together. The source does not quantify an information-only component. [Q2 2026 supplemental Q&A, p. 2](https://investors.cloverhealth.com/static-files/b260bff9-9b29-4250-bf15-24aecfabceb7).

## Suggested site wording

Hero: **Bring a better record to the first visit.**

Supporting line: An independent synthetic prototype exploring whether earlier information could help clinicians coordinate care sooner.

Observation: Clover management described roughly $70 PMPM of typical gross-profit improvement between a cohort's first and second years. How much of that improvement could earlier information bring forward? Public disclosures do not answer that question.

Interoperability: Clover announced patient-directed clinical and claims exchange through Kno2 in March 2026 and appears on CMS's payer pledge list. These are relevant infrastructure developments; record availability and enrollment-time access still need to be established.

Model: **Illustrative annualized gross opportunity, before implementation costs.** The 28% first-year share, 33% information-driven share, and 50% acceleration share are author assumptions. The $70 and membership inputs are public reference points. None are Clover projections of this proposed workflow. Allow zero for assumed information and acceleration shares so the model can represent no benefit.

Default arithmetic: 157,309 × 28% × $70 × 12 = $36,999,076.80 modeled annual cohort gap; ×33% = $12,209,695.34 assumed information component; ×50% = $6,104,847.67 assumed annualized gross opportunity. This is scenario arithmetic, not estimated realized savings. A full model would need retention, implementation cost, coverage, uptake, and evidence of causal effect.

## Clinical knowledge snippets — paraphrased

1. **CKD chronicity.** KDIGO 2024, practice points 1.1.3.1–1.1.3.2: establish chronicity over at least three months using longitudinal measurements or other relevant evidence; a single abnormal eGFR or ACR may reflect acute illness. Demo implication: a one-off reduced eGFR is insufficient for a chronic CKD claim; cite the value as an observation and request longitudinal context. [KDIGO 2024 CKD guideline](https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf). Version: 2024; [KDIGO identifies it as current](https://kdigo.org/guidelines/ckd-evaluation-and-management/).

2. **Diabetes monitoring.** NIDDK recommends A1C testing at least twice yearly in people with diabetes, and potentially more frequently when treatment goals are not met. Demo implication: report **No A1C result found in the supplied record in the past 12 months; confirm outside testing and follow-up needs**, rather than declaring care was missed. Twelve months is a conservative demo record-gap trigger, not a complete clinical monitoring schedule. [NIDDK, The A1C Test & Diabetes](https://www.niddk.nih.gov/health-information/diagnostic-tests/a1c-test). Accessed 2026-09-06.

3. **Ambiguous diabetes evidence.** NIDDK's clinician reference describes confirmatory abnormal testing and repeating the above-threshold test when two different tests conflict. Demo implication: a single elevated A1C without confirming context should prompt review of the laboratory evidence, not an autonomous type 2 diabetes diagnosis. Do not infer a diabetes type solely from a laboratory result. [NIDDK, Diabetes & Prediabetes Tests](https://www.niddk.nih.gov/health-information/professionals/clinical-tools-patient-management/diabetes/diabetes-prediabetes). Last reviewed August 2020; accessed 2026-09-06.

Implementation interpretation: patient source documents establish what is present in the synthetic record; clinical references provide general context. A guideline snippet must not masquerade as patient evidence. A missing record is an unknown, and an old medication or nonspecific lab is not enough to establish a current diagnosis. All proposed actions remain clinician review requests.
