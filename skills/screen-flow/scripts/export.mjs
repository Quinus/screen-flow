#!/usr/bin/env node
/**
 * Export a built screen-flow page to PNG or PDF without opening a browser window.
 *
 *   node export.mjs screen-flow.html out.png [--scope all|view|<group-id>] [--theme light|dark] [--no-hotspots]
 *   node export.mjs screen-flow.html out.pdf [--theme light] [--no-group-pages]
 *
 * PDF: page 1 is the whole flow, then one page per group (unless --no-group-pages or a --scope is given).
 * Uses the same renderer as the Export button in the page. Needs `playwright` or `playwright-core`
 * (+ installed Chrome/Edge), like capture_web.mjs:
 *   npm i --prefix /tmp/sf playwright-core && NODE_PATH=/tmp/sf/node_modules node export.mjs ...
 */
import { writeFileSync } from 'node:fs';
import { resolve, extname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const args = process.argv.slice(2);
const [input, output] = args.filter(a => !a.startsWith('--') && !isOptValue(a));
function isOptValue(a) { const i = args.indexOf(a); return i > 0 && ['--scope', '--theme'].includes(args[i - 1]); }
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def; };
if (!input || !output) {
  console.error('usage: node export.mjs screen-flow.html out.png|out.pdf [--scope all|view|<group>] [--theme light|dark] [--no-hotspots] [--no-group-pages]');
  process.exit(1);
}
const format = extname(output).toLowerCase() === '.pdf' ? 'pdf' : 'png';

const require = createRequire(join(process.cwd(), 'noop.js'));
async function chromium() {
  for (const name of ['playwright', 'playwright-core']) {
    let mod = null;
    try { mod = require(name); } catch {}
    if (!mod) try { mod = await import(name); } catch {}
    const c = mod && (mod.chromium || mod.default?.chromium);
    if (c) return { c, core: name === 'playwright-core' };
  }
  console.error('Playwright not found. Install it, e.g.: npm i --prefix /tmp/sf playwright-core, then set NODE_PATH=/tmp/sf/node_modules');
  process.exit(1);
}
const { c, core } = await chromium();
let browser;
for (const channel of core ? ['chrome', 'msedge', 'chromium'] : [undefined, 'chrome', 'msedge']) {
  try { browser = await c.launch(channel ? { channel } : {}); break; } catch (err) { if (channel === 'chromium' || channel === 'msedge') throw err; }
}
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(pathToFileURL(resolve(input)).href);
  await page.waitForFunction(() => typeof window.screenFlowExport === 'function');
  if (args.includes('--no-hotspots')) await page.evaluate(() => { const b = document.getElementById('t-hotspots'); if (b && !b.hidden && b.getAttribute('aria-pressed') === 'true') b.click(); });
  const b64 = await page.evaluate(async (o) => {
    const blob = await window.screenFlowExport(o);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  }, { format, scope: opt('--scope', 'all'), theme: opt('--theme', 'light'), pagePerGroup: !args.includes('--no-group-pages') });
  const buf = Buffer.from(b64, 'base64');
  writeFileSync(output, buf);
  console.log(`wrote ${output} (${(buf.length / 1048576).toFixed(1)} MB)`);
} finally { await browser.close(); }
