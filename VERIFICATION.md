# Verification — 2026-09-06

- Python 3.12.14, Pydantic 2.13.5: **45 tests passed**. Python 3.11 is the compatibility target, not a separately executed interpreter in this environment.
- 12 generated bundles validate; 30 labeled cases run through the actual pipeline. Unsupported and adversarial abstention: 12/12; explicit contradiction detection: 6/6; unsafe supporting-evidence omissions: 0/72 displayed findings. Exact citation checks pass.
- Independent review found and tests now cover target-scoped negation, family-history exclusions, provisional mentions after rule-out, and mismatches between structured facts and cited source text/dates.
- Website TypeScript check, production static export, and standalone offline build passed.
- Business-model arithmetic and invalid inputs were checked with Node: default gross scenario $6,104,847.672; zero-valued factors produce zero benefit; malformed/out-of-range inputs are rejected.
- Initial local route responded HTTP 200. No automated browser interactions, screenshots, mobile viewport run, accessibility audit, or sub-2-second performance measurement was performed.
- The optional WebMCP scenario tool uses the same state setter and arithmetic as the page. Input validation was tested. No supported WebMCP browser context was available, so registration and browser state transitions remain unverified.
- Optional live LLM and cached semantic-retrieval integrations were not exercised against a provider/model. Mocked provider failures, malformed outputs and evidence tampering are tested.
- GitHub Pages migration uses a plain Vite static build with `/day-one/` as its asset base. Vinext, React Server Components, and Cloudflare hosting dependencies were removed from this release. The original offline backup is retained byte-for-byte.
- All confidence values are uncalibrated heuristic record-status scores. This is a constructed regression harness, not clinical validation.
