from datetime import date

from django.utils import formats, translation

DAY = date(2026, 10, 7)


def test_english_dates_are_british():
    with translation.override("en"):
        assert formats.date_format(DAY) == "7 Oct 2026"
        assert formats.date_format(DAY, "SHORT_DATE_FORMAT") == "07/10/2026"
        assert formats.date_format(DAY, "MONTH_DAY_FORMAT") == "7 Oct"


def test_slovenian_keeps_its_own_dates():
    with translation.override("sl"):
        assert formats.date_format(DAY) != "7 Oct 2026"
