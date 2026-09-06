"""Generate 12 invented FHIR-ish fixtures; no external patient data is used."""

import json
from pathlib import Path

from .schemas import SyntheticBundle

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = {
    "ckd": ("Chronic kidney disease", "N18.9"),
    "chf": ("Heart failure", "I50.9"),
    "copd": ("COPD", "J44.9"),
    "diabetes": ("Type 2 diabetes", "E11.9"),
    "af": ("Atrial fibrillation", "I48.91"),
    "depression": ("Depression", "F32.A"),
}
LABS = {
    "ckd": ("eGFR", "33914-3", 44, "mL/min/1.73m2", 60, None),
    "diabetes": ("Hemoglobin A1c", "4548-4", 7.4, "%", 4.0, 5.6),
    "chf": ("BNP", "30934-4", 310, "pg/mL", 0, 100),
}
SUPPORT = {
    "ckd": "Nephrology clinician documents chronic kidney disease; eGFR 44 and 46 on measurements five months apart, with longitudinal assessment. External history awaits reconciliation at the first visit.",
    "diabetes": "Endocrinology clinician documents type 2 diabetes after repeated testing and clinical assessment. External history awaits reconciliation at the first visit.",
    "chf": "Cardiology clinician documents heart failure after clinical assessment and echocardiogram review. External history awaits reconciliation at the first visit.",
    "copd": "Pulmonary clinician documents COPD after reviewing symptoms, exposure history and post-bronchodilator spirometry. External history awaits reconciliation at the first visit.",
    "af": "Cardiology clinician documents atrial fibrillation after 12-lead ECG review. External history awaits reconciliation at the first visit.",
    "depression": "Behavioral-health clinician documents depression after clinical interview and longitudinal assessment. External history awaits reconciliation at the first visit.",
}
NEGATION = {
    "ckd": "Follow-up clinician review: chronic kidney disease ruled out; earlier low eGFR was transient during dehydration and has normalised on repeat testing. Do not carry the historical suggestion forward.",
    "diabetes": "Follow-up clinician review: type 2 diabetes ruled out on repeat testing; earlier hyperglycemia was transient during steroid treatment and resolved. Do not carry the historical suggestion forward.",
    "chf": "Follow-up cardiology review: heart failure ruled out following echocardiogram and clinical review; earlier BNP elevation was transient. Do not carry the historical suggestion forward.",
    "copd": "Follow-up pulmonary review: COPD ruled out after symptom and spirometry review; earlier respiratory symptoms resolved. Do not carry the historical suggestion forward.",
    "af": "Follow-up cardiology review: atrial fibrillation ruled out after tracing review; the earlier rhythm report was artifact. Do not carry the historical suggestion forward.",
    "depression": "Follow-up behavioral-health review: no evidence of current depression after clinical reassessment; earlier provisional impression was situational and resolved. Do not carry the historical suggestion forward.",
}


def make_bundle(index: int, scenario: str, keys: list[str]) -> SyntheticBundle:
    member = f"SYN-{index:03d}"
    raw = {
        "resourceType": "Bundle", "type": "collection", "member_id": member,
        "meta": {"label": "SYNTHETIC", "scenario": scenario},
        "demographics": {"age_band": ["65–69", "70–74", "75–79", "80–84"][(index-1) % 4], "sex": "female" if index % 2 else "male"},
        "coded_conditions": [], "medications": [], "encounters": [], "observations": [], "source_documents": [],
    }

    def doc(suffix, kind, day, excerpt):
        doc_id = f"{member}-{suffix}"
        raw["source_documents"].append({"doc_id": doc_id, "doc_type": kind, "date": day, "excerpt": "SYNTHETIC. " + excerpt})
        return doc_id

    def encounter(doc_id, day, kind="external specialist review"):
        raw["encounters"].append({"encounter_id": f"E-{doc_id}", "date": day, "encounter_type": kind, "source_doc_id": doc_id})

    intake = doc("intake", "encounter_note", "2026-08-25", "New-member intake. Outside records are partial; allergies, vaccination history, preventive screening history and member priorities still need reconciliation.")
    encounter(intake, "2026-08-25", "intake")
    if scenario == "sparse":
        # One sparse member has an incidental medication mention, insufficient to infer an indication.
        if index == 5:
            raw["source_documents"][0]["excerpt"] += " Member reports gabapentin for an uncertain indication; no disease assessment or verified medication list is available."
        if index == 6:
            raw["source_documents"][0]["excerpt"] += " Member reports fatigue and occasional ankle swelling; no specialist assessment or confirmatory tests are available."
        return SyntheticBundle.model_validate(raw)

    support_date = "2021-05-12" if scenario == "stale" else "2026-02-12"
    for key in keys:
        name, code = CONDITIONS[key]
        # Contradictory fixtures carry a provisional record impression, never a new diagnosis.
        excerpt = SUPPORT[key] if scenario in {"rich", "already_documented"} else f"Historical outside note records a provisional concern for {name.lower()}; current status was not established."
        source = doc(f"{key}-history", "encounter_note", support_date, excerpt)
        encounter(source, support_date)
        if key in LABS:
            lab_name, loinc, value, unit, low, high = LABS[key]
            lab_day = support_date
            lab_doc = doc(f"{key}-lab", "lab_result", lab_day, f"{lab_name}: {value} {unit}; LOINC {loinc}. This isolated result cannot establish {name.lower()}.")
            raw["observations"].append({"observation_id": f"O-{lab_doc}", "name": lab_name, "loinc": loinc, "value": value, "unit": unit, "date": lab_day, "reference_low": low, "reference_high": high, "condition_key": key, "source_doc_id": lab_doc})
            if key == "ckd" and scenario in {"rich", "already_documented"}:
                earlier = doc("ckd-earlier-lab", "lab_result", "2025-09-10", "eGFR: 46 mL/min/1.73m2; LOINC 33914-3. Result requires longitudinal clinical interpretation.")
                raw["observations"].append({"observation_id": f"O-{earlier}", "name": "eGFR", "loinc": "33914-3", "value": 46, "unit": "mL/min/1.73m2", "date": "2025-09-10", "reference_low": 60, "reference_high": None, "condition_key": key, "source_doc_id": earlier})
        if scenario in {"contradictory", "stale"}:
            resolved = doc(f"{key}-review", "encounter_note", "2026-07-21", NEGATION[key])
            encounter(resolved, "2026-07-21")
            if key in {"ckd", "diabetes"}:
                lab_name, loinc, _, unit, low, high = LABS[key]
                value = 82 if key == "ckd" else 5.4
                latest = doc(f"{key}-repeat", "lab_result", "2026-07-20", f"{lab_name}: {value} {unit}; LOINC {loinc}. Result reviewed in the subsequent clinician note.")
                raw["observations"].append({"observation_id": f"O-{latest}", "name": lab_name, "loinc": loinc, "value": value, "unit": unit, "date": "2026-07-20", "reference_low": low, "reference_high": high, "condition_key": key, "source_doc_id": latest})
        if scenario == "already_documented":
            coded = doc(f"{key}-chart", "claim", "2026-08-04", f"Current chart already lists {name.lower()} ({code}); retain the documented history for clinician review, without a duplicate suggestion.")
            raw["coded_conditions"].append({"condition_key": key, "code": code, "display": name, "date": "2026-08-04", "source_doc_id": coded})

    meds = {1: ["metformin", "furosemide"], 2: ["tiotropium", "apixaban", "sertraline"], 3: ["metformin"], 7: ["acetaminophen"], 8: ["albuterol"], 9: ["acetaminophen"], 10: ["acetaminophen"], 11: ["metformin"], 12: ["tiotropium", "apixaban", "sertraline"]}[index]
    med_day = "2025-01-15" if index == 10 else "2026-08-10"
    med_source = doc("medications", "med_list", med_day, "External medication list, active as recorded: " + ", ".join(meds) + ". Indications, doses and current use need clinician reconciliation; a medication alone does not establish a condition.")
    for med in meds:
        raw["medications"].append({"name": med, "status": "active", "date": med_day, "source_doc_id": med_source})
    return SyntheticBundle.model_validate(raw)


def generate(output: Path | None = None) -> list[SyntheticBundle]:
    output = output or ROOT / "data/synthetic"
    output.mkdir(parents=True, exist_ok=True)
    definitions = [
        (1, "rich", ["ckd", "diabetes", "chf"]), (2, "rich", ["copd", "af", "depression"]), (3, "rich", ["ckd", "diabetes"]),
        (4, "sparse", []), (5, "sparse", []), (6, "sparse", []),
        (7, "contradictory", ["ckd", "diabetes", "chf"]), (8, "contradictory", ["copd", "af", "depression"]),
        (9, "stale", ["ckd", "diabetes"]), (10, "stale", ["chf", "depression"]),
        (11, "already_documented", ["ckd", "diabetes", "chf"]), (12, "already_documented", ["copd", "af", "depression"]),
    ]
    bundles = [make_bundle(*definition) for definition in definitions]
    for bundle in bundles:
        (output / f"{bundle.member_id}.json").write_text(bundle.model_dump_json(indent=2) + "\n")
    return bundles


if __name__ == "__main__":
    bundles = generate()
    print(f"Generated {len(bundles)} SYNTHETIC members in {ROOT / 'data/synthetic'}")
