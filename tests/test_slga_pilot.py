import pytest

from scripts.slga_tiled_pilot import _normalise_peak_rss_bytes


def test_peak_rss_units_are_normalised_only_for_known_platform_contracts():
    assert _normalise_peak_rss_bytes(1234, "darwin") == (1234, "bytes")
    assert _normalise_peak_rss_bytes(1234, "linux") == (1_263_616, "KiB")
    assert _normalise_peak_rss_bytes(1234, "freebsd") == (
        None,
        "platform-dependent units",
    )
    with pytest.raises(ValueError, match="non-negative"):
        _normalise_peak_rss_bytes(-1, "darwin")
