from pathlib import Path
import pytest

from dayone.generate import make_bundle


@pytest.fixture
def rich_bundle():
    return make_bundle(1, "rich", ["ckd", "diabetes", "chf"])


@pytest.fixture
def contradictory_bundle():
    return make_bundle(7, "contradictory", ["ckd", "diabetes", "chf"])
