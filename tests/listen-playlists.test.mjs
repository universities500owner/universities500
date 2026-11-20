import test from 'node:test';
import assert from 'node:assert/strict';
import { guideClips, withHashes } from '../src/lib/listen.js';
import { buildHub, pickLists, fmtLength } from '../src/lib/listen-playlists.js';

const cfg = { version: 1, provider: 'elevenlabs', model: 'eleven_v4', voiceId: 'V', tonePrefix: '[warmly]', format: 'mp3_44100_64', settings: {}, audioBase: 'https://a.test/' };
const block = (text) => ({ t: 'p', runs: [{ t: text }] });
const guide = (slug, name, keys) => ({
  slug, name,
  sections: keys.map((k) => ({ key: k, title: `${name} ${k}`, blocks: [block(`${name} says something about ${k}.`)] })),
});
const guides = [guide('a', 'Alpha', ['overview', 'costs', 'visa']), guide('b', 'Beta', ['overview', 'costs', 'work', 'post-study']), guide('c', 'Gamma', ['overview', 'costs', 'visa'])];
const manifestFor = (list) => {
  const clips = {};
  for (const g of list) for (const c of withHashes(guideClips(g), cfg)) clips[c.hash] = { seconds: 60, bytes: 1, chars: 1 };
  return { clips };
};

test('lists: all guides, the topics found in two or more guides, then each guide', () => {
  const hub = buildHub(guides, manifestFor(guides), cfg);
  // only Beta has work rights, so there is no work list; visas are in two guides, which is enough
  assert.deepEqual(hub.lists.map((l) => l.id), ['all', 'costs', 'visa', 'g:a', 'g:b', 'g:c']);
  assert.equal(hub.base, 'https://a.test');
});

test('the closing reminder plays once, at the end of the all-guides list only', () => {
  const hub = buildHub(guides, manifestFor(guides), cfg);
  const all = hub.lists.find((l) => l.id === 'all');
  const closing = withHashes(guideClips(guides[0]), cfg).find((c) => c.id.endsWith('#closing')).hash;
  assert.equal(all.items.filter((i) => i[0] === closing).length, 1);
  assert.equal(all.items[all.items.length - 1][0], closing);
  assert.equal(hub.lists.find((l) => l.id === 'costs').items.some((i) => i[0] === closing), false);
  // each guide's own list keeps its closing
  assert.equal(hub.lists.find((l) => l.id === 'g:a').items.some((i) => i[0] === closing), true);
});

test('a topic list takes that section from each country and groups by country', () => {
  const hub = buildHub(guides, manifestFor(guides), cfg);
  const costs = hub.lists.find((l) => l.id === 'costs');
  assert.equal(costs.groups, 3);
  assert.deepEqual(costs.items.map((i) => hub.titles[i[3]]), ['Alpha: Cost of studying', 'Beta: Cost of studying', 'Gamma: Cost of studying']);
  assert.deepEqual(costs.items.map((i) => i[2]), [0, 1, 2]);
  assert.equal(costs.length, '3\u00a0min');
});

test('a guide whose audio is not all ready is left out, and with nothing ready there is no hub', () => {
  const partial = manifestFor([guides[0], guides[2]]);
  const hub = buildHub(guides, partial, cfg);
  assert.deepEqual(hub.lists.filter((l) => l.id.startsWith('g:')).map((l) => l.id), ['g:a', 'g:c']);
  assert.equal(buildHub(guides, { clips: {} }, cfg), null);
  assert.equal(buildHub(guides, manifestFor(guides), { ...cfg, voiceId: '' }), null);
});

test('pickLists keeps only the lists asked for and renumbers their titles', () => {
  const hub = buildHub(guides, manifestFor(guides), cfg);
  const small = pickLists(hub, ['costs']);
  assert.equal(small.lists.length, 1);
  assert.equal(small.titles.length, 3);
  assert.deepEqual(small.lists[0].items.map((i) => small.titles[i[3]]), ['Alpha: Cost of studying', 'Beta: Cost of studying', 'Gamma: Cost of studying']);
  assert.equal(pickLists(hub, ['nope']), null);
});

test('fmtLength', () => {
  assert.equal(fmtLength(20), '1\u00a0min');
  assert.equal(fmtLength(13 * 60 + 20), '13\u00a0min');
  assert.equal(fmtLength(3 * 3600 + 12 * 60), '3\u00a0h 12\u00a0min');
});
