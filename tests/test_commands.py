"""CLI command tests using Click's CliRunner + mocked client."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flomo_cli.cli import cli
from flomo_cli.exceptions import FlomoApiError, NotAuthenticatedError


def _runner():
    return CliRunner()


def _make_client(memos=None, memo=None, related=None, tags=None, memos_ascending=None, daily_review=None, rename_tag=None):
    """Return a mock FlomoClient."""
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    m.list_memos.return_value = memos or []
    m.list_memos_ascending.return_value = memos_ascending or memos or []
    m.list_all_memos.return_value = memos or []
    m.get_memo.return_value = memo or {"slug": "abc", "content": "<p>hi</p>", "tags": []}
    m.get_related_memos.return_value = related or []
    m.get_tag_tree.return_value = tags or []
    m.get_daily_review.return_value = daily_review or []
    m.create_memo.return_value = {"slug": "new", "content": "<p>x</p>", "tags": []}
    m.update_memo.return_value = {"slug": "abc", "content": "<p>y</p>", "tags": []}
    m.delete_memo.return_value = ""
    m.rename_tag.return_value = rename_tag or {"updated_num": 0}
    return m


# ─── Auth commands ──────────────────────────────────────────────────────────


class TestAuthCommands:
    def test_status_not_authenticated(self, monkeypatch):
        monkeypatch.delenv("FLOMO_TOKEN", raising=False)
        monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", MagicMock(exists=lambda: False))
        result = _runner().invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "未登录" in result.output or "flomo login" in result.output

    def test_status_json_not_authenticated(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FLOMO_TOKEN", raising=False)
        monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "nofile.json")
        result = _runner().invoke(cli, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["authenticated"] is False

    def test_logout_when_not_logged_in(self, tmp_path, monkeypatch):
        monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "nofile.json")
        result = _runner().invoke(cli, ["logout"])
        assert result.exit_code == 0

    def test_logout_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "nofile.json")
        result = _runner().invoke(cli, ["logout", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True


# ─── Memo commands ──────────────────────────────────────────────────────────


class TestMemoCommands:
    def _with_token(self, args):
        return ["--token", "fake-token"] + args

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_list_json(self, MockClient):
        memos = [
            {"slug": "s1", "content": "<p>First</p>", "tags": ["work"], "created_at": "2026-01-01 10:00:00", "updated_at": "2026-01-01 10:00:00", "files": []},
            {"slug": "s2", "content": "<p>Second</p>", "tags": [], "created_at": "2026-01-01 09:00:00", "updated_at": "2026-01-01 09:00:00", "files": []},
        ]
        MockClient.return_value = _make_client(memos=memos)
        result = _runner().invoke(cli, self._with_token(["list", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["slug"] == "s1"
        assert data["data"][0]["content_text"] == "First"
        assert "has_more" in data

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_list_sort_newest_is_default(self, MockClient):
        memos = [
            {"slug": "new", "content": "<p>New</p>", "tags": [], "created_at": "2026-03-17", "updated_at": "2026-03-17", "files": []},
        ]
        mock = _make_client(memos=memos)
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["list", "--json"]))
        assert result.exit_code == 0, result.output
        mock.list_memos.assert_called_once()
        mock.list_memos_ascending.assert_not_called()

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_list_sort_oldest(self, MockClient):
        old_memos = [
            {"slug": "old", "content": "<p>Old</p>", "tags": [], "created_at": "2024-02-19", "updated_at": "2024-02-19", "files": []},
        ]
        mock = _make_client(memos_ascending=old_memos)
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["list", "--sort", "oldest", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["data"][0]["slug"] == "old"
        mock.list_memos_ascending.assert_called_once()
        mock.list_memos.assert_not_called()

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_get_json(self, MockClient):
        memo = {"slug": "abc", "content": "<p>Hello</p>", "tags": ["note"], "created_at": "2026-01-01", "updated_at": "2026-01-01", "files": []}
        MockClient.return_value = _make_client(memo=memo)
        result = _runner().invoke(cli, self._with_token(["get", "abc", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["slug"] == "abc"
        assert data["data"]["content_text"] == "Hello"

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_new_json(self, MockClient):
        MockClient.return_value = _make_client()
        result = _runner().invoke(cli, self._with_token(["new", "test content #tag1", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_new_from_stdin(self, MockClient):
        MockClient.return_value = _make_client()
        result = _runner().invoke(cli, self._with_token(["new", "--json"]), input="来自 stdin 的内容\n")
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_new_from_file(self, MockClient, tmp_path):
        MockClient.return_value = _make_client()
        note_file = tmp_path / "note.txt"
        note_file.write_text("文件中的笔记内容 #测试", encoding="utf-8")
        result = _runner().invoke(cli, self._with_token(["new", "-f", str(note_file), "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_edit_json(self, MockClient):
        MockClient.return_value = _make_client()
        result = _runner().invoke(cli, self._with_token(["edit", "abc", "new content", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_delete_with_yes_flag(self, MockClient):
        MockClient.return_value = _make_client()
        result = _runner().invoke(cli, self._with_token(["delete", "abc", "-y", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["deleted"] is True

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_delete_without_yes_and_reject_confirmation(self, MockClient):
        mock = _make_client()
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["delete", "abc"]), input="n\n")
        assert result.exit_code == 1
        assert "Aborted!" in result.output
        mock.delete_memo.assert_not_called()

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_delete_without_yes_and_confirm(self, MockClient):
        mock = _make_client()
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["delete", "abc"]), input="y\n")
        assert result.exit_code == 0, result.output
        mock.delete_memo.assert_called_once_with("abc")

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_delete_json_without_yes_skips_confirmation(self, MockClient):
        mock = _make_client()
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["delete", "abc", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["deleted"] is True
        mock.delete_memo.assert_called_once_with("abc")

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_search_json(self, MockClient):
        memos = [
            {"slug": "s1", "content": "<p>Python programming</p>", "tags": [], "created_at": "2026-01-01", "updated_at": "2026-01-01", "files": []},
            {"slug": "s2", "content": "<p>JavaScript tips</p>", "tags": [], "created_at": "2026-01-01", "updated_at": "2026-01-01", "files": []},
        ]
        MockClient.return_value = _make_client(memos=memos)
        result = _runner().invoke(cli, self._with_token(["search", "Python", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["total"] == 1
        assert data["data"][0]["slug"] == "s1"

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_related_json(self, MockClient):
        related = [
            {"memo_id": 1, "similarity": "0.85", "memo": {"slug": "r1", "content": "<p>related</p>", "tags": [], "created_at": "2026-01-01", "updated_at": "2026-01-01"}}
        ]
        MockClient.return_value = _make_client(related=related)
        result = _runner().invoke(cli, self._with_token(["related", "abc", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert len(data["data"]) == 1

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_tags_json(self, MockClient):
        tag_tree = [{"name": "work", "memo_count": 5, "children": []}]
        MockClient.return_value = _make_client(tags=tag_tree)
        result = _runner().invoke(cli, self._with_token(["tags", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_review_json(self, MockClient):
        review_memos = [
            {"slug": "r1", "content": "<p>Review memo 1</p>", "tags": ["daily"], "created_at": "2024-03-08 18:15:23", "updated_at": "2024-03-08 18:15:23", "files": []},
            {"slug": "r2", "content": "<p>Review memo 2</p>", "tags": [], "created_at": "2024-08-19 23:26:29", "updated_at": "2024-08-19 23:26:29", "files": []},
        ]
        MockClient.return_value = _make_client(daily_review=review_memos)
        result = _runner().invoke(cli, self._with_token(["review", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["slug"] == "r1"
        assert data["data"][0]["content_text"] == "Review memo 1"

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_review_json_empty(self, MockClient):
        MockClient.return_value = _make_client(daily_review=[])
        result = _runner().invoke(cli, self._with_token(["review", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"] == []

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_review_rich_output(self, MockClient):
        review_memos = [
            {"slug": "r1", "content": "<p>Some review content</p>", "tags": ["reading"], "created_at": "2024-03-08 18:15:23", "updated_at": "2024-03-08 18:15:23", "files": []},
        ]
        MockClient.return_value = _make_client(daily_review=review_memos)
        result = _runner().invoke(cli, self._with_token(["review"]))
        assert result.exit_code == 0, result.output
        assert "每日回顾" in result.output or "Some review content" in result.output


# ─── Tag commands ────────────────────────────────────────────────────────────


class TestTagCommands:
    def _with_token(self, args):
        return ["--token", "fake-token"] + args

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_rename_json(self, MockClient):
        MockClient.return_value = _make_client(rename_tag={"updated_num": 5})
        result = _runner().invoke(cli, self._with_token(["tag", "rename", "old", "new", "--json"]))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["old_tag"] == "old"
        assert data["data"]["new_tag"] == "new"
        assert data["data"]["updated_num"] == 5

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_rename_rich_output(self, MockClient):
        MockClient.return_value = _make_client(rename_tag={"updated_num": 3})
        result = _runner().invoke(cli, self._with_token(["tag", "rename", "旧标签", "新标签"]))
        assert result.exit_code == 0, result.output
        assert "旧标签" in result.output
        assert "新标签" in result.output

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_rename_strips_hash_prefix(self, MockClient):
        mock = _make_client(rename_tag={"updated_num": 2})
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["tag", "rename", "#work", "#job", "--json"]))
        assert result.exit_code == 0, result.output
        mock.rename_tag.assert_called_once_with("work", "job")
        data = json.loads(result.output)
        assert data["data"]["old_tag"] == "work"
        assert data["data"]["new_tag"] == "job"

    def test_rename_same_name_rejected(self):
        result = _runner().invoke(cli, ["--token", "t", "tag", "rename", "same", "same"])
        assert result.exit_code != 0
        assert "相同" in result.output

    def test_rename_empty_name_rejected(self):
        result = _runner().invoke(cli, ["--token", "t", "tag", "rename", "#", "new"])
        assert result.exit_code != 0
        assert "为空" in result.output

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_rename_hierarchical_tag(self, MockClient):
        MockClient.return_value = _make_client(rename_tag={"updated_num": 10})
        result = _runner().invoke(
            cli, self._with_token(["tag", "rename", "读书/认知觉醒", "读书/认知驱动", "--json"])
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["data"]["old_tag"] == "读书/认知觉醒"
        assert data["data"]["new_tag"] == "读书/认知驱动"
        assert data["data"]["updated_num"] == 10

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_rename_api_error_json(self, MockClient):
        mock = _make_client()
        mock.rename_tag.side_effect = FlomoApiError("标签不存在")
        MockClient.return_value = mock
        result = _runner().invoke(cli, self._with_token(["tag", "rename", "a", "b", "--json"]))
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"] == "api_error"


# ─── Error handling ──────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_not_authenticated_json(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FLOMO_TOKEN", raising=False)
        monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "nofile.json")
        result = _runner().invoke(cli, ["list", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"] == "not_authenticated"

    @patch("flomo_cli.commands._common.FlomoClient")
    def test_api_error_json(self, MockClient):
        mock = _make_client()
        mock.list_memos.side_effect = FlomoApiError("API 失败")
        MockClient.return_value = mock
        result = _runner().invoke(cli, ["--token", "tok", "list", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"] == "api_error"
