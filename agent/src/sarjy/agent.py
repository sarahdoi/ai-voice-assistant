"""LiveKit entrypoint: resolve identity, build the session, start the agent."""

import asyncio
import contextlib
import logging

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import AgentServer, JobContext, cli, room_io

from sarjy.config import get_settings
from sarjy.events import MEMORY_RPC_METHOD, RoomEventSink
from sarjy.services.memory import DeferredMemoryService, NotImplementedMemoryService
from sarjy.services.weather import (
    FallbackWeatherService,
    MetNorwayWeatherService,
    OpenMeteoWeatherService,
)
from sarjy.storage import connect_memory_pool
from sarjy.tools import SarjyAgent
from sarjy.voice.factory import build_session

logger = logging.getLogger("sarjy")

# How long the greeting waits for saved facts before going ahead without them.
PRELOAD_WAIT_S = 1.5

load_dotenv(".env.local")
load_dotenv(".env")
server = AgentServer()


@server.rtc_session(agent_name=get_settings().agent_name)
async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    await ctx.connect()

    # Identity comes from the signed LiveKit token, never from the model.
    participant = await ctx.wait_for_participant()
    user_id = participant.identity
    logger.info("session started")

    # Start connecting now; a sleeping database wakes while the session starts.
    memory = NotImplementedMemoryService()
    if settings.database_url:
        deferred = DeferredMemoryService(
            connect_memory_pool(settings), fault_write=settings.fault_db_write
        )
        ctx.add_shutdown_callback(deferred.aclose)
        memory = deferred

    weather_client = httpx.AsyncClient(timeout=settings.weather_timeout_s)
    ctx.add_shutdown_callback(weather_client.aclose)
    session = build_session(settings)
    primary = OpenMeteoWeatherService(
        weather_client,
        geocoding_url=str(settings.weather_geocoding_url),
        forecast_url=str(settings.weather_forecast_url),
        fault=settings.fault_weather,
    )
    weather = FallbackWeatherService(
        primary,
        MetNorwayWeatherService(
            primary,
            url=str(settings.weather_fallback_url),
            user_agent=settings.weather_user_agent,
        ),
    )
    agent = SarjyAgent(
        user_id=user_id,
        memory=memory,
        weather=weather,
        events=RoomEventSink(ctx.room, user_id),
        name=settings.app_name,
    )
    # Load saved facts right away, while the voice session is still starting, so
    # they are ready for the greeting and for the memory panel before anyone asks.
    preload = agent.start_preloading_memories()

    # The UI asks for the saved facts when it opens. Only this session's user may ask.
    @ctx.room.local_participant.register_rpc_method(MEMORY_RPC_METHOD)
    async def memory_snapshot(data: rtc.RpcInvocationData) -> str:
        if data.caller_identity != user_id:
            raise rtc.RpcError(rtc.RpcError.ErrorCode.APPLICATION_ERROR, "Not your memory.")
        return (await agent.memory_snapshot()).model_dump_json()

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(participant_identity=user_id),
    )
    # Wait briefly so a returning user can be greeted by name; if storage is slow,
    # greet now and keep loading.
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(asyncio.shield(preload), timeout=PRELOAD_WAIT_S)
    await session.generate_reply(
        instructions=f"Greet the user briefly as {settings.app_name}. "
        "If you know their name, use it."
    )


def main() -> None:
    """Command-line entry point: `voice-agent dev` locally, `voice-agent start` in production."""
    cli.run_app(server)


if __name__ == "__main__":
    main()
