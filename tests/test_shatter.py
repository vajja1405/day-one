from copy import deepcopy

import pytest

from evaluation.shatter_fixtures import as_bundle, fixtures
from shatter.engine import shatter
from shatter.modes import MODES


def source_record():
    record = fixtures()[6]
    bundle = as_bundle(record)
    bundle["_shatter"] = deepcopy(record["_shatter"])
    return bundle


def test_zero_is_a_noop_and_reports_no_events():
    original = source_record()
    fragmented, report = shatter(original, severity=0.0, seed=11)
    assert fragmented == {key: value for key, value in original.items() if key != "_shatter"}
    assert not report.events
    assert report.restore(fragmented) == fragmented


def test_seeded_runs_are_deterministic_and_reversible():
    original = source_record()
    left, left_report = shatter(original, severity=0.6, seed=42)
    right, right_report = shatter(original, severity=0.6, seed=42)
    assert left == right
    assert left_report.model_dump() == right_report.model_dump()
    assert left_report.restore(left) == {key: value for key, value in original.items() if key != "_shatter"}


@pytest.mark.parametrize("mode", list(MODES))
def test_each_mode_can_fire_at_maximum_severity(mode):
    for record in fixtures():
        bundle = as_bundle(record)
        bundle["_shatter"] = deepcopy(record["_shatter"])
        _, report = shatter(bundle, severity=1.0, modes=[mode], seed=0)
        if report.eligibility[mode] > 0:
            assert report.fired[mode] > 0
            return
    pytest.fail(f"no fixture exercises {mode}")


def test_private_ground_truth_never_reaches_fragmented_record():
    fragmented, _ = shatter(source_record(), severity=0.8, seed=3)
    assert "_shatter" not in fragmented
    assert "ground_truth" not in str(fragmented)


def test_bad_inputs_fail_closed():
    with pytest.raises(ValueError):
        shatter(source_record(), severity=1.1, seed=0)
    with pytest.raises(ValueError):
        shatter(source_record(), severity=0.4, modes=["negation_loss", "negation_loss"], seed=0)
    with pytest.raises(ValueError):
        shatter({"member_id": "SYN-001"}, severity=0.4, seed=0)
