// Cloudflare Pages Function for /api/auth/request. The logic and the settings it needs are in src/lib/account/handlers.js.
import { handleRequestCode } from '../../../src/lib/account/handlers.js';

export const onRequest = ({ request, env }) => handleRequestCode(request, env);
