#!/usr/bin/env node
/**
 * Capture web screenshots for a screen flow with Playwright.
 *
 *   node capture_web.mjs shots.json
 *
 * Needs `playwright` (bundled browsers) or `playwright-core` (+ an installed Chrome/Edge).
 * Install into a temporary folder if the project has neither:
 *   npm i --prefix /tmp/sf playwright-core && NODE_PATH=/tmp/sf/node_modules node capture_web.mjs shots.json
 *
 * shots.json:
 * {
 *   "baseUrl": "http://localhost:3000",
 *   "outDir": "screens",                       // relative to shots.json
 *   "viewport": { "width": 390, "height": 844 },
 *   "deviceScaleFactor": 2,
 *   "isMobile": true,                          // optional, mobile emulation (touch, meta viewport)
 *   "colorScheme": "light",                    // optional
 *   "setup": [ { "goto": "/login" }, { "fill": ["#email", "demo@example.com"] }, ... ],  // optional, runs once (e.g. log in)
 *   "screens": [
 *     { "id": "home", "path": "/" },
 *     { "id": "settings", "path": "/profile", "steps": [ { "click": "text=Settings" } ], "waitFor": "h1:has-text('Settings')" },
 *     { "id": "about", "path": "/about", "fullPage": true },
 *     { "id": "details", "path": "/show/42",
 *       "hotspots": [ { "to": "player", "selector": "button:has-text('Play')" },
 *                     { "to": "record-confirm", "selector": "text=Record" } ] }
 *   ]
 * }
 *
 * `hotspots` record where the element that leads to another screen sits on this screenshot (the
 * button, tab or row a user taps). They are written to hotspots.json next to shots.json, keyed
 * "<screen id>><target id>" (or "<id>><target>#<label>" when `label` is given), as fractions of
 * the screenshot. build_flow.py picks that file up and draws the arrows from those spots.
 *
 * Step types: goto, click, fill [selector, value], press [selector, key] or key, hover, waitFor (selector),
 * wait (ms), eval (JS string run in the page). Each screen starts from a fresh page in the same
 * context, so cookies/storage from `setup` are kept.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { createRequire } from 'node:module';

const file = process.argv[2];
if (!file) { console.error('usage: node capture_web.mjs shots.json'); process.exit(1); }
const cfg = JSON.parse(readFileSync(file, 'utf8'));
const outDir = resolve(dirname(resolve(file)), cfg.outDir || 'screens');
const hotspotsFile = resolve(dirname(resolve(file)), cfg.hotspotsFile || 'hotspots.json');
const hotspots = existsSync(hotspotsFile) ? JSON.parse(readFileSync(hotspotsFile, 'utf8')) : {};
mkdirSync(outDir, { recursive: true });

const require = createRequire(join(process.cwd(), 'noop.js'));
async function loadChromium() {
  for (const name of ['playwright', 'playwright-core']) {
    let mod = null;
    try { mod = require(name); } catch {}
    if (!mod) try { mod = await import(name); } catch {}
    const chromium = mod && (mod.chromium || mod.default?.chromium);
    if (chromium) return { chromium, core: name === 'playwright-core' };
  }
  console.error('Playwright not found. Install it, e.g.: npm i --prefix /tmp/sf playwright-core, then set NODE_PATH=/tmp/sf/node_modules');
  process.exit(1);
}

async function launch() {
  const { chromium, core } = await loadChromium();
  const tries = core ? ['chrome', 'msedge', 'chromium'] : [undefined, 'chrome', 'msedge'];
  for (const channel of tries) {
    try { return await chromium.launch(channel ? { channel } : {}); } catch (err) { if (channel === tries.at(-1)) throw err; }
  }
}

async function runSteps(page, steps = []) {
  for (const s of steps) {
    if (s.goto) await page.goto(new URL(s.goto, cfg.baseUrl).href, { waitUntil: 'networkidle' });
    else if (s.click) await page.locator(s.click).first().click();
    else if (s.fill) await page.locator(s.fill[0]).first().fill(s.fill[1]);
    else if (s.press) Array.isArray(s.press) ? await page.locator(s.press[0]).first().press(s.press[1]) : await page.keyboard.press(s.press);
    else if (s.hover) await page.locator(s.hover).first().hover();
    else if (s.waitFor) await page.locator(s.waitFor).first().waitFor({ timeout: 15000 });
    else if (s.wait) await page.waitForTimeout(s.wait);
    else if (s.eval) await page.evaluate(s.eval);
  }
}

const browser = await launch();
const context = await browser.newContext({
  viewport: cfg.viewport || { width: 1440, height: 900 },
  deviceScaleFactor: cfg.deviceScaleFactor || 1,
  isMobile: !!cfg.isMobile,
  hasTouch: !!cfg.isMobile,
  colorScheme: cfg.colorScheme || 'light',
  reducedMotion: 'reduce',
  locale: cfg.locale,
});
let failed = 0;
try {
  if (cfg.setup?.length) { const p = await context.newPage(); await runSteps(p, cfg.setup); await p.close(); }
  for (const shot of cfg.screens || []) {
    const page = await context.newPage();
    try {
      if (shot.path != null) await page.goto(new URL(shot.path, cfg.baseUrl).href, { waitUntil: 'networkidle' });
      await runSteps(page, shot.steps);
      if (shot.waitFor) await page.locator(shot.waitFor).first().waitFor({ timeout: 15000 });
      await page.evaluate(() => document.fonts && document.fonts.ready);
      await page.waitForTimeout(shot.settle ?? 400);
      if (shot.hotspots?.length) {
        const [W, H, sx, sy] = await page.evaluate((full) => full
          ? [document.documentElement.scrollWidth, document.documentElement.scrollHeight, scrollX, scrollY]
          : [innerWidth, innerHeight, 0, 0], !!shot.fullPage);
        for (const h of shot.hotspots) {
          const bb = await page.locator(h.selector).first().boundingBox().catch(() => null);
          const key = `${shot.id}>${h.to}` + (h.label ? `#${h.label}` : '');
          if (!bb) { console.error(`warn ${key}: no element for ${h.selector}`); continue; }
          const r = v => Math.round(v * 1e5) / 1e5;
          hotspots[key] = { x: r((bb.x + sx) / W), y: r((bb.y + sy) / H), w: r(bb.width / W), h: r(bb.height / H) };
        }
      }
      const out = join(outDir, `${shot.id}.png`);
      await page.screenshot({ path: out, fullPage: !!shot.fullPage, animations: 'disabled', caret: 'hide' });
      console.log(`ok   ${shot.id} -> ${out}`);
    } catch (err) {
      failed++;
      console.error(`FAIL ${shot.id}: ${err.message.split('\n')[0]}`);
    } finally { await page.close(); }
  }
} finally { await browser.close(); }
if (Object.keys(hotspots).length) {
  writeFileSync(hotspotsFile, JSON.stringify(hotspots, null, 2) + '\n');
  console.log(`hotspots -> ${hotspotsFile} (${Object.keys(hotspots).length})`);
}
process.exit(failed ? 2 : 0);
