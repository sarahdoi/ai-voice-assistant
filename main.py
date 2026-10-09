"""Repository convenience entrypoint. Install agent first."""
from livekit.agents import cli
from sarjy.agent import server

if __name__ == "__main__":
    cli.run_app(server)
