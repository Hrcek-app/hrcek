from hrcek.ops.errors import RELEASE_IS_CURRENT, RELEASE_NOT_RECORDED, OpsError


def test_an_ops_error_leads_with_its_code_and_ends_with_details():
    error = OpsError(RELEASE_NOT_RECORDED, release="v1.0.0")
    assert str(error) == (
        "HRC-OPS-0002: That release has never run against this database, "
        "so there is nothing to roll back to. (release=v1.0.0)"
    )
    assert error.error_code is RELEASE_NOT_RECORDED


def test_an_ops_error_without_details_is_just_code_and_message():
    assert str(OpsError(RELEASE_IS_CURRENT)) == (
        "HRC-OPS-0003: That release is already the current one."
    )
