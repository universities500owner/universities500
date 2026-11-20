// Cloudflare Pages Function for /api/auth/verify. The logic and the settings it needs are in src/lib/account/handlers.js.
import { handleVerify } from '../../../src/lib/account/handlers.js';

export const onRequest = ({ request, env }) => handleVerify(request, env);
