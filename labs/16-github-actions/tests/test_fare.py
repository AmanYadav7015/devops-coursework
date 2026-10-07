import pytest

from app.fare import (
    BASE_FARE,
    RATE_PER_KM,
    RATE_PER_MINUTE,
    NIGHT_SURCHARGE,
    TripError,
    apply_coupon,
    compute_fare,
    split_fare,
    validate_trip,
)


def test_validate_trip_accepts_a_normal_trip():
    assert validate_trip(5.0, 12.0, 1.0) is True


@pytest.mark.parametrize(
    "distance,duration,surge",
    [
        (0, 10, 1.0),
        (-3, 10, 1.0),
        (5, 0, 1.0),
        (5, -1, 1.0),
        (5, 10, 0.5),
    ],
)
def test_validate_trip_rejects_bad_input(distance, duration, surge):
    with pytest.raises(TripError):
        validate_trip(distance, duration, surge)


def test_compute_fare_matches_the_published_formula():
    expected = round(BASE_FARE + (10 * RATE_PER_KM) + (20 * RATE_PER_MINUTE), 2)
    assert compute_fare(10, 20) == expected


def test_compute_fare_applies_surge_multiplier():
    plain = compute_fare(10, 20)
    surged = compute_fare(10, 20, surge=2.0)
    assert surged == round(plain * 2.0, 2)


def test_compute_fare_adds_night_surcharge():
    day = compute_fare(10, 20)
    night = compute_fare(10, 20, night=True)
    assert night - day == NIGHT_SURCHARGE


def test_compute_fare_never_drops_below_minimum():
    assert compute_fare(0.1, 0.1) == 50.0


def test_apply_coupon_is_case_insensitive():
    assert apply_coupon(200.0, "first50") == apply_coupon(200.0, "FIRST50") == 100.0


def test_apply_coupon_rejects_unknown_code():
    with pytest.raises(TripError):
        apply_coupon(200.0, "NOTACOUPON")


def test_apply_coupon_rejects_negative_amount():
    with pytest.raises(TripError):
        apply_coupon(-1.0, "FIRST50")


def test_split_fare_shares_sum_back_to_the_total():
    total = 100.0
    shares = split_fare(total, 3)
    assert len(shares) == 3
    assert round(sum(shares), 2) == total


def test_split_fare_rejects_zero_riders():
    with pytest.raises(TripError):
        split_fare(100.0, 0)
