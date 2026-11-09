# flow.json format

One JSON file describes the flow. Image paths are relative to the folder of `flow.json`.

```jsonc
{
  "title": "StreamTV — app navigation",          // page title
  "description": "Whole-app screen flow.",         // optional, shown in the sidebar
  "scope": "app",                                  // "app" | "feature"
  "platform": "iOS 18 · iPhone 16 simulator",     // optional, free text

  "groups": [
    { "id": "main", "label": "Main navigation", "kind": "nav", "description": "Bottom tab bar" },
    { "id": "auth", "label": "Onboarding & login" },
    { "id": "watch", "label": "Watch & record" },
    { "id": "settings", "label": "Settings", "parent": "main", "layout": "flow", "color": "#a142f4" }
  ],

  "screens": [
    { "id": "home", "title": "Home", "group": "main", "image": "screens/home.png", "route": "/", "entry": true },
    { "id": "details", "title": "Show details", "group": "watch", "image": "screens/details.png", "route": "/show/:id",
      "notes": "Opened from any show tile." },
    { "id": "record-confirm", "title": "Record dialog", "group": "watch", "image": "screens/record-confirm.png", "state": "modal" }
  ],

  "edges": [
    { "from": "home", "to": "details", "label": "Tap a show" },
    { "from": "details", "to": "record-confirm", "label": "Record", "kind": "modal" },
    { "from": "record-confirm", "to": "details", "label": "Cancel", "kind": "back",
      "hotspot": { "x": 0.05, "y": 0.42, "w": 0.9, "h": 0.06 } }
  ]
}
```

## Groups

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique id that screens refer to. |
| `label` | no | Heading on the canvas (defaults to `id`). |
| `kind` | no | `nav`: the main navigation shell, placed at the top. `feature` (default): one feature's screens. |
| `layout` | no | `row`: all screens side by side (default for `nav`). `flow`: left-to-right by navigation depth (default for `feature`). `grid`: compact block for screens that have no order. |
| `parent` | no | Group to place this one under when no edge leads into it. |
| `color` | no | `#rrggbb`. Without it, a color is picked from the palette. |
| `description` | no | Short subtitle next to the heading. |

The order of the `groups` array is the order of the sidebar and the tie-breaker in the layout.

## Screens

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique, kebab-case. Also the screenshot name: `screens/<id>.png`. |
| `group` | yes | Group id. |
| `title` | no | Card title (defaults to `id`). |
| `image` | no | Screenshot path (PNG, JPEG, WebP or GIF). Without it, a placeholder card is shown. |
| `route` | no | URL path, route name or deep link, shown on the card. |
| `entry` | no | `true` for the screen where the group starts. It goes in the first column. |
| `state` | no | Short badge such as `modal`, `empty`, `error`, `logged out`. |
| `notes` | no | Shown in the detail panel. Use it for conditions ("only for admins") or why a screenshot is missing. |
| `column` | no | Integer. Forces the screen into this column of a `flow` group. |

Portrait screenshots are shown 260 px wide and landscape ones 520 px wide. Very tall full-page
screenshots are cropped on the card, and the detail panel shows the whole image.

## Edges

| Field | Required | Meaning |
|---|---|---|
| `from`, `to` | yes | Screen ids. |
| `label` | no | The user action, such as `"Tap 'Buy'"`. Keep it short (it is cut off at about 30 characters). |
| `kind` | no | `nav` (default), `action`, `modal` (dotted line), `back` (faint dashed line, ignored by the layout, can be hidden), `redirect` (automatic navigation). |
| `hotspot` | no | Where the element that triggers this link sits on the source screenshot: `{ "x", "y", "w", "h" }` (or `[x, y, w, h]`). Use fractions of the image (0–1) or pixels of the original screenshot; the build converts pixels to fractions. |

### hotspots.json

Instead of writing `hotspot` on each edge, you can put the boxes in `hotspots.json` next to
`flow.json`. `scripts/capture_web.mjs` writes this file for you. The keys are `"<from>><to>"`, or
`"<from>><to>#<label>"` when two links connect the same screens:

```json
{ "details>player": { "x": 0.05, "y": 0.27, "w": 0.9, "h": 0.06 },
  "home>search": [312, 1622, 140, 60] }
```

A `hotspot` written on an edge takes priority over the file.

Edges between groups are drawn dashed in the target group's color, and the viewer can hide them.
The layout uses edges between groups to place a feature group close to the screens that lead into it.

## Layout rules (what the build does)

1. The `nav` groups go in one row at the top.
2. The feature groups reached from the row above go in the next row. Each one is centered under the
   screens that link to it, where there is room. Groups reached from those come in the row after
   that, and so on. Groups that nothing leads to go last.
3. Inside a `flow` group, columns follow the navigation depth from the entry screen(s). Screens in a
   column are ordered to keep crossing arrows to a minimum.
4. Rows wrap so that the whole canvas stays roughly landscape.
5. Arrows use only horizontal and vertical lines with rounded corners. They are routed around
   screens and group headings. Lines that would share a track are spread into separate lanes, and
   the two ends of an arrow line up when they can, so the line runs straight. Labels go where they
   do not cover screens, other labels or other lines.
6. In **hotspot mode** (on by default when there are hotspots), an arrow starts at its hotspot on
   the screenshot and leaves the card through the nearest edge that faces the target. Hotspots cut
   off by the crop of a tall screenshot fall back to a normal arrow.
7. Readers can drag cards, or whole groups by their heading, in the viewer. Those positions are saved in their browser only, and
   "Reset layout" undoes them.
