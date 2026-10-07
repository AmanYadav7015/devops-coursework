"""Fare calculation rules for the Yatri ride-hailing demo service."""

BASE_FARE = 30.0
RATE_PER_KM = 12.5
RATE_PER_MINUTE = 1.5
NIGHT_SURCHARGE = 25.0
MIN_FARE = 50.0

COUPONS = {
    "FIRST50": 0.50,
    "WEEKEND20": 0.20,
    "STUDENT10": 0.10,
}


class TripError(ValueError):
    """Raised when a trip cannot be priced."""


def validate_trip(distance_km, duration_min, surge):
    if distance_km <= 0:
        raise TripError("distance_km must be greater than zero")
    if duration_min <= 0:
        raise TripError("duration_min must be greater than zero")
    if surge < 1.0:
        raise TripError("surge must be at least 1.0")
    return True


def compute_fare(distance_km, duration_min, surge=1.0, night=False):
    validate_trip(distance_km, duration_min, surge)
    fare = BASE_FARE + (distance_km * RATE_PER_KM) + (duration_min * RATE_PER_MINUTE)
    fare = fare * surge
    if night:
        fare = fare + NIGHT_SURCHARGE
    return round(max(fare, MIN_FARE), 2)


def apply_coupon(amount, code):
    if amount < 0:
        raise TripError("amount must not be negative")
    normalised = str(code).strip().upper()
    if normalised not in COUPONS:
        raise TripError("unknown coupon: " + normalised)
    return round(amount * (1 - COUPONS[normalised]), 2)


def split_fare(amount, riders):
    if riders < 1:
        raise TripError("riders must be at least 1")
    share = round(amount / riders, 2)
    shares = [share] * riders
    shares[-1] = round(amount - share * (riders - 1), 2)
    return shares
