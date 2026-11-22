// The universities the SOP builder lets a student choose from: [slug, name, country]. About 20 KB. The page asks for one
// university's courses (sop-data/<slug>.json) only after the student has picked it.
import { all } from '../../../lib/data.js';

export function GET() {
  const list = all.map((u) => ({ s: u.slug, n: u.name, c: u.country })).sort((a, b) => a.n.localeCompare(b.n, 'en'));
  return new Response(JSON.stringify(list), { headers: { 'content-type': 'application/json; charset=utf-8' } });
}
