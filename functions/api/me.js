// Cloudflare Pages Function for /api/me. The logic and the settings it needs are in src/lib/account/handlers.js.
import { handleMe } from '../../src/lib/account/handlers.js';

export const onRequest = ({ request, env }) => handleMe(request, env);
