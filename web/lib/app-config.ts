/**
 * Branding, set per deployment. NEXT_PUBLIC_ values are read at build time, so
 * rebuild after changing them. Keep APP_NAME in step with the agent's APP_NAME
 * so the assistant introduces itself with the name shown on screen.
 */
export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME?.trim() || 'Sarjy';
