// The reading mode: an optional Meaning Model add-on that gives a book's text as the model asks for it, so a reader can
// "read a little, think when a new idea comes up, tend to the graph" in one session. It is not part of the Meaning
// Model. Load it by naming this file's absolute path in MEANING_MODEL_ADDONS, beside storytelling, and its parameter
// file in READING_MODE_PARAMETERS. README.md describes the parameters.
//
// life_reading_next gives the next whole paragraphs, as many as asked for, by paragraphs or by characters, and writes
// them to a file, so life_document_import can take that sourcePath. life_reading_status gives the progress and the
// last text again, so a resumed session can pick up. Only text already handed out leaves this module: the source's
// path stays in the parameter file, which only the server's settings name.
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';

const chars = (text) => [...text].length; // code points, as the parameter file and the paper's runs count them

// The paper's seeded perspective order: Python's random.Random(seed).shuffle, reproduced exactly (MT19937).
function pythonRandom(seed) {
  const mt = new Uint32Array(624);
  let index = 624;
  mt[0] = 19650218;
  for (let i = 1; i < 624; i++) mt[i] = Math.imul(1812433253, mt[i - 1] ^ (mt[i - 1] >>> 30)) + i;
  const key = [];
  for (let rest = BigInt(Math.abs(seed)); key.length === 0 || rest > 0n; rest >>= 32n) key.push(Number(rest & 0xffffffffn));
  let i = 1, j = 0;
  for (let k = Math.max(624, key.length); k; k--) {
    mt[i] = (mt[i] ^ Math.imul(mt[i - 1] ^ (mt[i - 1] >>> 30), 1664525)) + key[j] + j;
    i++; j++;
    if (i >= 624) { mt[0] = mt[623]; i = 1; }
    if (j >= key.length) j = 0;
  }
  for (let k = 623; k; k--) {
    mt[i] = (mt[i] ^ Math.imul(mt[i - 1] ^ (mt[i - 1] >>> 30), 1566083941)) - i;
    i++;
    if (i >= 624) { mt[0] = mt[623]; i = 1; }
  }
  mt[0] = 0x80000000;
  const next = () => {
    if (index >= 624) {
      for (let k = 0; k < 624; k++) {
        const y = (mt[k] & 0x80000000) | (mt[(k + 1) % 624] & 0x7fffffff);
        mt[k] = mt[(k + 397) % 624] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      index = 0;
    }
    let y = mt[index++];
    y ^= y >>> 11; y ^= (y << 7) & 0x9d2c5680; y ^= (y << 15) & 0xefc60000; y ^= y >>> 18;
    return y >>> 0;
  };
  const below = (n) => { const bits = n.toString(2).length; let r; do r = next() >>> (32 - bits); while (r >= n); return r; };
  return {
    shuffle(list) {
      for (let k = list.length - 1; k > 0; k--) { const pick = below(k + 1); [list[k], list[pick]] = [list[pick], list[k]]; }
      return list;
    },
  };
}

export function perspectivesFor(stretch, { perspectives, perspectives_per_stretch: count, seed }) {
  const random = pythonRandom(seed), order = [];
  while (order.length < count * stretch) order.push(...random.shuffle([...perspectives]));
  return order.slice(count * (stretch - 1), count * stretch);
}

// How many paragraphs from start come closest to size characters.
export function paragraphsNear(lengths, start, size) {
  let best = 1, total = 0;
  for (let count = 1; start + count <= lengths.length; count++) {
    total += lengths[start + count - 1];
    const bestTotal = lengths.slice(start, start + best).reduce((sum, length) => sum + length, 0);
    if (Math.abs(total - size) <= Math.abs(bestTotal - size)) best = count;
    if (total > size) break;
  }
  return best;
}

export function loadReading(file) {
  if (!file || !isAbsolute(file)) throw new Error('The reading mode needs READING_MODE_PARAMETERS, the absolute path of its parameter file.');
  const settings = { stretch_chars: 4000, time_limit_hours: 4, perspectives: [], perspectives_per_stretch: 2, seed: 20261009, stop_at_chars: 0,
    ...JSON.parse(readFileSync(file, 'utf8')) };
  if (!settings.source) throw new Error(`The reading parameters in ${file} name no source.`);
  const source = resolve(dirname(file), settings.source);
  const text = readFileSync(source, 'utf8');
  const paragraphs = text.split(/\n\s*\n/u).map((paragraph) => paragraph.trim()).filter(Boolean);
  const store = process.env.LIFE_SIM_STATE_FILE;
  const folder = settings.state_folder ? resolve(dirname(file), settings.state_folder) : store && `${resolve(store)}.reading`;
  if (!folder) throw new Error('The reading mode keeps its state beside the store: set LIFE_SIM_STATE_FILE, or state_folder in the parameters.');
  return { settings, paragraphs, lengths: paragraphs.map(chars), sourceSha256: createHash('sha256').update(text).digest('hex'), folder };
}

export function createReading({ settings, paragraphs, lengths, sourceSha256, folder }) {
  const total = lengths.reduce((sum, length) => sum + length, 0);
  const path = join(folder, 'reading-state.json');
  mkdirSync(join(folder, 'text'), { recursive: true });
  const state = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : { sourceSha256, position: 0, reads: [], sessions: [] };
  if (state.sourceSha256 !== sourceSha256) throw new Error(`The reading state in ${folder} belongs to another source text.`);
  const limit = settings.stop_at_chars || null;
  const read = (position = state.position) => lengths.slice(0, position).reduce((sum, length) => sum + length, 0);
  const ended = () => (state.position >= paragraphs.length ? 'book' : limit && read() >= limit ? 'limit' : null);
  const save = () => {
    state.sessions.at(-1).last = Date.now() / 1000;
    Object.assign(state, { limit, ended: ended() });
    writeFileSync(`${path}.tmp`, `${JSON.stringify(state, null, 1)}\n`);
    renameSync(`${path}.tmp`, path);
  };
  const progress = () => {
    const minutes = state.sessions.reduce((sum, session) => sum + session.last - session.start, 0) / 60;
    return `So far: ${read().toLocaleString('en-US')} of ${total.toLocaleString('en-US')} characters (${Math.round(100 * read() / total)}%), ` +
      `paragraph ${state.position} of ${paragraphs.length}. Time used: ${Math.round(minutes)} of about ${Math.round(settings.time_limit_hours * 60)} minutes.`;
  };
  const ending = () => ({ book: 'The text ends here: this is the end of the book.',
    limit: 'That is all the text for this session. The reading pauses here, and the book goes on: finish your thinking on what you have read.' })[ended()] ?? '';
  const describe = (entry, text) => {
    const span = entry.to === entry.from + 1 ? `paragraph ${entry.to}` : `paragraphs ${entry.from + 1} to ${entry.to}`;
    const names = entry.workers.length < 3 ? entry.workers.join(' and ') : `${entry.workers.slice(0, -1).join(', ')} and ${entry.workers.at(-1)}`;
    const workers = entry.workers.length ? `\nWorkers for this stretch: ${names}.` : '';
    return `Read ${entry.read}: ${span} of ${paragraphs.length}, ${entry.chars.toLocaleString('en-US')} characters, also in ${entry.file}\n${progress()}${workers}\n\n${text}`;
  };
  const now = Date.now() / 1000;
  state.sessions.push({ start: now, last: now });
  save();
  process.on('exit', save);

  return {
    next({ paragraphs: wanted, chars: size } = {}) {
      if (ended()) { save(); return `${ending()}\n${progress()}`; }
      const start = state.position;
      const count = wanted ?? (size ? paragraphsNear(lengths, start, size) : 1);
      let end = Math.min(start + Math.max(1, count), paragraphs.length);
      while (limit && end > start + 1 && read(end - 1) >= limit) end--;
      const text = paragraphs.slice(start, end).join('\n\n');
      const number = state.reads.length + 1;
      const file = join(folder, 'text', `read-${String(number).padStart(3, '0')}.txt`);
      writeFileSync(file, `${text}\n`);
      // A read names the Workers of every stretch it covers, so a long read skips no one.
      const first = Math.floor(read(start) / settings.stretch_chars) + 1, last = Math.floor((read(end) - 1) / settings.stretch_chars) + 1;
      const stretches = Array.from({ length: last - first + 1 }, (_, k) => first + k);
      const workers = settings.perspectives.length ? [...new Set(stretches.flatMap((stretch) => perspectivesFor(stretch, settings)))] : [];
      const entry = { read: number, from: start, to: end, chars: chars(text), file, stretches, workers, at: Date.now() / 1000, asked: { paragraphs: wanted, chars: size } };
      state.reads.push(entry);
      state.position = end;
      save();
      return describe(entry, text) + (ending() ? `\n\n${ending()}` : '');
    },
    status() {
      save();
      const entry = state.reads.at(-1);
      if (!entry) return `Nothing read yet: life_reading_next gives the first text.\n${progress()}`;
      return `The last text you read follows.\n${describe(entry, paragraphs.slice(entry.from, entry.to).join('\n\n'))}` + (ending() ? `\n\n${ending()}` : '');
    },
  };
}

export function register(server, service, { z }) {
  const reading = createReading(loadReading(process.env.READING_MODE_PARAMETERS));
  const reply = (text) => ({ content: [{ type: 'text', text }] });
  server.registerTool('life_reading_next', {
    description: 'Read the next part of the book, as much or as little as you want. Give paragraphs, or chars for the whole paragraphs that come closest to that many characters; with neither, one paragraph. Returns the text, the path of a file holding it for life_document_import, how far you have got, the time used, and the Workers for this stretch. Nothing else gives the book\'s text.',
    inputSchema: z.object({
      paragraphs: z.number().int().min(1).optional().describe('How many paragraphs to read.'),
      chars: z.number().int().min(1).optional().describe('About how many characters to read, in whole paragraphs.'),
    }).strict(),
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
  }, async (input) => reply(reading.next(input)));
  server.registerTool('life_reading_status', {
    description: 'How far you have got in the book and the time used, with the last text read again and its Workers.',
    inputSchema: z.object({}).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }, async () => reply(reading.status()));
}
