# screen-flow

An [Agent Skill](https://agentskills.io) that maps an app's navigation as a **screen flow built from real
screenshots**. The result is one standalone HTML file with an infinite, zoomable canvas:

- screens as cards, with labelled arrows for each link between them
- the main navigation grouped in one row at the top, and each feature in its own group below it,
  placed under the screens that lead into it
- **hotspot mode**: each arrow starts at the button, tab or row that triggers it, and in the detail
  panel those areas are clickable, like a prototype
- straight horizontal and vertical arrows with rounded corners, routed around screens without overlaps
- export to **PNG** or **PDF** (everything, the current view or one group, light or dark), from the
  page or headlessly with `scripts/export.mjs`
- pan, zoom, a minimap, search, a detail panel with incoming and outgoing links, screens and whole
  groups you can drag, deep links (`#screen-id`), and light and dark mode
- no dependencies; images are embedded, so the file works offline and can be shared as is

It works for one feature or a whole app, on web, iOS, Android, TV and desktop. The agent reads the
navigation from the code, captures each screen with the tools it has (browser or device tools,
Playwright, `simctl`, `adb`), and then runs the bundled builder.

## Install

```bash
git clone https://github.com/Quinus/screen-flow.git && cd screen-flow
# Claude Code (personal)
ln -s "$PWD/skills/screen-flow" ~/.claude/skills/screen-flow
# Codex and other agents that read ~/.agents/skills
ln -s "$PWD/skills/screen-flow" ~/.agents/skills/screen-flow
# Codex (if it does not read ~/.agents/skills)
ln -s "$PWD/skills/screen-flow" ~/.codex/skills/screen-flow
```

Or copy `skills/screen-flow/` into a project's `.claude/skills/` or `.agents/skills/` folder.

## Use

> Make a screen flow of the whole app
> Map the checkout feature as a screen flow

## Parts

| Path | What it is |
|---|---|
| `skills/screen-flow/SKILL.md` | The procedure the agent follows |
| `skills/screen-flow/scripts/build_flow.py` | `flow.json` + screenshots → standalone HTML (Python standard library only) |
| `skills/screen-flow/scripts/capture_web.mjs` | Optional Playwright helper for web screenshots and hotspots |
| `skills/screen-flow/scripts/export.mjs` | Optional: export a built page to PNG/PDF headlessly |
| `skills/screen-flow/assets/viewer.html` | The canvas viewer template |
| `skills/screen-flow/references/` | The `flow.json` format and capture commands per platform |
| `examples/streamtv/` | A sample flow (14 screens, 4 groups) and its built `screen-flow.html` |

Build the example yourself:

```bash
python3 skills/screen-flow/scripts/build_flow.py examples/streamtv/flow.json
open examples/streamtv/screen-flow.html
```

## License

MIT
