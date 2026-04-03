"""
Slack/Discord Bot Skeleton — Stores conversations in Mem0 automatically.

Slack Usage:
    export SLACK_BOT_TOKEN=xoxb-your-token
    export MEM0_BASE_URL=http://localhost:8000
    export MEM0_API_KEY=your-jwt-token
    python -m mem0.slack_bot

Discord Usage:
    export DISCORD_BOT_TOKEN=your-token
    export MEM0_BASE_URL=http://localhost:8000
    export MEM0_API_KEY=your-jwt-token
    python -m mem0.discord_bot
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = ["Mem0Bot"]


class Mem0Bot:
    """
    Base bot class that stores conversations in Mem0.

    Subclass this for Slack or Discord specific implementations.
    """

    def __init__(
        self,
        mem0_base_url: str = "http://localhost:8000",
        mem0_api_key: Optional[str] = None,
    ):
        self.mem0_base_url = mem0_base_url
        self.mem0_api_key = mem0_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from mem0.client import Mem0Client
            self._client = Mem0Client(
                base_url=self.mem0_base_url,
                api_key=self.mem0_api_key,
            )
        return self._client

    def on_message(self, user_id: str, message: str) -> str:
        """
        Handle an incoming message.

        1. Store the message in Mem0
        2. Search for relevant context
        3. Return a response (to be implemented by subclass)

        Args:
            user_id: User/channel identifier.
            message: Message content.

        Returns:
            Bot response string.
        """
        client = self._get_client()

        # Store the message
        try:
            client.add(
                [{"role": "user", "content": message}],
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to store message: {e}")

        # Search for context
        context = ""
        try:
            results = client.search(message, user_id=user_id)
            memories = results.get("results", [])[:5]
            if memories:
                context = "\n".join(m.get("memory", "") for m in memories)
        except Exception as e:
            logger.warning(f"Failed to search context: {e}")

        # Generate response (implement in subclass or integrate with LLM)
        if context:
            return f"Based on what I remember: {context[:200]}..."
        return "I don't have any relevant memories about that yet."


def main_slack():
    """Run the Slack bot."""
    try:
        import slack_bolt
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        print("Install slack-bolt: pip install slack-bolt")
        return

    bot = Mem0Bot(
        mem0_base_url=os.environ.get("MEM0_BASE_URL", "http://localhost:8000"),
        mem0_api_key=os.environ.get("MEM0_API_KEY"),
    )

    app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

    @app.message(".*")
    def handle_message(message, say):
        user_id = message.get("user", "unknown")
        text = message.get("text", "")
        response = bot.on_message(user_id, text)
        say(response)

    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()


def main_discord():
    """Run the Discord bot."""
    try:
        import discord
    except ImportError:
        print("Install discord.py: pip install discord.py")
        return

    bot_instance = Mem0Bot(
        mem0_base_url=os.environ.get("MEM0_BASE_URL", "http://localhost:8000"),
        mem0_api_key=os.environ.get("MEM0_API_KEY"),
    )

    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        user_id = str(message.author.id)
        response = bot_instance.on_message(user_id, message.content)
        await message.channel.send(response)

    client.run(os.environ.get("DISCORD_BOT_TOKEN", ""))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    platform = os.environ.get("BOT_PLATFORM", "slack").lower()
    if platform == "discord":
        main_discord()
    else:
        main_slack()
