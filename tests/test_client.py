"""Unit tests for FlomoClient using mocked HTTP responses."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from flomo_cli.client import FlomoClient, _generate_sign, _handle_response
from flomo_cli.exceptions import FlomoApiError, NotAuthenticatedError, NotFoundError


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    return resp


class TestHandleResponse:
    def test_success_returns_data(self):
        resp = _mock_response({"code": 0, "data": {"id": 1}})
        assert _handle_response(resp) == {"id": 1}

    def test_success_empty_data(self):
        resp = _mock_response({"code": 0, "data": []})
        assert _handle_response(resp) == []

    def test_session_expired_raises(self):
        resp = _mock_response({"code": -10, "message": "expired"})
        with pytest.raises(NotAuthenticatedError):
            _handle_response(resp)

    def test_password_required_raises(self):
        resp = _mock_response({"code": -20, "message": "verify"})
        with pytest.raises(NotAuthenticatedError):
            _handle_response(resp)

    def test_404_raises_not_found(self):
        resp = _mock_response({"code": -1, "message": "not found"}, status_code=404)
        with pytest.raises(NotFoundError):
            _handle_response(resp)

    def test_generic_error_raises(self):
        resp = _mock_response({"code": -99, "message": "unknown"})
        with pytest.raises(FlomoApiError):
            _handle_response(resp)


class TestFlomoClientMethods:
    def setup_method(self):
        self.client = FlomoClient("test-token-123")

    def teardown_method(self):
        self.client._http.close()

    def _patch_get(self, data):
        return patch.object(
            self.client._http,
            "request",
            return_value=_mock_response({"code": 0, "data": data}),
        )

    def test_get_me(self):
        user = {"id": 1, "name": "Test"}
        with self._patch_get(user):
            result = self.client.get_me()
        assert result == user

    def test_list_memos_returns_list(self):
        memos = [{"slug": "abc", "content": "<p>hi</p>"}]
        with self._patch_get(memos):
            result = self.client.list_memos(limit=10)
        assert result == memos

    def test_get_memo(self):
        memo = {"slug": "abc123", "content": "<p>test</p>", "tags": []}
        with self._patch_get(memo):
            result = self.client.get_memo("abc123")
        assert result["slug"] == "abc123"

    def test_create_memo(self):
        memo = {"slug": "newslug", "content": "<p>new</p>", "tags": ["tag1"]}
        with self._patch_get(memo):
            result = self.client.create_memo("<p>new</p>")
        assert result["slug"] == "newslug"

    def test_delete_memo(self):
        with self._patch_get(""):
            result = self.client.delete_memo("someslug")
        assert result == ""

    def test_get_related_memos(self):
        related = [{"memo_id": 1, "similarity": "0.9", "memo": {"content": "<p>r</p>"}}]
        with self._patch_get(related):
            result = self.client.get_related_memos("abc")
        assert len(result) == 1

    def test_list_all_memos_stops_on_empty(self):
        call_count = 0

        def mock_list(*, limit, latest_updated_at, latest_slug, include_deleted=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"slug": "s1", "updated_at": "2026-01-01 10:00:00", "content": ""}]
            return []

        with patch.object(self.client, "list_memos_ascending", side_effect=mock_list):
            result = self.client.list_all_memos()
        assert len(result) == 1
        assert call_count == 2

    def test_list_memos_excludes_deleted_by_default(self):
        memos = [
            {"slug": "a1", "content": "<p>active</p>", "deleted_at": None},
            {"slug": "d1", "content": "<p>deleted</p>", "deleted_at": "2026-03-01 10:00:00"},
            {"slug": "a2", "content": "<p>active2</p>"},
        ]
        with self._patch_get(memos):
            result = self.client.list_memos(limit=10)
        assert [m["slug"] for m in result] == ["a1", "a2"]

    def test_list_memos_includes_deleted_when_requested(self):
        memos = [
            {"slug": "a1", "content": "<p>active</p>", "deleted_at": None},
            {"slug": "d1", "content": "<p>deleted</p>", "deleted_at": "2026-03-01 10:00:00"},
        ]
        with self._patch_get(memos):
            result = self.client.list_memos(limit=10, include_deleted=True)
        assert len(result) == 2

    def test_list_all_memos_excludes_deleted(self):
        call_count = 0

        def mock_list(*, limit, latest_updated_at, latest_slug, include_deleted=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    {"slug": "a1", "updated_at": "2026-01-01 10:00:00", "content": "", "deleted_at": None},
                    {"slug": "d1", "updated_at": "2026-01-01 11:00:00", "content": "", "deleted_at": "2026-01-01 12:00:00"},
                ]
            return []

        with patch.object(self.client, "list_memos_ascending", side_effect=mock_list):
            result = self.client.list_all_memos()
        assert [m["slug"] for m in result] == ["a1"]

    def test_request_retries_timeout_then_succeeds(self):
        user = {"id": 1, "name": "RetryOK"}
        with (
            patch.object(
                self.client._http,
                "request",
                side_effect=[
                    httpx.TimeoutException("timeout"),
                    _mock_response({"code": 0, "data": user}),
                ],
            ) as mock_request,
            patch("flomo_cli.client.time.sleep") as mock_sleep,
        ):
            result = self.client.get_me()

        assert result == user
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(2)

    def test_request_network_error_exhausts_retries(self):
        with (
            patch.object(
                self.client._http,
                "request",
                side_effect=httpx.NetworkError("network down"),
            ) as mock_request,
            patch("flomo_cli.client.time.sleep") as mock_sleep,
        ):
            with pytest.raises(FlomoApiError, match="已重试 3 次"):
                self.client.get_me()

        assert mock_request.call_count == 3
        assert [call.args[0] for call in mock_sleep.call_args_list] == [2, 4]

    def test_get_daily_review(self):
        slugs = ["slug1", "slug2"]
        memo1 = {"slug": "slug1", "content": "<p>m1</p>", "tags": []}
        memo2 = {"slug": "slug2", "content": "<p>m2</p>", "tags": []}
        with patch.object(self.client, "_get", return_value=slugs):
            with patch.object(self.client, "get_memo", side_effect=[memo1, memo2]):
                result = self.client.get_daily_review()
        assert len(result) == 2
        assert result[0]["slug"] == "slug1"

    def test_get_daily_review_skips_not_found(self):
        slugs = ["ok", "gone", "ok2"]
        memo_ok = {"slug": "ok", "content": "<p>ok</p>", "tags": []}
        memo_ok2 = {"slug": "ok2", "content": "<p>ok2</p>", "tags": []}
        with patch.object(self.client, "_get", return_value=slugs):
            with patch.object(
                self.client,
                "get_memo",
                side_effect=[memo_ok, NotFoundError("not found"), memo_ok2],
            ):
                result = self.client.get_daily_review()
        assert len(result) == 2
        assert [m["slug"] for m in result] == ["ok", "ok2"]

    def test_get_daily_review_empty(self):
        with patch.object(self.client, "_get", return_value=[]):
            result = self.client.get_daily_review()
        assert result == []

    def test_request_does_not_retry_api_error(self):
        with (
            patch.object(
                self.client._http,
                "request",
                return_value=_mock_response({"code": -99, "message": "boom"}),
            ) as mock_request,
            patch("flomo_cli.client.time.sleep") as mock_sleep,
        ):
            with pytest.raises(FlomoApiError):
                self.client.get_me()

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()
