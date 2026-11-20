// Cloudflare Pages Function for /api/auth/logout. The logic and the settings it needs are in src/lib/account/handlers.js.
import { handleLogout } from '../../../src/lib/account/handlers.js';

export const onRequest = ({ request, env }) => handleLogout(request, env);
