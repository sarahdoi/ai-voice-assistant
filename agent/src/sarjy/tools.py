"""Thin adapters that expose services to the model.

Design rules:
- Tools never take a user_id argument. The user_id is bound at construction
  from the verified LiveKit participant identity, so the model cannot choose it.
- Tools return ToolResult JSON so the model confirms only real successes.
"""

from livekit.agents import Agent, function_tool

from sarjy.services.memory import MemoryService
from sarjy.services.weather import WeatherService

INSTRUCTIONS = """\
You are Sarjy, a warm, concise voice assistant.
Only say you saved, changed or forgot something when the tool result has ok=true.
Never state weather values that are not in the weather tool's data.
If a tool fails, say so plainly and do not guess.
"""


class SarjyAgent(Agent):
    def __init__(self, user_id: str, memory: MemoryService, weather: WeatherService) -> None:
        super().__init__(instructions=INSTRUCTIONS)
        self._user_id = user_id
        self._memory = memory
        self._weather = weather

    @function_tool
    async def remember(self, key: str, value: str) -> str:
        """Save a personal fact or preference the user explicitly stated.

        Args:
            key: short snake_case name, e.g. favorite_color
            value: the value the user gave
        """
        return (await self._memory.remember(self._user_id, key, value)).model_dump_json()

    @function_tool
    async def recall(self, key: str | None = None) -> str:
        """Look up a saved fact, or all saved facts when key is omitted."""
        return (await self._memory.recall(self._user_id, key)).model_dump_json()

    @function_tool
    async def correct(self, key: str, new_value: str) -> str:
        """Change a fact the user previously saved."""
        return (await self._memory.correct(self._user_id, key, new_value)).model_dump_json()

    @function_tool
    async def forget(self, key: str) -> str:
        """Delete a saved fact at the user's request."""
        return (await self._memory.forget(self._user_id, key)).model_dump_json()

    @function_tool
    async def get_weather(self, city: str) -> str:
        """Get current conditions and a short forecast for a city."""
        return (await self._weather.get_forecast(city)).model_dump_json()
