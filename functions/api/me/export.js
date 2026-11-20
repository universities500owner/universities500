// Cloudflare Pages Function for /api/me/export. The logic and the settings it needs are in src/lib/account/handlers.js.
import { handleExport } from '../../../src/lib/account/handlers.js';

export const onRequest = ({ request, env }) => handleExport(request, env);
