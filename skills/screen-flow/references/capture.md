# Capturing screenshots

Use the first option that your environment offers. All options produce `screens/<screen-id>.png`.

## Order of preference

1. **Tools from your harness**: built-in browser or preview tools, device or simulator tools (for
   example an iOS Simulator or Android Emulator panel), or an MCP server such as Playwright MCP or
   Chrome DevTools MCP. These are made for this job. If the harness says to use its device tools
   instead of raw `simctl` or `adb`, follow that.
2. **The fallback commands below.**
3. **Ask the user** for screenshots only as a last resort, for example when the app needs hardware,
   a real payment, or an account you cannot get. Name the exact screens you need.

## Web

### Playwright helper (bundled)

`scripts/capture_web.mjs` captures a list of screens with proper device emulation:

```bash
# If the project has no playwright, install playwright-core in a temporary folder.
# It uses the Chrome or Edge that is already installed, so there is no browser download.
npm i --prefix /tmp/sf playwright-core
NODE_PATH=/tmp/sf/node_modules node scripts/capture_web.mjs <out>/shots.json
```

`shots.json` lists `baseUrl`, `viewport`, `deviceScaleFactor`, `isMobile`, an optional `setup`
(for example a login, which runs once and keeps cookies) and `screens` with `path`, `steps`
(`click`, `fill`, `press`, `hover`, `waitFor`, `wait`, `eval`) and `fullPage`. The header of the
script shows the full format. Screens that fail are reported, and the others are still captured.

Tips:
- Prefer `steps` that click through the real UI (for example `"click": "text=Settings"`) over
  deep URLs. Clicking through also checks the edges in your map.
- For modals and menus, open them with `steps` and capture without `fullPage`.
- Use `fullPage: true` only for long scrolling pages where the content below the fold matters.
- Do not use Chrome's command line `--headless --screenshot` for mobile sizes. Chrome keeps a
  minimum window width there, so narrow viewports come out clipped on the right.

### Browser or preview tools from the harness

Set the viewport size first. Navigate, wait for the page to settle, and take a screenshot of the
viewport. If the tool returns the image inline and does not save a file, check whether it has an
option to save to a path. Otherwise use the Playwright helper for the files and use the tool only to
explore.

## iOS (Simulator)

```bash
xcrun simctl list devices booted                           # pick one device and keep it
xcrun simctl openurl booted "myapp://settings/parental"    # deep link, if the app supports it
xcrun simctl io booted screenshot screens/parental.png
xcrun simctl status_bar booted override --time 9:41 --batteryLevel 100 --cellularBars 4   # clean status bar
```

To tap through the UI, use your harness's device tool or an automation tool that is already in the
project (XCUITest, Maestro, Appium). `simctl` cannot tap.

## Android (Emulator or device)

```bash
adb devices
adb shell am start -W -a android.intent.action.VIEW -d "myapp://settings/parental"   # deep link
adb shell input tap 540 1650                    # tap at coordinates (read them from uiautomator dump)
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml   # find element bounds
adb exec-out screencap -p > screens/parental.png
adb shell settings put global sysui_demo_allowed 1   # optional: demo mode for a clean status bar
```

For Android TV, use D-pad key events instead of taps: `adb shell input keyevent KEYCODE_DPAD_DOWN`,
`KEYCODE_DPAD_CENTER`, `KEYCODE_BACK`.

## Desktop apps

- **Electron**: Playwright's `_electron.launch()` gives a `page` with `page.screenshot()`.
- **macOS**: `screencapture -l <windowId> -o screens/x.png`. To get the window id, list windows with
  a small `osascript`/Swift helper, or use `screencapture -w` interactively.
- **Windows**: an automation tool that is already in the project (WinAppDriver, Playwright for
  WebView2), or ask the user.

## Hotspots (where a link is tapped)

For each link, record the bounding box of the element the user taps, measured on the same screen
and in the same state as its screenshot. Pixels of the screenshot image or fractions (0–1) both work.

- **Web, with the helper**: add `"hotspots": [{ "to": "<target id>", "selector": "<selector>" }]` to
  the screen in `shots.json`. The helper writes `hotspots.json`, which the build picks up.
- **Web, with other browser tools**: run
  `JSON.stringify(document.querySelector(sel).getBoundingClientRect())` in the page and divide by
  `innerWidth` and `innerHeight` (for full-page shots, add `scrollX` and `scrollY` and divide by the page size).
- **Android**: `adb shell uiautomator dump` gives `bounds="[x1,y1][x2,y2]"` in screen pixels, which
  are the same pixels as `screencap`. Use `[x1, y1, x2 - x1, y2 - y1]`.
- **iOS**: device or automation tools (XCUITest `frame`, Maestro, Appium, agent-device snapshots)
  give frames in points. Multiply by the screen scale (2× or 3×) to get screenshot pixels, or divide
  by the screen size in points to get fractions.
- **TV / focus-based UIs**: use the focused element's bounds just before you press OK.

Leave out hotspots for links without a visible element: swipes, automatic redirects, the system back button.

## Checklist for each screenshot

- Is it the right screen, fully loaded, with no spinner or skeleton?
- Is it the same device, viewport, theme and language as the rest?
- Are there no debug overlays and no personal data (real names, emails, tokens)? Use test accounts.
- Is it saved as `screens/<id>.png`, and does `image` in `flow.json` point to it?
- Did you look at the image after saving it?
- Do the hotspots for this screen cover the right elements? Check them in the built page: open the
  screen's detail panel, where the hotspots are drawn on the screenshot.
