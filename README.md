# MO2ModernThemes

Modern themes with extended styling through a plugin for [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer).

The themes are Qt stylesheets in a dark and a light base, each with nine accent colors. The plugin does what a stylesheet cannot: smooth scrolling, overlay scroll bars, list columns that always fit, rounded and pinned separators, themed window title bars, sharp SVG icons in place of MO2's small PNGs, and fixes for the places where MO2 or Qt paint over a stylesheet. Any stylesheet can use the plugin, see [Using the plugin in your own stylesheet](#using-the-plugin-in-your-own-stylesheet).

## Installing

Download both archives from the [latest release](../../releases/latest) and extract them into your MO2 folder, the one with `ModOrganizer.exe`:

- **MO2ModernThemes-Plugin** puts `modern_themes.py` in `plugins/`.
- **MO2ModernThemes-Themes** puts the stylesheets and their icons in `stylesheets/`.

Restart MO2, then pick a theme in **Settings → General → Style**: `Modern Theme Dark - <accent>` or `Modern Theme Light - <accent>`, with Blue, Gray, Green, Indigo, Orange, Red, Violet or Yellow. The themes work without the plugin too, with ordinary scroll bars and MO2's own icons in the lists.

### Plugin settings

**Settings → Plugins → Modern Themes**:

| Setting | Default | |
|---|---|---|
| `overlay_scroll_bars` | on | Slim scroll bars over the content's edge while the mouse is near it, instead of regular ones. |
| `smooth_scrolling` | on | Lists glide to where a mouse wheel step takes them. |
| `scroll_speed` | 3 | Rows a wheel step scrolls. |
| `sticky_separators` | on | The separator of the mods at the top of the mod list stays pinned there. |
| `hide_nexus_settings_gap` | on | Closes an empty gap in the Nexus settings tab. |

## The themes

| Base | Colors from |
|---|---|
| Dark | [Bearded Theme](https://github.com/BeardedBear/bearded-theme) Vivid Black |
| Light | VS Code's Light Modern |

The accent colors checkboxes, radio buttons, settings panels and active filter borders. Everything else uses the base's colors.

The stylesheet started from [Night Eyes](https://github.com/ciathyza/mo2-themes) by Ciathyza. MO2's icons are redrawn flat, tracing the shapes of MO2's originals.

## Using the plugin in your own stylesheet

The plugin does nothing for a stylesheet unless the stylesheet asks for it, with comments. This one turns it on:

```css
/* mo2-modern-themes */
```

With it, the plugin:

- Makes context menus and dropdown lists see-through windows without the Windows drop shadow, so rounded corners in the stylesheet show. A dropdown's list lines up with its dropdown.
- Draws the mod, plugin and archive lists with Fusion, whose checkboxes a stylesheet can fully style. The native Windows 11 style paints its own under them.
- Fills a highlighted row of the mod or plugin list across the whole row, the indentation and the square around a rounded checkbox included.
- Keeps the status bar's API label inside the stylesheet's rounded corners and margins.
- Scrolls every list smoothly and fits the mod and plugin lists' columns to their width.
- Pins the top separator of the mod list, lines the executables row up with the mod list's, and closes the Nexus settings' empty gap. The settings above turn these off.

Each of these comments turns on more. A value runs to the end of its comment; quote one that has spaces.

| Comment | Does |
|---|---|
| `mo2-modern-themes-titlebar: caption=#rrggbb text=#rrggbb border=#rrggbb [dark=0\|1]` | Colors every window's title bar (Windows 11). Any of the three colors can be left out. `dark` picks light or dark minimize, maximize and close buttons, by default whatever suits the caption color. |
| `mo2-modern-themes-icons: <folder>` | Replaces MO2's icons with the SVGs in the folder, relative to the stylesheet. See [Icons](#icons). |
| `mo2-modern-themes-filter: #rrggbb [<width>px]` | Colors MO2's red borders for an active filter (on the lists, their counters and Clear all Filters), and optionally sets their width. |
| `mo2-modern-themes-filter-toggle: <closed.svg> <open.svg>` | Shows these icons on the filter panel's toggle, relative to the stylesheet, in place of MO2's `»` and `«`. |
| `mo2-modern-themes-list-corner: <radius>` | Keeps list rows out of rounded list corners. Qt draws rows over the border's rounding, so give lists a border radius and pass the radius less the border's width. |
| `mo2-modern-themes-separators: radius=<radius> margin=<x>,<y>` | Draws the mod list's separators as rounded bars with a margin around them, instead of full row stripes. They show no hover or selection. |
| `mo2-modern-themes-popup-gap: <gap>` | Leaves a gap of that many pixels between a button or dropdown and the menu or list it opens. |
| `mo2-modern-themes-overlay-scrollbars` | Hides the scroll bars and shows the vertical ones over the content's edge while the mouse is near it (the `overlay_scroll_bars` setting turns this off). The bar is as wide as the stylesheet makes `QScrollBar:vertical`, and named `modernThemesOverlayScrollBar` for a selector. Draw its handle in its outer part to make a wide bar that looks slim. |

The plugin also leaves names a stylesheet can use: `modernThemesOverlayScrollBar` for the overlay bars, and `modernThemesCornerCap` for the small widgets that paint a list's rounded corners.

### Icons

The icon folder holds SVGs named after MO2's resource aliases in its [`resources.qrc`](https://github.com/ModOrganizer2/modorganizer/blob/master/src/resources.qrc): `warning.svg` replaces `:/MO/gui/warning`, `content/plugin.svg` replaces `:/MO/gui/content/plugin`. Any subset works; MO2 keeps its own icon wherever the folder has none. The plugin renders them sharp at any scaling for the lists' flag, conflict and content icons, the log, the filter panel and the menus.

Toolbar and button icons are the stylesheet's to set, with `qproperty-icon` by object name. MO2 hands each toolbar action's icon to a stand-in button named after the action:

```css
#actionSettings { qproperty-icon: url(./MyTheme/icons/settings.svg); }
#EditExecutablesDialog #add { qproperty-icon: url(./MyTheme/icons/add.svg); }
```

Qt reads such an icon at the SVG's own `width` and `height` and scales it down, so give it a large size, 128 for example. The notifications icon is the exception: MO2 paints the problem count onto it at 64 pixels, which works only for an icon of at most 64.

## Building

The stylesheets are built from the templates in `src/`, a base palette from `themes/` and an accent from `accents/`. Qt stylesheets have no CSS variables, so the build writes each variant out complete. It needs Python 3.10 or newer, and nothing else:

```
python build.py
```

This writes `stylesheets/`. To deploy to an MO2 install as well:

```
python build.py --deploy "C:\path\to\MO2"
```

The `MO2_DIR` environment variable also works in place of the argument. The deploy restarts MO2 when the plugin or an icon changed, since MO2 loads both only at startup.

`src/icons/mo2/` is generated by `tools/icons.py`, which needs PyQt6. Change an icon there and run the script, rather than editing the SVGs:

```
python tools/icons.py [name ...]
```

A new base is a new `themes/<name>.css` with the same variables; a new accent is a new `accents/<name>.css`. Each palette variable's comment names the VS Code theme key it comes from.

### Releasing

The **Draft release** workflow, run by hand from the Actions tab, builds the stylesheets and drafts a release with the two archives. It takes the version to release, by default the plugin's own.

## License

[GPL-3.0](LICENSE)
