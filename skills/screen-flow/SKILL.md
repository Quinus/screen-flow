---
name: screen-flow
description: Map an app's navigation as a screen flow built from real screenshots, delivered as one standalone HTML file with an infinite, zoomable canvas. Screens are placed as cards with arrows between them, the main navigation is grouped together, and each feature's screens get their own group. Works for one feature or the whole app, on web, iOS, Android or desktop. Use when the user asks for a screen flow, user flow, navigation map, flow diagram, sitemap with screenshots, "map all screens", "how do you get to X", or wants to document or review an app's or feature's navigation visually.
---

# Screen flow

Make a standalone HTML screen flow from **real screenshots** of the running app. There are three parts:

1. **Map** the screens and the links between them, mostly from the code, and write them in `flow.json`.
2. **Capture** each screen in the running app with the agent tools you have. For every link, also
   record its **hotspot**: where the button, tab or row that triggers it sits on the screenshot.
   The viewer then starts each arrow at that spot.
3. **Build** the page with `scripts/build_flow.py`. The script does the layout, the arrows, pan and
   zoom, and embeds the images. Never write the viewer HTML yourself. Spend your effort on a correct
   map and good screenshots.

Paths below are relative to this skill's folder (the folder this file is in).

## 0. Scope and output

- **Scope**: `feature` (one feature or flow, such as "checkout" or "parental control") or `app` (all
  screens). If the request does not say, use the feature they named. With no feature named, use the
  whole app.
- **Feature scope**: include the entry screens that lead into the feature, such as the tab or home
  screen with the button that opens it. Put them in a small `nav` group so readers can see where the
  feature starts. Do not capture the rest of the app.
- **Output folder**: use what the user asked for. Otherwise use `screen-flows/<slug>/` in the project:
  `flow.json`, `screens/<screen-id>.png`, and `screen-flow.html`. Before writing into the repo, check
  whether `screen-flows/` should be added to `.gitignore`. The PNGs can be large.

## 1. Map the navigation (before any screenshots)

Read the code to build an inventory. Do not click around at random. Where to look:

| Stack | Where navigation lives |
|---|---|
| React Router / TanStack Router | route config, `createBrowserRouter`, `<Route>`, `routes/` folder |
| Next.js / Remix / Nuxt / SvelteKit | file-based routes: `app/`, `pages/`, `routes/`, `src/routes/` |
| Angular / Vue | `*-routing.module.ts`, `router/index.ts` |
| SwiftUI / UIKit | `NavigationStack`, `TabView`, `.sheet`, `.fullScreenCover`, coordinators, storyboards/segues |
| Android | `NavHost` / `composable(...)` routes, `nav_graph.xml`, Activities in the manifest, bottom nav menus |
| Flutter | `GoRouter` / `routes:` / `Navigator.push`, `BottomNavigationBar` |
| React Native | `createNativeStackNavigator`, `createBottomTabNavigator`, Expo Router `app/` folder |
| TV / 10-foot apps | focus-based menus, rails, the remote's back key, deep-link handlers |

Then find the **triggers** that link screens: buttons, links, tab bars, menus, `navigate(...)`,
`router.push`, `.sheet(isPresented:)`, redirects after login, guards. Each trigger becomes an edge.

Write a first `flow.json` without images. The full format is in
[references/flow-schema.md](references/flow-schema.md). In short:

- **Groups**
  - Make exactly one `kind: "nav"` group for the primary navigation shell: the tab bar or sidebar
    destinations, the home screen, and global menus. These screens sit together in one row at the
    top of the canvas.
  - Make one `kind: "feature"` group per feature, with its screens in task order (for example:
    list → detail → edit → confirm).
  - Put onboarding, login and sign-up in their own feature group.
- **Screens**: one per distinct view. Modals, sheets, dialogs and important states (empty, error,
  paywall) count as screens when they matter to the flow. Mark them with `state`. Set
  `entry: true` on the screen where a group starts.
- **Edges**: write the user's action as the label, such as `"Tap 'Checkout'"` or
  `"Swipe left"`. Use `kind` for `back` (return paths), `modal`, and `redirect` (automatic
  navigation). Leave out obvious back links unless they matter. Do not link every tab to every
  other tab. Link the default tab to each of the others, so a 5-tab app has 4 edges, not 20.

Check the map with `python3 scripts/build_flow.py flow.json --check`. For a whole app with more
than about 25 screens, show the user the list of groups and screens and ask them to confirm it
before you capture anything.

## 2. Capture real screenshots

Read [references/capture.md](references/capture.md) for the tool and commands to use on each
platform. Rules for every platform:

- **Use the tools your harness gives you first.** These include browser or preview tools, device or
  simulator tools, and Playwright/Chrome DevTools MCP servers. If you have none, use the fallbacks in
  `capture.md`: `scripts/capture_web.mjs` (Playwright), `xcrun simctl io`, or `adb exec-out screencap`.
- **Run the app yourself.** Use the project's own run instructions (README, AGENTS.md/CLAUDE.md,
  `package.json` scripts, run configs). Use a local or dev build with test data.
- **Log in** with a test account. If you need credentials, ask the user. Never guess, never use a
  real customer's account, and never paste secrets into `flow.json`.
- **Use one device and viewport for the whole flow.** For mobile web, use 390×844 at 2×. For desktop
  web, use 1440×900. For native apps, use one simulator or emulator model. Use the same theme and
  language everywhere.
- **Get to each screen the way a user would** when that is practical. This also checks your edges.
  If a step is slow or flaky, open the screen directly with a deep link or URL. If the real path
  differs from your map, fix the map.
- **Wait until the screen has settled.** No spinners, no skeletons, images loaded, no toasts unless
  they are the point. Close dev overlays and debug banners.
- **Never do anything destructive or irreversible**, such as payments, deletes, or sending email or
  messages, outside a sandbox. Capture the confirmation screen and stop there.
- Save each screenshot as `screens/<screen-id>.png`, and set `image` in `flow.json`.
- **Record a hotspot for each link** while you are on the source screen: the bounding box of the
  element the user taps. Write it in the same coordinate system as the screenshot (pixels of the
  image, or fractions from 0 to 1). On the web, `scripts/capture_web.mjs` does this for you from a
  selector and writes `hotspots.json`. On native platforms, take the element bounds from the UI tree
  (see `capture.md`). Skip it for links that are not a visible element, such as a swipe, an
  automatic redirect or the system back button.
- **Look at every screenshot** after you save it, using your image viewer or Read tool. Recapture
  any shot that is blank, clipped, the wrong screen, a login wall, or an error page.
- **If a screen cannot be reached**, keep it in the map without an `image`, and write the reason in
  `notes`. The viewer shows a "No screenshot captured" card for it.

## 3. Build and check

```bash
python3 scripts/build_flow.py <out>/flow.json            # writes <out>/screen-flow.html
python3 scripts/build_flow.py <out>/flow.json -o docs/flow.html --max-width 900
```

The script needs only the Python standard library. It reads `hotspots.json` next to `flow.json`
when that file exists, or a file you pass with `--hotspots`. To keep the file small, it downscales
screenshots wider than `--max-width` (default 1000 px) when Pillow or macOS `sips` is available.

Open the HTML and look at it. Use a browser tool to screenshot it, or open it for the user. Then
fix the layout through `flow.json` and rebuild:

| Problem | Fix |
|---|---|
| Screens in the wrong order inside a group | Reorder `screens`, set `entry: true`, or pin a screen with `"column": n` |
| A group is a loose set of screens, not a sequence | `"layout": "grid"` on the group |
| A long sequence should run in one row | `"layout": "row"` |
| A feature sits far from where it starts | Add the edge that leads into it, or set `"parent": "<group-id>"` |
| Too many arrows | Remove back links you don't need, or link tabs only from the default tab |
| An arrow starts at the wrong place on a screenshot | Fix that edge's `hotspot` (check it in the detail panel) |

### PNG and PDF exports

If the user asks for an image or a PDF, or the flow has to go into a pull request, a ticket, Confluence
or slides, export it headlessly. This uses the same renderer as the page's Export button:

```bash
node scripts/export.mjs <out>/screen-flow.html <out>/screen-flow.png                 # whole flow
node scripts/export.mjs <out>/screen-flow.html <out>/checkout.png --scope checkout   # one group
node scripts/export.mjs <out>/screen-flow.html <out>/screen-flow.pdf                 # overview + a page per group
```

Options: `--theme light|dark` (default light), `--no-hotspots`, `--no-group-pages` (PDF). The
script needs Playwright, set up the same way as for `capture_web.mjs`. Look at the PNG before you hand it over.

## 4. Report

Give the user the path to `screen-flow.html` and the number of screens and groups. List any screens
without a screenshot and the reason. Mention these viewer controls:

- Drag to pan; scroll or pinch to zoom.
- Click a screen to see it large, with its incoming and outgoing links.
- Drag screens, or a group by its heading, to rearrange them; this is saved in that browser.
- **Hotspots** (toolbar button, or `H`) starts each arrow at the button that triggers it. In the
  detail panel, the hotspots are clickable, so readers can click through the flow like a prototype.
- `/` searches, `F` fits everything on screen.
- **Export** (toolbar) downloads a PNG or a PDF of everything, the current view or one group, in
  the light or dark theme. The PDF has an overview page plus one page per group. Exports follow the
  current toggles (labels, cross-group links, back links, hotspots).
- `#<screen-id>` at the end of the URL opens that screen.
