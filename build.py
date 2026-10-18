"""Builds the Modern Theme stylesheets and icons from the templates in src/ and the palettes.

Qt stylesheets have no CSS variables, so every var(--name) in the templates is replaced with the value
the palette gives it. A palette is a base theme from themes/ with an accent from accents/: every pair
becomes stylesheets/Modern Theme <theme> - <accent>.qss. The icons use only the base's colors, so a
base's variants share stylesheets/ModernTheme<theme>/. Outputs that are no longer built are removed.

    python build.py                       build every theme
    python build.py --deploy [MO2 folder] build, then copy the themes and the plugin into an MO2 install,
                                          the folder given or else the MO2_DIR environment variable's,
                                          restarting MO2 when the plugin or an icon changed
"""

import filecmp
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "src" / "modern-theme.qss"
ICONS = ROOT / "src" / "icons"
THEMES = ROOT / "themes"
ACCENTS = ROOT / "accents"
STYLESHEETS = ROOT / "stylesheets"
PLUGIN = ROOT / "plugins" / "modern_themes.py"
# In seconds, how long MO2 gets to close before a deploy gives up.
CLOSE_TIMEOUT = 30

# What the build writes into a stylesheets folder, so it can tell its own stale outputs apart.
STYLESHEET_PATTERN = "Modern Theme*.qss"
ICON_DIR_PATTERN = "ModernTheme*"

VARIABLE = re.compile(r"var\(--([\w-]+)\)")
DECLARATION = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# A hex color, but not an object name in a selector such as QFrame#frame.
HEX_COLOR = re.compile(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b")


def readText(path: Path) -> str:
    # Line endings as they are in the file. Path.read_text() takes newline= only from Python 3.13.
    with open(path, encoding="utf-8", newline="") as file:
        return file.read()


def readPalette(path: Path, required: tuple) -> dict:
    palette = dict(DECLARATION.findall(COMMENT.sub("", readText(path))))
    palette = {name: value.strip() for name, value in palette.items()}
    for name in required:
        if name not in palette:
            sys.exit(f"{path.name}: --{name} is missing")
    return palette


def themes() -> list:
    """Every base theme with its accents, as (theme palette, [(source, variant palette)])."""
    result = []
    for themePath in sorted(THEMES.glob("*.css")):
        theme = readPalette(themePath, ("name", "colors-from"))
        # The icons use only the base's colors, so every accent of a base shares one icon folder.
        theme["icon-dir"] = "ModernTheme" + theme["name"].replace(" ", "")
        accents = []
        for accentPath in sorted(ACCENTS.glob("*.css")):
            accent = readPalette(accentPath, ("accent-name", "accent"))
            palette = {**theme, **accent}
            palette["name"] = f"{theme['name']} - {palette.pop('accent-name')}"
            accents.append((f"{themePath.name} + {accentPath.name}", palette))
        result.append((theme, accents))
    return result


def resolve(text: str, palette: dict, source: str, used: set) -> str:
    def replace(match):
        name = match.group(1)
        if name not in palette:
            sys.exit(f"{source}: var(--{name}) is not in the palette")
        used.add(name)
        return palette[name]

    return VARIABLE.sub(replace, text)


def checkTemplates(templates: list):
    for path in templates:
        for number, line in enumerate(readText(path).splitlines(), 1):
            # A selector line, such as "#EditExecutablesDialog #add,", names objects; colors are in values.
            isSelector = line.rstrip().endswith((",", "{")) or not (":" in line or "=" in line)
            if not isSelector and HEX_COLOR.search(line):
                sys.exit(f"{path.relative_to(ROOT)}:{number}: use a palette variable instead of a hex color")


def removeStale(folder: Path, built: list) -> list:
    """Removes the stylesheets and icon folders in folder that the build wrote but no longer builds."""
    keep = {path.name for path in built}
    removed = []
    for path in [*folder.glob(STYLESHEET_PATTERN), *folder.glob(ICON_DIR_PATTERN)]:
        if path.name in keep:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path.name)
    return removed


def build() -> list:
    icons = sorted(ICONS.rglob("*.svg"))
    checkTemplates([TEMPLATE, *icons])
    built = []
    for theme, accents in themes():
        # Rendered from the base palette alone, an icon cannot pick up an accent.
        iconUsed = set()
        iconDir = STYLESHEETS / theme["icon-dir"]
        for icon in icons:
            target = iconDir / icon.relative_to(ICONS)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(resolve(readText(icon), theme, icon.name, iconUsed),
                              encoding="utf-8", newline="")
        built.append(iconDir)
        for source, palette in accents:
            used = set(iconUsed)
            styleSheet = STYLESHEETS / f"Modern Theme {palette['name']}.qss"
            styleSheet.write_text(resolve(readText(TEMPLATE), palette, TEMPLATE.name, used),
                                  encoding="utf-8", newline="")
            unused = set(palette) - used
            if unused:
                print(f"{source}: unused variables: {', '.join(sorted(unused))}")
            print(f"Built {styleSheet.name}")
            built.append(styleSheet)
    for name in removeStale(STYLESHEETS, built):
        print(f"Removed {name}")
    return built


def runningMO2(exe: Path) -> list:
    # Only this install's MO2, another install may be open too.
    command = f"(Get-Process ModOrganizer -ErrorAction Ignore | Where-Object Path -eq '{exe}').Id"
    output = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            capture_output=True, text=True).stdout
    return output.split()


def closeMO2(exe: Path, processIds: list):
    # Without /F taskkill asks MO2 to close, so it saves its settings like a normal exit.
    for processId in processIds:
        subprocess.run(["taskkill", "/PID", processId], capture_output=True)
    deadline = time.monotonic() + CLOSE_TIMEOUT
    while runningMO2(exe):
        if time.monotonic() > deadline:
            sys.exit("MO2 did not close, close it and deploy again")
        time.sleep(0.5)


def changedFiles(source: Path, target: Path) -> list:
    """The files under source that are missing under target or differ from their copy there."""
    return [
        path for path in source.rglob("*")
        if path.is_file() and not (
            (target / path.relative_to(source)).exists()
            and filecmp.cmp(path, target / path.relative_to(source), shallow=False)
        )
    ]


def deploy(built: list, mo2: Path):
    exe = mo2 / "ModOrganizer.exe"
    if not exe.exists():
        sys.exit(f"{mo2} is not an MO2 install: it has no ModOrganizer.exe")
    target = mo2 / "stylesheets"
    # MO2 reads the icons when it applies a stylesheet, and reapplies one only when the stylesheet's own
    # file changes; a changed icon needs a restart.
    iconsChanged = any(changedFiles(path, target / path.name) for path in built if path.is_dir())
    # MO2 reloads a stylesheet when its file changes, so stylesheets deploy without a restart.
    for path in built:
        if path.is_dir():
            shutil.copytree(path, target / path.name, dirs_exist_ok=True)
        else:
            shutil.copy2(path, target / path.name)
    for name in removeStale(target, built):
        print(f"Removed {name} from {target}")
    deployedPlugin = mo2 / "plugins" / PLUGIN.name
    pluginChanged = not (deployedPlugin.exists() and filecmp.cmp(PLUGIN, deployedPlugin, shallow=False))
    if not pluginChanged and not iconsChanged:
        print(f"Deployed to {mo2}")
        return
    # MO2 loads plugins only at startup, so a changed plugin needs a restart.
    processIds = runningMO2(exe)
    if processIds:
        print(f"{'Plugin' if pluginChanged else 'Icons'} changed, restarting MO2")
        closeMO2(exe, processIds)
    shutil.copy2(PLUGIN, deployedPlugin)
    if processIds:
        subprocess.Popen([exe], cwd=mo2, close_fds=True,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    print(f"Deployed to {mo2}")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    builtThemes = build()
    if "--deploy" in arguments:
        rest = arguments[arguments.index("--deploy") + 1:]
        folder = rest[0] if rest and not rest[0].startswith("--") else os.environ.get("MO2_DIR")
        if not folder:
            sys.exit("--deploy needs the MO2 folder, as an argument or in the MO2_DIR environment variable")
        deploy(builtThemes, Path(folder))
