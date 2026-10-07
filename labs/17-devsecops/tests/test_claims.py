import pytest

from app.claims import (
    ClaimError,
    fingerprint,
    issue_reference,
    price_claim,
    summarise,
    validate_claim,
)


def test_validate_claim_accepts_a_normal_claim():
    clean = validate_claim(
        {"employee": "  asha  ", "category": "meals", "amount": 820.5, "receipts": 2}
    )
    assert clean["employee"] == "asha"
    assert float(clean["amount"]) == 820.5


@pytest.mark.parametrize(
    "claim",
    [
        {"employee": "", "category": "meals", "amount": 100},
        {"employee": "asha", "category": "yacht", "amount": 100},
        {"employee": "asha", "category": "meals", "amount": 0},
        {"employee": "asha", "category": "meals", "amount": -5},
        {"employee": "asha", "category": "meals", "amount": "100"},
        {"employee": "asha", "category": "meals", "amount": 100, "receipts": -1},
    ],
)
def test_validate_claim_rejects_bad_input(claim):
    with pytest.raises(ClaimError):
        validate_claim(claim)


def test_validate_claim_rejects_a_non_object():
    with pytest.raises(ClaimError):
        validate_claim(["asha"])


def test_price_claim_applies_the_category_rate():
    priced = price_claim(
        {"employee": "ravi", "category": "meals", "amount": 1000, "receipts": 1}
    )
    assert priced["reimbursed"] == 800.0
    assert priced["needs_approval"] is False
    assert priced["reasons"] == []


def test_price_claim_caps_the_category():
    priced = price_claim(
        {"employee": "ravi", "category": "meals", "amount": 5000, "receipts": 1}
    )
    assert priced["reimbursed"] == 1200.0
    assert "exceeds the meals cap" in priced["reasons"][0]


def test_price_claim_halves_a_claim_without_receipts():
    priced = price_claim(
        {"employee": "ravi", "category": "lodging", "amount": 4000, "receipts": 0}
    )
    assert priced["reimbursed"] == 2000.0
    assert "no receipts attached" in priced["reasons"][0]


def test_price_claim_flags_large_reimbursements_for_approval():
    priced = price_claim(
        {"employee": "ravi", "category": "training", "amount": 25000, "receipts": 4}
    )
    assert priced["reimbursed"] == 22500.0
    assert priced["needs_approval"] is True


def test_fingerprint_is_stable_and_salted():
    claim = {"employee": "ravi", "category": "travel", "amount": 900, "receipts": 1}
    assert fingerprint(claim, "pepper") == fingerprint(claim, "pepper")
    assert fingerprint(claim, "pepper") != fingerprint(claim, "other")
    assert len(fingerprint(claim, "pepper")) == 32


def test_issue_reference_is_unique_and_prefixed():
    references = {issue_reference() for _ in range(200)}
    assert len(references) == 200
    assert all(ref.startswith("CLM-") for ref in references)


def test_summarise_adds_up_a_batch():
    report = summarise(
        [
            {"employee": "a", "category": "meals", "amount": 1000, "receipts": 1},
            {"employee": "b", "category": "travel", "amount": 2000, "receipts": 1},
        ]
    )
    assert report["count"] == 2
    assert report["total_reimbursed"] == 2800.0
    assert report["needs_approval"] is False


def test_summarise_rejects_an_empty_batch():
    with pytest.raises(ClaimError):
        summarise([])
