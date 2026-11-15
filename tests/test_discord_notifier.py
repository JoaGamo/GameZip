import pytest
from unittest.mock import patch

from discord_notifier import notify_game_processed


class TestNotifyGameProcessed:
    @patch("discord_notifier.requests.post")
    def test_payload_structure(self, mock_post):
        mock_post.return_value.status_code = 204
        notify_game_processed("https://discord.com/api/webhook/test", "Minecraft", 1.50, "https://images.igdb.com/igdb/image/upload/t_cover_big/abc123.jpg")
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        embed = payload["embeds"][0]
        assert embed["title"] == "Game processed successfully"
        assert embed["color"] == 0x00FF00
        fields = embed["fields"]
        assert fields[0] == {"name": "Game", "value": "Minecraft", "inline": True}
        assert fields[1] == {"name": "Size", "value": "1.50 GB", "inline": True}
        assert fields[2] == {"name": "Cover", "value": "https://images.igdb.com/igdb/image/upload/t_cover_big/abc123.jpg", "inline": True}
        assert kwargs["timeout"] == 10

    @patch("discord_notifier.requests.post")
    def test_no_cover_url(self, mock_post):
        mock_post.return_value.status_code = 204
        notify_game_processed("https://discord.com/api/webhook/test", "Minecraft", 2.0)
        fields = mock_post.call_args.kwargs["json"]["embeds"][0]["fields"]
        assert len(fields) == 2

    @patch("discord_notifier.requests.post")
    def test_error_does_not_raise(self, mock_post):
        mock_post.side_effect = Exception("timeout")
        notify_game_processed("https://discord.com/api/webhook/test", "Minecraft", 1.0)
        # Should not raise

    @patch("discord_notifier.requests.post")
    def test_timeout_exception(self, mock_post):
        mock_post.side_effect = Exception("Connection timed out")
        notify_game_processed("https://discord.com/api/webhook/test", "Game", 1.0)