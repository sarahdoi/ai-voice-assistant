"""LiveKit entrypoint: resolve identity, build the session, start the agent."""

import logging

from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, cli, room_io

from sarjy.config import get_settings
from sarjy.services.memory import NotImplementedMemoryService
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

    session = build_session(settings)
    agent = SarjyAgent(
        user_id=user_id,
        memory=NotImplementedMemoryService(),
        weather=NotImplementedWeatherService(),
    )
    await session.start(
        agent=agent, room=ctx.room,
        room_options=room_io.RoomOptions(participant_identity=user_id),
    )
    await session.generate_reply(instructions="Greet the user briefly as Sarjy.")


if __name__ == "__main__":
    cli.run_app(server)
