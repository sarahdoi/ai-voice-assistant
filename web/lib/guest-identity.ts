/**
 * Anonymous guest identity.
 *
 * The server creates a random UUID on the first visit and keeps it in an
 * HttpOnly cookie. Every later visit from the same browser reuses it, and it
 * becomes the LiveKit participant identity, which the agent uses as user_id.
 *
 * Nothing is written to the database here: a memory row only exists once the
 * user asks the assistant to remember something.
 */

export const GUEST_ID_COOKIE = 'sarjy_uid';
export const GUEST_ID_MAX_AGE_SECONDS = 60 * 60 * 24 * 365; // one year

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type GuestIdentity = { userId: string; isNew: boolean };

/**
 * Reuse the cookie's ID when it is a well-formed UUID; otherwise issue a new one.
 * A tampered or malformed cookie is treated as "no identity", never trusted.
 */
export function resolveGuestIdentity(cookieValue: string | undefined): GuestIdentity {
  if (cookieValue && UUID_V4.test(cookieValue)) {
    return { userId: cookieValue.toLowerCase(), isNew: false };
  }
  return { userId: crypto.randomUUID(), isNew: true };
}

export const guestIdCookieOptions = {
  httpOnly: true, // page scripts cannot read or change it
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const,
  path: '/',
  maxAge: GUEST_ID_MAX_AGE_SECONDS,
};
