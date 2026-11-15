import requests
from typing import Optional

def notify_game_processed(webhook_url: str, game_name: str, size_gb: float, cover_url: Optional[str] = None) -> None:
    """Send Discord embed after successful game compression.

    Args:
        webhook_url: Full webhook URL from env var.
        game_name: Cleaned game name.
        size_gb: Archive size in GB (float).
        cover_url: Optional IGDB cover image URL.
    """
    embed = {
        "title": "Game processed successfully",
        "color": 0x00FF00,  # green
        "fields": [
            {"name": "Game", "value": game_name, "inline": True},
            {"name": "Size", "value": f"{size_gb:.2f} GB", "inline": True},
        ]
    }
    if cover_url:
        embed["fields"].append({"name": "Cover", "value": cover_url, "inline": True})
    payload = {"embeds": [embed]}
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Discord notification failed: {e}")