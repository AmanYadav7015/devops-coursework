import hashlib
import secrets
from decimal import Decimal, ROUND_HALF_UP

CATEGORY_CAPS = {
    "travel": Decimal("12000.00"),
    "meals": Decimal("1500.00"),
    "lodging": Decimal("8000.00"),
    "training": Decimal("25000.00"),
    "equipment": Decimal("40000.00"),
}

REIMBURSEMENT_RATE = {
    "travel": Decimal("1.00"),
    "meals": Decimal("0.80"),
    "lodging": Decimal("1.00"),
    "training": Decimal("0.90"),
    "equipment": Decimal("0.70"),
}

APPROVAL_THRESHOLD = Decimal("10000.00")


class ClaimError(ValueError):
    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_claim(claim):
    if not isinstance(claim, dict):
        raise ClaimError("claim must be an object")

    employee = claim.get("employee")
    if not isinstance(employee, str) or not employee.strip():
        raise ClaimError("employee is required")

    category = claim.get("category")
    if category not in CATEGORY_CAPS:
        raise ClaimError("category must be one of " + ", ".join(sorted(CATEGORY_CAPS)))

    amount = claim.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ClaimError("amount must be a number")
    if amount <= 0:
        raise ClaimError("amount must be greater than zero")

    receipts = claim.get("receipts", 0)
    if not isinstance(receipts, int) or isinstance(receipts, bool) or receipts < 0:
        raise ClaimError("receipts must be a non-negative integer")

    return {
        "employee": employee.strip(),
        "category": category,
        "amount": _money(amount),
        "receipts": receipts,
    }


def price_claim(claim):
    clean = validate_claim(claim)
    cap = CATEGORY_CAPS[clean["category"]]
    rate = REIMBURSEMENT_RATE[clean["category"]]

    capped = min(clean["amount"], cap)
    reimbursed = _money(capped * rate)

    reasons = []
    if clean["amount"] > cap:
        reasons.append("amount exceeds the {} cap of {}".format(clean["category"], cap))
    if clean["receipts"] == 0:
        reimbursed = _money(reimbursed * Decimal("0.50"))
        reasons.append("no receipts attached, reimbursement halved")

    needs_approval = reimbursed > APPROVAL_THRESHOLD
    if needs_approval:
        reasons.append("reimbursement above {} needs manager approval".format(APPROVAL_THRESHOLD))

    return {
        "employee": clean["employee"],
        "category": clean["category"],
        "claimed": float(clean["amount"]),
        "reimbursed": float(reimbursed),
        "needs_approval": needs_approval,
        "reasons": reasons,
    }


def fingerprint(claim, salt):
    clean = validate_claim(claim)
    payload = "{}|{}|{}|{}".format(
        clean["employee"], clean["category"], clean["amount"], clean["receipts"]
    )
    digest = hashlib.sha256((salt + payload).encode("utf-8")).hexdigest()
    return digest[:32]


def issue_reference():
    return "CLM-" + secrets.token_hex(8).upper()


def summarise(claims):
    if not isinstance(claims, list) or not claims:
        raise ClaimError("claims must be a non-empty list")
    priced = [price_claim(item) for item in claims]
    total = sum(Decimal(str(row["reimbursed"])) for row in priced)
    return {
        "count": len(priced),
        "total_reimbursed": float(_money(total)),
        "needs_approval": any(row["needs_approval"] for row in priced),
    }
