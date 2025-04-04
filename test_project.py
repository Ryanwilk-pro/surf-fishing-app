import pytest
from datetime import datetime, timezone, timedelta
from project import get_moon_phase

# reference new moon date for calculations algorithm
REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
CYCLE_LENGTH = 29.53058867  # lunar cycle length in days

# helper function to calculate test dates
def get_test_date(days_offset):
    """return a UTC datetime offset by days from the reference new moon."""
    return REFERENCE_NEW_MOON + timedelta(days=days_offset)

# test cases for each moon phase
def test_new_moon():
    # new Moon: phase_fraction < 0.02 or >= 0.98
    test_date = get_test_date(0)
    assert get_moon_phase(test_date) == 'New Moon'

    test_date = get_test_date(CYCLE_LENGTH * 0.99)
    assert get_moon_phase(test_date) == 'New Moon'

def test_waxing_crescent():
    # waxing Crescent: 0.02 <= phase_fraction < 0.23
    test_date = get_test_date(CYCLE_LENGTH * 0.10)
    assert get_moon_phase(test_date) == 'Waxing Crescent'

def test_first_quarter():
    # first Quarter: 0.23 <= phase_fraction < 0.27
    test_date = get_test_date(CYCLE_LENGTH * 0.25)
    assert get_moon_phase(test_date) == 'First Quarter'

def test_waxing_gibbous():
    # waxing Gibbous: 0.27 <= phase_fraction < 0.48
    test_date = get_test_date(CYCLE_LENGTH * 0.40)
    assert get_moon_phase(test_date) == 'Waxing Gibbous'

def test_full_moon():
    # full Moon: 0.48 <= phase_fraction < 0.52
    test_date = get_test_date(CYCLE_LENGTH * 0.50)
    assert get_moon_phase(test_date) == 'Full Moon'

def test_waning_gibbous():
    # waning Gibbous: 0.52 <= phase_fraction < 0.73
    test_date = get_test_date(CYCLE_LENGTH * 0.60)
    assert get_moon_phase(test_date) == 'Waning Gibbous'

def test_last_quarter():
    # last Quarter: 0.73 <= phase_fraction < 0.77
    test_date = get_test_date(CYCLE_LENGTH * 0.75)
    assert get_moon_phase(test_date) == 'Last Quarter'

def test_waning_crescent():
    # waning Crescent: 0.77 <= phase_fraction < 0.98
    test_date = get_test_date(CYCLE_LENGTH * 0.90)
    assert get_moon_phase(test_date) == 'Waning Crescent'

# edge case: negative phase fraction correction
def test_negative_phase_correction():
    # test a date before the reference new moon
    test_date = REFERENCE_NEW_MOON - timedelta(days=5)
    result = get_moon_phase(test_date)
    assert result in ['New Moon', 'Waxing Crescent', 'First Quarter', 'Waxing Gibbous',
                      'Full Moon', 'Waning Gibbous', 'Last Quarter', 'Waning Crescent'], \
           "Expected a valid moon phase even with a date before reference"

# error case: Invalid input type
def test_invalid_date_type():
    with pytest.raises(TypeError):
        get_moon_phase("not_a_date")  # should raise an error due to invalid subtraction


# note to self further study pytest syntax this took way too much time and research.

