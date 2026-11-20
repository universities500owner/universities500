// Cloudflare Pages Function for /api/auth/config. The logic and the settings it needs are in src/lib/account/handlers.js.
import { handleConfig } from '../../../src/lib/account/handlers.js';

export const onRequest = ({ request, env }) => handleConfig(request, env);
