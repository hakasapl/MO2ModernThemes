# MO2 Modern Themes

Stylesheets for Mod Organizer 2, plus a plugin (`plugins/modern_themes.py`) that does what a stylesheet cannot. The plugin is for any stylesheet, not only these themes: a stylesheet opts in with marker comments, documented in the README, which is the plugin's public interface.

Keep this file up to date: when the user gives a lasting instruction about this project, record it in the relevant section.

## Layout

- `src/modern-theme.qss` and `src/icons/*.svg`: templates shared by every theme.
- `src/icons/mo2/<alias>.svg`: flat versions of MO2's own icons, named after the resource alias in MO2's `resources.qrc` (`emblem_notendorsed.svg` replaces `:/MO/gui/emblem_notendorsed`, `content/plugin.svg` replaces `:/MO/gui/content/plugin`); an icon without an alias takes its file's name. `tools/icons.py` (needs PyQt6) writes them all: change an icon there and run it, never the SVG. Each traces the shape of MO2's original (same silhouette, badge positions and sizes) at the original's pixel size as its viewBox, drawn flat in palette colors, with real gaps cut where one shape sits on another. How they reach MO2:
  - The stylesheet sets the toolbar's and buttons' icons with `qproperty-icon` by object name. MO2 hands a toolbar action's icon to a stand-in button named after the action, so `#actionSettings` matches it; a dialog's buttons are scoped by the dialog's name (`#EditExecutablesDialog #add`).
  - The plugin puts the list icons MO2's icon delegates draw (conflicts, flags, content) in Qt's pixmap cache under MO2's keys, and the images MO2 loads as pixmaps (the notification badges) under QPixmap's file keys; adding a file is enough for those.
  - Icons a model hands its view need their column in `DECORATION_COLUMNS`: the plugin swaps them for the theme's where Qt's own delegate draws the cell, and draws over MO2's drawing where MO2's delegate does (the Version column), so those must cover the original's whole silhouette. Menu items MO2 adds in code get the theme's icon when the menu opens.
  - The SVGs are 128px, the size Qt reads a stylesheet icon at and scales down from, except the notifications icon: MO2 paints the count onto it at 64px, which comes out right only for an icon of at most 64.
- `themes/<theme>.css`: base palettes, a `:root` block of CSS variables. One base: `dark.css` (colors from Bearded Theme Vivid Black). A light base (from VS Code's Light Modern) was tried and removed at the user's request; do not add one back unasked. Each variable's comment names the theme key it comes from.
- `accents/<color>.css`: one accent per color of the rainbow, plus gray, `--accent-name` and `--accent`; every accent is used with every base. The build makes one variant per base and accent. The base palette is the main file all variants inherit; an accent declares only what differs, and any variable it declares overrides the base's, like a later `:root` rule in CSS (except in the icons, which use the base alone). Qt stylesheets have no `@import`, so every shipped `.qss` is written out complete.
- `stylesheets/`: build output, not committed (`Modern Theme <theme> - <accent>.qss`, such as `Modern Theme Dark - Red.qss`, and `ModernTheme<theme>/` icons). Icons use only base colors, so all accents of a base share one icon folder; the build renders them from the base palette alone, so an icon using `--accent` fails the build. Do not edit it by hand; the build removes outputs of variants that no longer exist, here and in MO2's install.
- `build.py`: Qt stylesheets have no CSS variables, so it replaces every `var(--x)` with the palette value. Python 3.10 or newer, no packages; the release workflow builds with 3.12, so keep to what 3.10 has.
- `tools/icons.py` and `tools/shapes.py`: the icon generator, see above.
- `.github/workflows/release.yml`: run by hand, builds the stylesheets and drafts a GitHub release with two archives, each extracted into the MO2 folder: the plugin (`plugins/`) and the themes (`stylesheets/`). The version is the plugin's `version()` unless one is given.
- `README.md`: for MO2 users and stylesheet authors: installing, the plugin's settings, and every marker comment. Keep it in step with the plugin.

## Workflow

After any edit, rebuild and deploy to the MO2 install at `C:\Relentless\MO2`:

```
python build.py --deploy C:\Relentless\MO2
```

MO2 reloads the stylesheet on its own when the file changes. A changed plugin only loads at startup, and MO2 reads the icons only when it applies a stylesheet, so `--deploy` closes MO2 normally and starts it again whenever the plugin or an icon differs from the deployed copy.

## Plugin guidelines

- The plugin does nothing unless the selected stylesheet carries the `mo2-modern-themes` marker: with another style it watches only the main window for a stylesheet change, installs no app-wide event filter and starts no thread or timer. Anything new it does must be gated the same way and undone when another style is selected.
- The plugin is not tied to these themes. A fix for how MO2 or Qt paint over a stylesheet can apply to every marked stylesheet; a design choice (a gap, a radius, a look) goes behind its own optional marker comment, read by `Markers` in the plugin, off when the comment is absent, with this repo's values written in `src/modern-theme.qss`. Document every marker in the README and the plugin's docstring.
- Each step of `refresh()` runs on its own, so one failing leaves the others applied; the event filter catches its own exceptions. Keep new steps in that list.
- Every element the plugin hides must be toggleable in the plugin settings. Add it to `HIDDEN_WIDGETS` in `plugins/modern_themes.py` (object name, setting key, description); the setting defaults to hidden and applies without a restart. An object name other windows use too is written `ancestor/name` (`nexusScrollAreaWidgetContents/widget_6`), so it only matches inside that ancestor. Things hidden other than by object name get their own setting in `settings()`, like `SCROLL_BAR_SETTING` for the scroll bars the plugin replaces with overlay bars.
- The theme has no animations. A hover fade for lists and a fade for the overlay scroll bars were tried and removed: both made scrolling or the fade itself jitter. Smooth scrolling is the one motion, with its own setting.
- The plugin never hardcodes colors. Colors it needs come from the stylesheet's marker comments, written there by the template from palette variables, like the `mo2-modern-themes-titlebar` comment for window title bars.

## Color guidelines

The theme will be recolored into many permutations, so color lives only in the palettes.

- Never write a hex color in `src/`; use a `var(--...)` from the palette. `build.py` rejects hex colors in templates.
- Keep the palette small. Reuse an existing variable whenever the color is close; do not add a variable for a shade that differs only slightly from one already there. Every new variable must be defined in every theme.
- Name variables by role or ramp step (`--bg-0` … `--bg-6`, `--text-muted`), never by hue, so the names stay true in every permutation.
- A new theme is a new `themes/<theme>.css` with the same variables; nothing in `src/` changes.
- The accent (`--accent`) colors the checkboxes, the radio buttons and the active filter borders (the lists, their counters and Clear all Filters), for now. Group boxes (settings panels, the filter panel) have the context menus' border, not the accent. Everything else uses base colors, including links (`--link`) and progress bars (`--progress`).
- Base palette colors come from the base's VS Code theme JSON (Bearded Vivid Black from the Bearded extension). A variable takes the same theme key in every base, and translucent theme colors are blended over the background shade they sit on. Where a key would break a role, its comment says what it uses instead and why (the borderless `--input-border`).
- Icons draw their light marks with `--icon-mark` and their dark marks with `--icon-shade`, never `--text-bright` or a background shade, so they stay right in a base of any lightness. Cut-outs only go through shapes in `--text` colors or saturated colors, where the background shows through as a contrasting mark.
