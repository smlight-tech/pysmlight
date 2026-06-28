import pytest

from pysmlight.models import IRPayload


@pytest.mark.parametrize(
    "timings, freq, expected_code, expected_freq",
    [
        ([500, 1000], 38000, "0a14", 38),  # Regular conversion
        ([500], None, "0a", 38),  # Missing optional frequency
        (
            [26000],
            38000,
            "ff00ff000a",
            38,
        ),  # Large ticks greater than 255
    ],
)
def test_ir_payload_from_raw_timings(timings, freq, expected_code, expected_freq):
    payload = IRPayload.from_raw_timings(timings, freq=freq)
    assert payload.code == expected_code
    assert payload.freq == expected_freq


def test_ir_payload_to_raw_timings_empty():
    payload = IRPayload()
    with pytest.raises(ValueError, match="IRPayload code is empty"):
        payload.to_raw_timings()


@pytest.mark.parametrize(
    "code, expected_timings",
    [
        ("0a14", [500, 1000]),  # Basic usage
        ("ff00ff000a", [26000]),  # Large ticks greater than 255
        ("aaff", [8500, 12750]),  # Edge case ending perfectly with 255
    ],
)
def test_ir_payload_to_raw_timings(code, expected_timings):
    payload = IRPayload(code=code)
    assert payload.to_raw_timings() == expected_timings
