---
name: iphone-pwa
description: Hard constraints and verification workflow for a React PWA whose only real client is an iPhone 14 running iOS Safari, installed to the Home Screen. Use this skill whenever writing or changing ANY frontend code in this repo - layout, CSS, forms, navigation, charts, camera, manifest, service worker, or viewport - even when the request is phrased as a small tweak, a styling change, or "just add a field". Also use when the user reports that something "looks wrong on my phone", text is cut off, the page zooms unexpectedly, the keyboard covers an input, the bottom nav sits under the home indicator, or the barcode scanner does not open. Applies to design decisions AND correctness; do not skip it because the task seems purely cosmetic.
---

# iPhone 14 PWA Constraints

This app has exactly one production client: an **iPhone 14 (base model)** running iOS Safari, installed to the Home Screen, served over HTTPS from a Raspberry Pi via Tailscale. Desktop browser rendering is a development convenience, not a target. When a tradeoff exists, the phone wins.

Every rule below is a correctness constraint, not a preference. Violating them produces bugs that are invisible on a desktop browser and obvious on the device.

## Device facts (do not guess these)

| Property | Value |
|---|---|
| CSS viewport (portrait) | **390 × 844 px** |
| Device pixel ratio | **3** (physical 1170 × 2532) |
| Screen cutout | **Notch**, not Dynamic Island |
| `safe-area-inset-top` (standalone, portrait) | ~47–48px |
| `safe-area-inset-bottom` (portrait) | **34px** (home indicator) |
| `safe-area-inset-left/right` (portrait) | 0 |

The iPhone 14 has a **notch**. The Dynamic Island is the 14 **Pro**. Do not copy inset values or mockups that assume the Pro; the top inset differs.

Insets are **0 in a normal Safari tab** and non-zero only in standalone (Home Screen) mode. This is the single biggest reason a layout "works in Safari but breaks after installing". Always reason about standalone mode as the real case.

## The non-negotiables

### 1. Viewport meta

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

`viewport-fit=cover` is **required** or every `env(safe-area-inset-*)` resolves to 0 and all safe-area handling silently does nothing.

Never add `user-scalable=no` or `maximum-scale=1`. It is an accessibility failure, and modern iOS Safari ignores it anyway, so it buys nothing and costs pinch-zoom. It is **not** the fix for input zoom; see rule 3.

### 2. Height: never `100vh`

On iOS Safari `100vh` is the **largest** viewport (toolbar collapsed). With the toolbar visible, `100vh` overflows the visible area and the bottom of the app shell is unreachable.

```css
.app-shell {
  height: 100vh;   /* fallback for anything ancient */
  height: 100dvh;  /* wins where supported */
}
```

Tailwind: `h-screen` is `100vh` and is **wrong here**. Use `h-dvh`, or `h-[100dvh]` on older Tailwind.

Use `dvh` for the app shell and anything that must fill the screen. `svh` is acceptable for a fixed element that must never be occluded regardless of toolbar state.

### 3. Form inputs: 16px minimum, always

If any `input`, `select`, or `textarea` has a computed `font-size` below 16px, Safari **zooms the page on focus and does not zoom back out**. In a food-logging app this fires on every single entry and makes the app feel broken.

```css
input, select, textarea { font-size: 16px; }
```

Tailwind: `text-base` (16px) minimum on all form controls. Never `text-sm` or `text-xs` on an input, no matter how much better it looks in the desktop preview. If a field must appear visually smaller, scale it with padding, width, or `transform`, never `font-size`.

This applies to the barcode/weight/macro quick-entry fields especially, since they are the highest-frequency interactions in the app.

### 4. Safe areas: bottom nav and headers

The home indicator sits over the bottom 34px. A bottom tab bar without inset padding has its tap targets partly under it.

```css
.bottom-nav {
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}

.app-header {
  padding-top: max(12px, env(safe-area-inset-top));
}
```

Tailwind: `pb-[max(0.75rem,env(safe-area-inset-bottom))]`.

Always wrap in `max()` with the design padding. Bare `env(...)` collapses to 0 in a browser tab and on desktop, giving a nav with no padding at all.

Any `position: fixed` bottom element (nav, FAB, sticky "Save" button) needs this. Any scrollable list above a fixed bottom nav needs matching bottom padding or the last row is permanently hidden behind it.

### 5. Status bar style

```html
<meta name="apple-mobile-web-app-status-bar-style" content="default">
```

Use `black-translucent` **only** if the header is deliberately drawn under the status bar and handles `safe-area-inset-top` itself. Choosing `black-translucent` without inset padding puts the header content under the clock. If unsure, `default` is the safe choice.

### 6. Tap targets: 44 × 44pt

Apple HIG minimum. Applies to nav items, set-logging +/− steppers, chart legend toggles, and delete buttons.

```css
.tap-target { min-height: 44px; min-width: 44px; }
```

Tailwind: `min-h-11 min-w-11` (44px).

If the visual element must be smaller (a small icon button), keep the visual size and expand the hit area with padding or a `::after` overlay. Do not shrink the target.

### 7. Scroll behaviour

```css
body { overscroll-behavior-y: none; }
```

Stops the rubber-band / pull-to-refresh gesture reloading the app mid-scroll, which in standalone mode loses in-memory state.

Charts and horizontally scrolling elements steal vertical scroll unless told not to:

```css
.chart-container { touch-action: pan-y; }
```

Kill the grey flash on tap:

```css
* { -webkit-tap-highlight-color: transparent; }
```

Only do this if a visible `:active` or focus state exists to replace it. Removing feedback without a replacement is worse than the grey flash.

### 8. Keyboard and `position: fixed`

iOS does **not** resize the layout viewport when the keyboard opens. A `position: fixed` bottom bar stays put and the keyboard covers it. There is no CSS fix.

If a fixed element must stay above the keyboard, use the `visualViewport` API:

```js
visualViewport.addEventListener('resize', () => {
  const offset = window.innerHeight - visualViewport.height - visualViewport.offsetTop;
  document.documentElement.style.setProperty('--kb-offset', `${Math.max(0, offset)}px`);
});
```

Then offset with `transform: translateY(calc(-1 * var(--kb-offset, 0px)))`.

Prefer avoiding the problem: on any screen with a text input, do not use a fixed bottom action bar. Put the action inline at the end of the form and let the page scroll.

### 9. Home Screen icon and splash

iOS **ignores manifest icons** for the Home Screen icon. Without this tag you get a screenshot of the page as the icon:

```html
<link rel="apple-touch-icon" href="/apple-touch-icon.png"> <!-- 180×180 -->
```

The icon must be **opaque** (iOS composites onto white and applies its own mask; transparency looks broken) and must have **no pre-rounded corners** (iOS rounds it).

Without `apple-touch-startup-image`, launch shows a white flash. For iPhone 14 the splash image is **1170 × 2532**. This is polish, not correctness; defer it if time-constrained.

Manifest needs `"display": "standalone"`.

## Camera and the barcode scanner

`getUserMedia` requires a **secure context**. Over Tailscale, a plain `http://` MagicDNS hostname is **not** secure and the scanner will fail silently with a permissions error, no matter what the frontend does.

Requirement: Tailscale HTTPS certificates (MagicDNS + Let's Encrypt) must be enabled, and the app served over `https://`. `localhost` is exempt during development, which is exactly why this bug does not appear on the laptop and does appear on the phone. If the scanner fails on device, **check the scheme before touching frontend code**.

Also true on iOS:
- Camera permission needs a real user gesture. Do not call `getUserMedia` on mount or during a route transition; call it from the tap on "Scan".
- Request `{ video: { facingMode: 'environment' } }` for the rear camera.
- Permission is per-origin and survives; a denial is sticky and only reversible in iOS Settings. Handle the denied state with an explicit instruction, not a silent failure.
- Stop all tracks on unmount or the camera light stays on.

## Storage and state

Do not treat client storage as durable. **The Pi is the source of truth.** IndexedDB / localStorage / cache are a latency optimisation and an offline-read convenience, never the only copy of a logged meal, weight, or set.

Any mutation (food log, set, weight, bloodwork panel) must reach the backend or be queued for replay with an explicit pending state visible in the UI. Never show a write as succeeded on the strength of a local write alone.

Standalone mode has **no browser back button**. Every screen deeper than the tab root needs an in-app back affordance, or the user is trapped and force-quits.

## Verification: assert, don't eyeball

Desktop responsive mode does **not** reproduce safe-area insets, input zoom, `dvh` toolbar behaviour, or the keyboard. It is not evidence. Use Playwright's built-in device descriptor:

```js
const { devices } = require('@playwright/test');
const iphone = devices['iPhone 14'];
// viewport 390×844, deviceScaleFactor 3, isMobile, hasTouch, iOS Safari UA
```

After any frontend change, verify at that viewport and screenshot before claiming it works.

The checks Playwright **can** catch:
- Horizontal overflow at 390px wide: `document.documentElement.scrollWidth > 390` must be false. This is the most common real bug (a wide chart, a long food name, an unwrapped table).
- Any form control with computed `font-size` < 16px.
- Any interactive element with a bounding box < 44px in either axis.
- `100vh` present in shipped CSS.
- Bare `env(safe-area-inset-*)` not wrapped in `max()`.

The checks Playwright **cannot** catch, which need the real device:
- Actual safe-area inset rendering in standalone mode.
- Keyboard occlusion.
- Camera / `getUserMedia`.
- Home Screen icon and splash.

So: Playwright is the fast gate, the phone is the acceptance test. Never report a mobile fix as done on the basis of a desktop render.

## Review checklist

Before finishing any frontend change, confirm:

- [ ] No `100vh` (or Tailwind `h-screen`) in the diff
- [ ] Every new input/select/textarea is ≥ 16px
- [ ] No horizontal overflow at 390px
- [ ] New fixed/sticky bottom elements use `max(..., env(safe-area-inset-bottom))`
- [ ] Scroll containers above the bottom nav have clearing padding
- [ ] New tap targets ≥ 44×44
- [ ] No fixed bottom action bar on a screen with a text input
- [ ] Any new write path has a server round-trip or a visible queued state
- [ ] Screenshotted at the `iPhone 14` Playwright descriptor
