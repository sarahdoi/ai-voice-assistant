import { createHmac, randomUUID, timingSafeEqual } from 'node:crypto';

/**
 * Anonymous guest identity.
 *
 * The server creates a random UUID on the first visit and keeps it in an
 * HttpOnly cookie, signed with a server-only secret (HMAC-SHA256). Every later
 * visit from the same browser reuses it, and it becomes the LiveKit participant
 * identity, which the agent uses as user_id.
 *
 * Why signed: the ID itself is not secret (it is the LiveKit identity and the
 * key in the database), so a bare ID in a cookie could be forged by anyone who
 * learned it. Only this server can produce a valid signature, so a token is
 * issued only to the browser the ID was given to.
 *
 * Nothing is written to the database here: a memory row only exists once the
 * user asks the assistant to remember something.
 */

export const GUEST_ID_COOKIE = 'sarjy_uid';
export const GUEST_ID_MAX_AGE_SECONDS = 60 * 60 * 24 * 365; // one year
export const MIN_SECRET_LENGTH = 32;

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export type GuestIdentity = {
  userId: string;
  /** The signed value to (re)set in the cookie. */
  cookie: string;
  isNew: boolean;
};

function signature(userId: string, secret: string): string {
  return createHmac('sha256', secret).update(`guest:v1:${userId}`).digest('base64url');
}

export function signGuestId(userId: string, secret: string): string {
  return `${userId}.${signature(userId, secret)}`;
}

/** The user ID in a signed cookie, or null if it is missing, malformed or forged. */
export function verifyGuestCookie(value: string | undefined, secret: string): string | null {
  if (!value) return null;
  const dot = value.indexOf('.');
  if (dot < 0) return null;
  const userId = value.slice(0, dot);
  if (!UUID_V4.test(userId)) return null;
  const given = Buffer.from(value.slice(dot + 1));
  const expected = Buffer.from(signature(userId, secret));
  return given.length === expected.length && timingSafeEqual(given, expected) ? userId : null;
}

/**
 * Reuse the cookie's ID when its signature is valid; otherwise issue a new one.
 * A tampered, unsigned or malformed cookie is treated as "no identity", never trusted.
 */
export function resolveGuestIdentity(
  cookieValue: string | undefined,
  secret: string
): GuestIdentity {
  const existing = verifyGuestCookie(cookieValue, secret);
  const userId = existing ?? randomUUID();
  return { userId, cookie: signGuestId(userId, secret), isNew: existing === null };
}

export const guestIdCookieOptions = {
  httpOnly: true, // page scripts cannot read or change it
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const,
  path: '/',
  maxAge: GUEST_ID_MAX_AGE_SECONDS,
};
