"""Provider construction; switching configurations still requires behavior tests."""

from livekit.agents import AgentSession, TurnHandlingOptions, inference

from sarjy.config import Settings, VoiceProvider


def build_session(settings: Settings) -> AgentSession:
    match settings.voice_provider:
        case VoiceProvider.LIVEKIT_PIPELINE:
            return AgentSession(
                stt=inference.STT(model=settings.stt_model, language=settings.language),
                llm=inference.LLM(model=settings.llm_model),
                tts=inference.TTS(model=settings.tts_model, voice=settings.tts_voice),
                turn_handling=TurnHandlingOptions(turn_detection=inference.TurnDetector()),
            )
        case VoiceProvider.GEMINI_LIVE:
            from livekit.plugins import google

            api_key = settings.google_api_key
            if not api_key:
                raise ValueError("GOOGLE_API_KEY is required for gemini_live")
            return AgentSession(
                llm=google.realtime.RealtimeModel(
                    model=settings.gemini_model,
                    voice=settings.gemini_voice,
                    api_key=api_key.get_secret_value() if api_key else None,
                )
            )
        case VoiceProvider.DEEPGRAM_CASCADE:
            raise NotImplementedError("Deepgram cascade is stretch scope.")
    raise ValueError(f"Unknown voice provider: {settings.voice_provider}")
