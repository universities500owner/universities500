// One university's courses, with only the facts the SOP builder may use: course length, intakes and the IELTS overall score,
// each with the official page it was read from and the day it was last checked. A course with no such fact is still listed
// (the student can still write about it); the draft then has nothing to say about it and shows a gap instead.
import { all } from '../../../lib/data.js';
import { items, ieltsScore } from '../../../lib/courses.js';
import subjectDef from '../../../data/subjects.json';

const GROUP = new Map(subjectDef.subjects.map((s) => [s.id, s.group]));
const byUni = new Map();
for (const i of items) (byUni.get(i.uni) || byUni.set(i.uni, []).get(i.uni)).push(i);

export function getStaticPaths() {
  return all.map((u) => ({ params: { slug: u.slug }, props: { u } }));
}

export function GET({ props }) {
  const { u } = props;
  const courses = (byUni.get(u.slug) || [])
    .map((i) => ({
      id: `crs:${i.uni}/${i.slug}`,
      n: i.degree && i.degree.length <= 140 ? i.degree : i.name,
      lv: i.level === 'Master' ? "Master's" : "Bachelor's",
      g: GROUP.get((i.sj || [])[0]) || '',
      d: i.duration ? i.duration.display : '',
      m: i.intakes && i.intakes.months ? i.intakes.months : [],
      ie: ieltsScore(i),
      u: i.url || '',
      on: i.lastVerified || '',
    }))
    .sort((a, b) => a.n.localeCompare(b.n, 'en'));
  return new Response(JSON.stringify({ s: u.slug, n: u.name, c: u.country, courses }), { headers: { 'content-type': 'application/json; charset=utf-8' } });
}
