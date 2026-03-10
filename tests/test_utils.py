"""Tests for formatting utilities."""

from yoorquezt_mev.utils import (
    format_duration,
    format_gwei,
    format_percent,
    format_wei,
    is_valid_address,
    parse_wei,
    truncate_address,
)


class TestFormatWei:
    def test_one_eth(self):
        assert format_wei("1000000000000000000") == "1.0 ETH"

    def test_zero(self):
        assert format_wei("0") == "0.0 ETH"

    def test_fractional(self):
        assert format_wei("1500000000000000000") == "1.5 ETH"

    def test_small_amount(self):
        result = format_wei("100000000000000")  # 0.0001 ETH
        assert result == "0.0001 ETH"

    def test_large_amount(self):
        result = format_wei("100000000000000000000")  # 100 ETH
        assert result == "100.0 ETH"

    def test_int_input(self):
        assert format_wei(10**18) == "1.0 ETH"


class TestFormatGwei:
    def test_float(self):
        assert format_gwei(30.5) == "30.5 gwei"

    def test_string(self):
        assert format_gwei("20") == "20.0 gwei"

    def test_zero(self):
        assert format_gwei(0) == "0.0 gwei"


class TestParseWei:
    def test_whole_eth(self):
        assert parse_wei("1") == 10**18

    def test_fractional_eth(self):
        assert parse_wei("1.5") == 1500000000000000000

    def test_zero(self):
        assert parse_wei("0") == 0

    def test_small_fraction(self):
        assert parse_wei("0.001") == 1000000000000000

    def test_roundtrip(self):
        original = "2"
        assert parse_wei(original) == 2 * 10**18


class TestTruncateAddress:
    def test_standard_address(self):
        addr = "0xabcdef1234567890abcdef1234567890abcdef12"
        assert truncate_address(addr) == "0xabcd...ef12"

    def test_custom_chars(self):
        addr = "0xabcdef1234567890abcdef1234567890abcdef12"
        assert truncate_address(addr, 6) == "0xabcdef...cdef12"

    def test_short_string(self):
        assert truncate_address("0x1234") == "0x1234"


class TestIsValidAddress:
    def test_valid(self):
        assert is_valid_address("0xabcdef1234567890abcdef1234567890abcdef12")

    def test_valid_mixed_case(self):
        assert is_valid_address("0xAbCdEf1234567890AbCdEf1234567890AbCdEf12")

    def test_no_prefix(self):
        assert not is_valid_address("abcdef1234567890abcdef1234567890abcdef12")

    def test_too_short(self):
        assert not is_valid_address("0xabcdef")

    def test_too_long(self):
        assert not is_valid_address("0x" + "a" * 41)

    def test_invalid_chars(self):
        assert not is_valid_address("0xgggggggggggggggggggggggggggggggggggggggg")

    def test_empty(self):
        assert not is_valid_address("")


class TestFormatDuration:
    def test_milliseconds(self):
        assert format_duration(500) == "500ms"

    def test_seconds(self):
        assert format_duration(5000) == "5s"

    def test_minutes(self):
        assert format_duration(120_000) == "2m"

    def test_minutes_and_seconds(self):
        assert format_duration(90_000) == "1m 30s"

    def test_hours(self):
        assert format_duration(7_200_000) == "2h"

    def test_hours_and_minutes(self):
        assert format_duration(5_400_000) == "1h 30m"


class TestFormatPercent:
    def test_whole(self):
        assert format_percent(1.0) == "100.00%"

    def test_fractional(self):
        assert format_percent(0.956) == "95.60%"

    def test_zero(self):
        assert format_percent(0.0) == "0.00%"

    def test_small(self):
        assert format_percent(0.001) == "0.10%"
