import { type NextRequest, NextResponse } from 'next/server';
import {
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
  type VideoGrant,
} from 'livekit-server-sdk';
import { GUEST_ID_COOKIE, guestIdCookieOptions, resolveGuestIdentity } from '@/lib/guest-identity';

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
};

const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL;
const AGENT_NAME = process.env.AGENT_NAME ?? 'sarjy';

// Never cache: every call mints a fresh, short-lived token.
export const revalidate = 0;

/**
 * Issues a LiveKit token for this browser's guest identity.
 *
 * Identity is decided here, on the server, from the HttpOnly cookie. The browser
 * cannot choose it, and the agent reads it from the signed token as user_id.
 * Agent dispatch is also fixed here; any room_config sent by the client is ignored.
 */
export async function POST(req: NextRequest) {
  if (!LIVEKIT_URL || !API_KEY || !API_SECRET) {
    console.error(
      'LiveKit env vars are missing (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)'
    );
    return new NextResponse('Voice service is not configured', { status: 500 });
  }

  // Only our own pages may request tokens. Browsers always send Origin on POST.
  const origin = req.headers.get('origin');
  if (origin !== null && origin !== req.nextUrl.origin) {
    return new NextResponse('Forbidden', { status: 403 });
  }

  const { userId, isNew } = resolveGuestIdentity(req.cookies.get(GUEST_ID_COOKIE)?.value);
  const roomName = `sarjy-${crypto.randomUUID()}`;
  const participantName = 'Guest';

  try {
    const participantToken = await createParticipantToken(userId, participantName, roomName);
    const data: ConnectionDetails = {
      serverUrl: LIVEKIT_URL,
      roomName,
      participantName,
      participantToken,
    };

    const response = NextResponse.json(data, { headers: { 'Cache-Control': 'no-store' } });
    // Set on every call so the one-year expiry slides forward with each visit.
    response.cookies.set(GUEST_ID_COOKIE, userId, guestIdCookieOptions);
    if (isNew) console.info('issued new guest identity');
    return response;
  } catch (error) {
    console.error('failed to create LiveKit token', error);
    return new NextResponse('Could not start a voice session', { status: 500 });
  }
}

function createParticipantToken(identity: string, name: string, roomName: string): Promise<string> {
  const at = new AccessToken(API_KEY, API_SECRET, { identity, name, ttl: '15m' });
  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canPublishData: true,
    canSubscribe: true,
  };
  at.addGrant(grant);
  at.roomConfig = new RoomConfiguration({
    agents: [new RoomAgentDispatch({ agentName: AGENT_NAME })],
  });
  return at.toJwt();
}
