"""LiveKit entrypoint: resolve identity, build the session, start the agent."""

import logging

import asyncpg
from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, cli, room_io

from sarjy.config import get_settings
from sarjy.services.memory import NotImplementedMemoryService, PostgresMemoryService
from sarjy.services.weather import NotImplementedWeatherService
from sarjy.tools import SarjyAgent
from sarjy.voice.factory import build_session

logger = logging.getLogger("sarjy")

load_dotenv(".env.local")
load_dotenv(".env")
server = AgentServer()


@server.rtc_session(agent_name="sarjy")
async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    await ctx.connect()

    # Identity comes from the signed LiveKit token, never from the model.
    participant = await ctx.wait_for_participant()
    user_id = participant.identity
    logger.info("session started")

    memory = NotImplementedMemoryService()
    if settings.database_url:
        try:
            pool = await asyncpg.create_pool(
                settings.database_url.get_secret_value(),
                min_size=1,
                max_size=2,
                timeout=settings.db_timeout_s,
                command_timeout=settings.db_timeout_s,
            )
            ctx.add_shutdown_callback(pool.close)
            memory = PostgresMemoryService(pool, fault_write=settings.fault_db_write)
        except (asyncpg.PostgresError, OSError, TimeoutError):
            logger.warning("Database connection unavailable; memory tools will report unavailable")

    session = build_session(settings)
    agent = SarjyAgent(
        user_id=user_id,
        memory=memory,
        weather=NotImplementedWeatherService(),
    )
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(participant_identity=user_id),
    )
    await session.generate_reply(instructions="Greet the user briefly as Sarjy.")


if __name__ == "__main__":
    cli.run_app(server)
