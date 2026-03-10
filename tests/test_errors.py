"""Tests for QMEVError and MEV_ERROR_CODES."""

import pytest

from yoorquezt_mev.errors import MEV_ERROR_CODES, QMEVError


class TestQMEVErrorInit:
    def test_basic_construction(self):
        err = QMEVError("BUNDLE_REVERTED", "Bundle simulation reverted")
        assert err.code == "BUNDLE_REVERTED"
        assert str(err) == "Bundle simulation reverted"
        assert err.details is None

    def test_with_details(self):
        details = {"tx": "0xabc", "reason": "out of gas"}
        err = QMEVError("SIMULATION_FAILED", "sim failed", details)
        assert err.details == details
        assert err.details["tx"] == "0xabc"

    def test_inherits_from_exception(self):
        err = QMEVError("TEST", "test error")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(QMEVError) as exc_info:
            raise QMEVError("RATE_LIMITED", "too many requests")
        assert exc_info.value.code == "RATE_LIMITED"

    def test_caught_as_generic_exception(self):
        with pytest.raises(Exception):
            raise QMEVError("TEST", "generic catch")


class TestFromCode:
    def test_known_code(self):
        err = QMEVError.from_code("BUNDLE_REVERTED")
        assert err.code == "BUNDLE_REVERTED"
        assert str(err) == "Bundle simulation reverted"

    def test_known_code_with_details(self):
        err = QMEVError.from_code("RELAY_TIMEOUT", {"relay": "flashbots"})
        assert err.code == "RELAY_TIMEOUT"
        assert err.details == {"relay": "flashbots"}

    def test_unknown_code(self):
        err = QMEVError.from_code("TOTALLY_NEW_ERROR")
        assert err.code == "TOTALLY_NEW_ERROR"
        assert "Unknown error" in str(err)

    @pytest.mark.parametrize("code", list(MEV_ERROR_CODES.keys()))
    def test_all_known_codes_produce_correct_message(self, code: str):
        err = QMEVError.from_code(code)
        assert err.code == code
        assert str(err) == MEV_ERROR_CODES[code]


class TestNetworkError:
    def test_basic(self):
        err = QMEVError.network_error()
        assert err.code == "NETWORK_ERROR"
        assert str(err) == "Network connection failed"
        assert err.details is None

    def test_with_cause(self):
        cause = ConnectionRefusedError("refused")
        err = QMEVError.network_error(cause)
        assert err.code == "NETWORK_ERROR"
        assert err.details is cause


class TestAuthError:
    def test_basic(self):
        err = QMEVError.auth_error()
        assert err.code == "AUTH_INVALID"
        assert str(err) == "Invalid API key or credentials"
        assert err.details is None


class TestFromJsonRpcError:
    def test_standard_rpc_error(self):
        rpc_err = {"code": -32600, "message": "Invalid Request"}
        err = QMEVError.from_json_rpc_error(rpc_err)
        assert err.code == "RPC_-32600"
        assert str(err) == "Invalid Request"
        assert err.details is None

    def test_rpc_error_with_data(self):
        rpc_err = {
            "code": -32000,
            "message": "execution reverted",
            "data": "0xdeadbeef",
        }
        err = QMEVError.from_json_rpc_error(rpc_err)
        assert err.code == "RPC_-32000"
        assert str(err) == "execution reverted"
        assert err.details == "0xdeadbeef"

    def test_rpc_error_missing_fields(self):
        err = QMEVError.from_json_rpc_error({})
        assert err.code == "RPC_-1"
        assert str(err) == "Unknown RPC error"
        assert err.details is None

    def test_rpc_error_partial(self):
        err = QMEVError.from_json_rpc_error({"code": -32601})
        assert err.code == "RPC_-32601"
        assert str(err) == "Unknown RPC error"


class TestToDict:
    def test_basic(self):
        err = QMEVError("BUNDLE_EXPIRED", "Bundle target block has passed")
        d = err.to_dict()
        assert d == {
            "code": "BUNDLE_EXPIRED",
            "message": "Bundle target block has passed",
            "details": None,
        }

    def test_with_details(self):
        err = QMEVError("AUCTION_OUTBID", "outbid", {"new_bid": "1.5 ETH"})
        d = err.to_dict()
        assert d["code"] == "AUCTION_OUTBID"
        assert d["details"] == {"new_bid": "1.5 ETH"}

    def test_roundtrip_from_code(self):
        err = QMEVError.from_code("RELAY_UNAVAILABLE", "relay-1")
        d = err.to_dict()
        assert d["code"] == "RELAY_UNAVAILABLE"
        assert d["message"] == "Relay is not reachable"
        assert d["details"] == "relay-1"


class TestRepr:
    def test_repr_format(self):
        err = QMEVError("TEST_CODE", "test message")
        r = repr(err)
        assert "QMEVError" in r
        assert "TEST_CODE" in r
        assert "test message" in r

    def test_repr_with_special_chars(self):
        err = QMEVError("X", "it's a \"test\"")
        r = repr(err)
        assert "QMEVError" in r


class TestMEVErrorCodes:
    def test_all_codes_are_strings(self):
        for code, message in MEV_ERROR_CODES.items():
            assert isinstance(code, str)
            assert isinstance(message, str)

    def test_expected_codes_exist(self):
        expected = [
            "BUNDLE_REVERTED",
            "BUNDLE_UNDERPAID",
            "BUNDLE_EXPIRED",
            "RELAY_TIMEOUT",
            "RELAY_UNAVAILABLE",
            "AUTH_INVALID",
            "AUTH_EXPIRED",
            "RATE_LIMITED",
            "NETWORK_ERROR",
            "WS_DISCONNECTED",
            "WS_SUBSCRIBE_FAILED",
            "INTERNAL_ERROR",
        ]
        for code in expected:
            assert code in MEV_ERROR_CODES, f"Missing error code: {code}"

    def test_no_empty_messages(self):
        for code, message in MEV_ERROR_CODES.items():
            assert len(message) > 0, f"Empty message for code: {code}"
