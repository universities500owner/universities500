# Listen audio

Each destination guide and article can have a "Listen to this guide" button that plays it as a podcast-style recording.

## How it works

1. `src/lib/listen.js` turns a guide or article into short clips (one per section), written the way they should be spoken.
2. Each clip gets a fingerprint from its exact text plus the voice settings. The audio file is named after that fingerprint.
3. `scripts/listen/generate.mjs` voices only the clips that have no audio yet, and records them in `src/data/listen/manifest.json`.
4. At build time a page looks up every clip of itself in the manifest. If all are there, the button shows. If anyone edits a
   sentence, that clip's fingerprint changes, the page's button hides, and the next run of the workflow makes only that clip again.
5. The audio files live in Cloudflare R2, not in this repository (about 250 MB for everything).

## One-time setup

1. **ElevenLabs.** Create a key at elevenlabs.io > Developers > API Keys. Allow only *Text to Speech* (and *Voices: read*), and
   set a monthly character limit on the key. Pick a voice in the Voice Library, add it to *My Voices*, copy its Voice ID into
   `voiceId` in `src/data/listen/config.json`. Changing the voice later makes all audio count as new (and be made again).
2. **Cloudflare R2.** Create a bucket (for example `universities500-audio`). Under the bucket's Settings > Public access, connect the
   custom domain `audio.universities500.com`. Then R2 > Manage API tokens > Create token with *Object Read & Write* on that bucket.
   Keep the Account ID, Access Key ID and Secret Access Key it shows.
3. **GitHub** (Settings > Secrets and variables > Actions). Secrets: `ELEVENLABS_API_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`. Variable: `R2_BUCKET`. Optional variables: `LISTEN_MONTHLY_CHARS` (default 700,000) and
   `LISTEN_AUTO` = `on` (make new audio automatically when content changes; leave off until a manual run worked).

## First run

Actions > *Listen audio* > Run workflow, `only` = `guide:canada`, leave *dry_run* ticked: it prints the count and a cost estimate.
Then untick *dry_run* and run again. When it finishes, the manifest is committed to `main` and the Canada guide shows its button
after the next deploy. Then run again with `only` blank for everything else.

## Locally

`node scripts/listen/generate.mjs --dry-run` counts and estimates. `--provider stub` makes silent MP3s of the right length, for
testing the player (set `PUBLIC_LISTEN_BASE` for the build to point at them). Do not commit a manifest made with the stub.
