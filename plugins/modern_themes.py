"""Modern Themes: what a Mod Organizer 2 stylesheet cannot do on its own.

The plugin does nothing until the selected stylesheet carries the "mo2-modern-themes" marker comment; it
then watches only the main window for a change of stylesheet. More marker comments turn on the parts that
are a stylesheet's design choice, each described in the README:

    mo2-modern-themes-titlebar: caption=<color> text=<color> border=<color> [dark=0|1]
    mo2-modern-themes-icons: <folder>
    mo2-modern-themes-filter: <color> [<width>px]
    mo2-modern-themes-filter-toggle: <closed icon> <open icon>
    mo2-modern-themes-list-corner: <radius>
    mo2-modern-themes-separators: radius=<radius> margin=<x>,<y>
    mo2-modern-themes-popup-gap: <gap>
    mo2-modern-themes-overlay-scrollbars

With the marker, whatever the others say:
- Context menus and dropdown lists get see-through windows without the Windows drop shadow, so a
  stylesheet's rounded corners show instead of the square window behind them, and a dropdown's list lines
  up with the dropdown, at least as wide.
- The checkable lists (mods, plugins, archives) draw on Fusion instead of the native Windows 11 style,
  which paints its own checkbox under the stylesheet's one.
- A highlighted row of the mod or plugin list, such as a conflict highlight, takes its color across the
  whole row: the indentation left of the name and the square around the checkbox, which a stylesheet's
  rounded checkbox leaves showing the list's background.
- The status bar's API label keeps its background inside the stylesheet's rounded corners and margins;
  MO2 turns on autoFillBackground for it on every update.
- Every list scrolls smoothly, a wheel step gliding there instead of jumping a few rows, at a speed the
  settings set, and scrolls quickly as a mod or a selection is dragged to its top or bottom; the mod and plugin lists' columns always fit the list's width, dragging the edge between
  two columns trades width between just those two; the mod list's top separator stays pinned while its
  mods fill the list; the executables row sits level with the mod list's; the Nexus settings lose an empty
  gap and the Diagnostics settings their wider spacing. Settings turn the smooth scrolling, the pinned separator and the Nexus gap off.

From the other markers:
- Window title bars, the main window's and every dialog's, take the stylesheet's colors (Windows 11).
- MO2's icons come from the stylesheet's SVGs, sharp at any scaling instead of MO2's small PNGs: the
  lists' conflict, flag and content icons, the images MO2 loads as pixmaps such as the notification count
  badges, icons a model hands its view (the log's levels, the filter panel's checkboxes, the Version
  column's) and the icons of menu items MO2 adds in code. The stylesheet sets the toolbar's and the
  buttons' itself, with qproperty-icon.
- MO2 marks an active filter with red borders on the lists, their counters and Clear all Filters; they take
  the stylesheet's color and width. The filter panel's toggle shows the stylesheet's icons for its arrows.
- Lists keep their rows out of their rounded corners: small caps in the content area's corners paint the
  border's corners over them.
- The mod list's separators are rounded bars with a margin around them instead of full row stripes.
- A menu a button opens, and a dropdown's list, leave a gap to the button or the dropdown.
- Scroll bars are hidden everywhere; the stylesheet's vertical ones show over the content's right edge
  while the mouse is near it, nothing stands in for the horizontal ones. A setting brings the regular
  ones back.

Everything is undone when another style is selected.
"""

import ctypes
import logging
import math
import os
import re
import struct
import sys
import threading
import time
from ctypes import wintypes

import mobase
from PyQt6.QtCore import (
    QElapsedTimer,
    QEvent,
    QFileInfo,
    QModelIndex,
    QPersistentModelIndex,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QTimeZone,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDragMoveEvent,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QPixmapCache,
    QRegion,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QStyle,
    QStyledItemDelegate,
    QStyleFactory,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QToolButton,
    QTableView,
    QTreeView,
    QWidget,
)

# The stylesheet's comments that the plugin reads, see the README. The first turns the plugin on.
MARKER = "mo2-modern-themes"
MARKER_PATTERN = re.compile(r"mo2-modern-themes(?![-\w])")
# A marker's value runs to the end of its comment or line; values are words, quoted when they have spaces.
MARKER_TOKEN = re.compile(r'"[^"]*"|\'[^\']*\'|[^\s"\']+')

# The lists whose content area can meet their rounded border, and so gets corner caps.
CORNERED_LISTS = (QTreeView, QTableView)
# Widgets MO2 gives its own stylesheet with a red border while a filter is active, and the red it uses.
FILTER_WIDGETS = ("modList", "espList", "activeModsCounter", "activePluginsCounter", "clearFiltersButton")
MO2_FILTER_RED = re.compile(r"#f00\b|#ff0000\b", re.IGNORECASE)
MO2_BORDER_WIDTH = re.compile(r"(border\s*:\s*)\d+px")
# The filter panel's toggle, MO2 sets its text to these arrows; a stylesheet's icons stand in for them.
FILTER_TOGGLE = "displayCategoriesBtn"
FILTER_TOGGLE_TEXT = ("\u00bb", "\u00ab")
FILTER_TOGGLE_ICON_SIZE = 20
ICON_RESOURCE_PREFIX = ":/MO/gui/"
# MO2 caches its list icons as "<resource>_<size>", the size is 16 or less when the column is narrow.
ICON_SIZES = range(4, 17)
ICON_LISTS = ("modList", "espList")
# Columns whose icons come from the model, a new QIcon per cell, so the cache cannot replace them: the
# mod list's Version column (ModList::COL_VERSION), the log's level column, the filter panel's checkboxes
# and the downloads' incomplete-info warning.
DECORATION_COLUMNS = (("modList", 7), ("logList", 1), ("filters", 0), ("downloadView", 0))
# The sizes the theme's own icons for models and menus are rendered at, Qt picks the nearest.
THEME_ICON_SIZES = (16, 20, 24, 32, 48)
# The window Qt shows a dropdown's list in.
DROPDOWN_CLASS = "QComboBoxPrivateContainer"
# Widgets whose layout differs from MO2's while a stylesheet asks for the plugin, by object name: the
# layout's left, top, right and bottom margins, None to keep one, and its spacing, -1 for the style's own.
LAYOUTS = {
    # The executables and Run row, level with the mod list's row beside it.
    "startGroup": {"margins": (None, 0, None, None)},
    # The settings' Diagnostics page sets twice the spacing between its panels that every other page has.
    "diagnosticsTab": {"spacing": -1},
}
# Lists whose highlighted rows fill the whole row; the mod list's separator delegate does it there when
# the stylesheet asks for separator bars.
ROW_FILL_LISTS = ("modList", "espList", "bsaList")
CHECKABLE_LISTS = ("modList", "espList", "bsaList")
# Labels MO2 sets autoFillBackground on, which paints over the stylesheet's border radius and margins.
FILLED_LABELS = ("apistats",)
# Widget object name: the setting that hides it and its description in the plugin settings. A name that
# other windows use too is given as "ancestor/name", the widget only counts inside that ancestor.
HIDDEN_WIDGETS = {
    # An empty widget between the Nexus settings' Nexus Connection and Options panels, which took a
    # second gap of the layout's spacing there.
    "nexusScrollAreaWidgetContents/widget_6": (
        "hide_nexus_settings_gap",
        "Close the extra gap between the Nexus Connection and Options panels in the Nexus settings",
    ),
}
SCROLL_BAR_SETTING = (
    "overlay_scroll_bars",
    "Hide the scroll bars and show slim ones over the content's edge while the mouse is near it",
)
# In logical pixels, how near the edge the mouse brings an overlay scroll bar in.
SCROLL_BAR_REACH = 40
# In milliseconds, how often the mouse position is checked.
SCROLL_BAR_POLL = 30
SMOOTH_SCROLL_SETTING = ("smooth_scrolling", "Scroll lists smoothly with the mouse wheel")
STICKY_SEPARATOR_SETTING = (
    "sticky_separators",
    "Keep the separator of the mods at the top of the mod list pinned there while scrolling",
)
SCROLL_SPEED_SETTING = ("scroll_speed", "Rows the lists scroll for each mouse wheel step", 3)
# In milliseconds, the time a glide takes to close all but 1/e of the distance left, so a wheel step
# settles in about 4.6 times that.
SMOOTH_SCROLL_TIME_CONSTANT = 45
# Edge scrolling, while a mod or a selection is dragged to a list's top or bottom, in rows a second: as the
# cursor comes into the edge zone, at the list's very edge, and as far past it as the zone is deep, when
# dragging a selection out of the list.
EDGE_SCROLL_SPEEDS = (15, 40, 65)
# In milliseconds, the time edge scrolling takes to get all but 1/e of the way to its speed.
EDGE_SCROLL_RAMP = 60
EDGE_SCROLL_EVENTS = (
    QEvent.Type.DragEnter,
    QEvent.Type.DragMove,
    QEvent.Type.DragLeave,
    QEvent.Type.Drop,
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseMove,
    QEvent.Type.MouseButtonRelease,
)
# In milliseconds, how long a glide waits for the list to paint its last step before it makes the next.
SMOOTH_SCROLL_PAINT_WAIT = 50
# Once easing moves less than a step a frame, the glide moves one step every few frames, the gap growing
# from one frame up to this many, so it slows to a stop evenly instead of a step at ever longer gaps.
SMOOTH_SCROLL_MAX_INTERVAL = 4
# In milliseconds, how often a repainting list checks the cache still holds the theme's icons.
ICON_CHECK_INTERVAL = 500
# Lists whose columns always fit their width.
FITTED_LISTS = ("modList", "espList")


def hiddenWidgetKey(widget: QWidget):
    """The HIDDEN_WIDGETS key the widget answers to, if any."""
    name = widget.objectName()
    for key in HIDDEN_WIDGETS:
        ancestor, _, keyName = key.rpartition("/")
        if keyName != name:
            continue
        if not ancestor:
            return key
        parent = widget.parentWidget()
        while parent is not None:
            if parent.objectName() == ancestor:
                return key
            parent = parent.parentWidget()
    return None


log = logging.getLogger(__name__)

# Window attributes from dwmapi.h. Colors are COLORREFs, 0x00BBGGRR.
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_COLOR_DEFAULT = 0xFFFFFFFF


def markerValue(styleSheet: str, name: str):
    """The value of the stylesheet's "mo2-modern-themes-<name>:" comment, "" without one, None if absent."""
    match = re.search(rf"{MARKER}-{re.escape(name)}(?![-\w])[ \t]*(?::[ \t]*([^\n]*?))?[ \t]*(?:\*/|$)", styleSheet, re.M)
    if match is None:
        return None
    return match.group(1) or ""


def markerTokens(value: str) -> tuple:
    """A marker's words and its key=value settings, quotes taken off."""
    words, settings = [], {}
    for token in MARKER_TOKEN.findall(value or ""):
        key, equals, rest = token.partition("=")
        if equals and not token.startswith(("\"", "'")):
            settings[key.lower()] = rest.strip("\"'")
        else:
            words.append(token.strip("\"'"))
    return words, settings


def markerNumber(text, default: float) -> float:
    try:
        return float(str(text).removesuffix("px"))
    except (TypeError, ValueError):
        return default


class Markers:
    """What the stylesheet's marker comments ask of the plugin; everything off without the main marker."""

    def __init__(self, styleSheet: str, folder: str):
        self.isActive = MARKER_PATTERN.search(styleSheet) is not None
        self.titleBar = None
        self.iconFolder = ""
        self.filterColor = None
        self.filterWidth = None
        self.filterToggle = None
        self.listCornerRadius = 0.0
        self.separators = None
        self.popupGap = 0
        self.overlayScrollBars = False
        if not self.isActive:
            return
        words, settings = markerTokens(markerValue(styleSheet, "titlebar"))
        colors = {key: settings[key] for key in ("caption", "text", "border") if QColor(settings.get(key, "")).isValid()}
        if colors:
            caption = QColor(colors.get("caption", "#000000"))
            dark = settings.get("dark")
            # Dark mode turns the minimize, maximize and close glyphs light, for a dark caption.
            isDark = dark in ("1", "true", "yes") if dark is not None else caption.lightness() < 128
            self.titleBar = TitleBar({key: colorRef(value) for key, value in colors.items()}, isDark)
        words, settings = markerTokens(markerValue(styleSheet, "icons"))
        if words and folder:
            self.iconFolder = os.path.normpath(os.path.join(folder, words[0]))
        words, settings = markerTokens(markerValue(styleSheet, "filter"))
        if words and QColor(words[0]).isValid():
            self.filterColor = QColor(words[0]).name()
            if len(words) > 1:
                self.filterWidth = max(0, round(markerNumber(words[1], 0)))
        words, settings = markerTokens(markerValue(styleSheet, "filter-toggle"))
        paths = [os.path.normpath(os.path.join(folder, word)) for word in words[:2]] if folder else []
        if len(paths) == 2 and all(os.path.isfile(path) for path in paths):
            self.filterToggle = tuple(paths)
        words, settings = markerTokens(markerValue(styleSheet, "list-corner"))
        if words:
            self.listCornerRadius = max(0.0, markerNumber(words[0], 0.0))
        value = markerValue(styleSheet, "separators")
        if value is not None:
            words, settings = markerTokens(value)
            margins = [markerNumber(part, 0) for part in settings.get("margin", "4,2").split(",")]
            marginX, marginY = (margins + margins)[:2]
            self.separators = (markerNumber(settings.get("radius"), 6), int(marginX), int(marginY))
        words, settings = markerTokens(markerValue(styleSheet, "popup-gap"))
        if words:
            self.popupGap = max(0, round(markerNumber(words[0], 0)))
        self.overlayScrollBars = markerValue(styleSheet, "overlay-scrollbars") is not None


class TitleBar:
    """The window title bars' colors, COLORREFs by "caption", "text" and "border", and dark mode."""

    def __init__(self, colors: dict, isDark: bool):
        self.colors = colors
        self.isDark = isDark


def readStyleSheet() -> tuple:
    """Returns the stylesheet's text and the folder it is in, empty when it is not a file."""
    styleSheet = QApplication.instance().styleSheet()
    # MO2 hands Qt the stylesheet as a file URL, so relative image paths resolve next to it.
    if not styleSheet.startswith("file:"):
        return styleSheet, ""
    path = QUrl(styleSheet).toLocalFile()
    try:
        with open(path, encoding="utf-8", errors="replace") as file:
            return file.read(), os.path.dirname(path)
    except OSError:
        return "", ""


def readIconFiles(iconFolder: str) -> dict:
    """Maps each MO2 resource the stylesheet's icon folder replaces to its SVG file.

    A subfolder stands for the resource's, content/plugin.svg replaces :/MO/gui/content/plugin.
    """
    if not iconFolder:
        return {}
    files = {}
    for parent, _, names in os.walk(iconFolder):
        for name in names:
            if name.endswith(".svg"):
                path = os.path.join(parent, name)
                relative = os.path.relpath(path, iconFolder)[: -len(".svg")].replace(os.sep, "/")
                files[ICON_RESOURCE_PREFIX + relative] = path
    return files


def hexString(value: int, layout: str) -> str:
    # Qt's HexString: the value's bytes in memory order, each as its low hex digit, then its high one.
    return "".join("0123456789abcdef"[byte & 0xF] + "0123456789abcdef"[byte >> 4] for byte in struct.pack(layout, value))


def pixmapCacheKey(path: str) -> str:
    """The key QPixmap(path) looks the file up under in the pixmap cache before it loads it."""
    info = QFileInfo(path)
    seconds = info.lastModified(QTimeZone.utc()).toSecsSinceEpoch() & 0xFFFFFFFF
    # The last part is the pixmap type, QPlatformPixmap::PixmapType for a pixmap that has none yet.
    return "qt_pixmap" + info.absoluteFilePath() + hexString(seconds, "<I") + hexString(info.size(), "<q") + hexString(0, "<I")


def colorRef(color: str) -> int:
    """A color as a Windows COLORREF, 0x00BBGGRR."""
    color = QColor(color)
    return color.red() | color.green() << 8 | color.blue() << 16


def renderIcon(renderer: QSvgRenderer, size: int, ratio: float) -> QPixmap:
    # MO2 ships no SVG icon engine, so QIcon would read the SVG as a plain 16px image at any ratio.
    pixels = round(size * ratio)
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def iconFingerprint(icon: QIcon) -> bytes:
    image = icon.pixmap(QSize(16, 16)).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    return bytes(image.constBits().asstring(image.sizeInBytes()))


class ForwardingDelegate(QStyledItemDelegate):
    """Stands in for one of MO2's delegates, which still sizes and edits the cells and draws them."""

    def __init__(self, view: QAbstractItemView, original):
        super().__init__(view)
        self._original = original
        # The view listens to this delegate, editing goes through MO2's.
        self._original.commitData.connect(self.commitData)
        self._original.closeEditor.connect(self.closeEditor)

    def paint(self, painter, option, index):
        self._original.paint(painter, option, index)

    def sizeHint(self, option, index):
        return self._original.sizeHint(option, index)

    def createEditor(self, parent, option, index):
        return self._original.createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        self._original.setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        self._original.setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        self._original.updateEditorGeometry(editor, option, index)

    def editorEvent(self, event, model, option, index):
        return self._original.editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index):
        return self._original.helpEvent(event, view, option, index)


class DecorationDelegate(ForwardingDelegate):
    """Lets MO2's delegate draw a cell, then draws the theme's icon over the model's icon.

    The theme's icons trace the originals' outlines, so drawn on top they cover them.
    """

    def __init__(self, view: QAbstractItemView, columnDelegate, plugin: "ModernThemes"):
        super().__init__(view, columnDelegate or view.itemDelegate())
        self.columnDelegate = columnDelegate
        self._plugin = plugin
        # Qt's own delegate draws just what the model gives it, so this one draws the cell in its place
        # with the theme's icon instead; one of MO2's may draw more, so the icon goes over its drawing.
        self._isPlain = self._original.metaObject().className() == "QStyledItemDelegate"

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        resource = self._plugin.decorationResource(option.icon) if not option.icon.isNull() else None
        if resource is not None:
            option.icon = self._plugin.themeIcon(resource)

    def paint(self, painter, option, index):
        if self._isPlain:
            QStyledItemDelegate.paint(self, painter, option, index)
            return
        self._original.paint(painter, option, index)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(icon, QIcon) or icon.isNull():
            return
        resource = self._plugin.decorationResource(icon)
        if resource is None:
            return
        # Laid out as the cell, the place of its icon; the icon itself is not looked up again.
        itemOption = QStyleOptionViewItem(option)
        QStyledItemDelegate.initStyleOption(self, itemOption, index)
        view = self.parent()
        rect = view.style().subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, itemOption, view)
        size = min(rect.width(), rect.height())
        if size > 0:
            x = rect.x() + (rect.width() - size) // 2
            y = rect.y() + (rect.height() - size) // 2
            painter.drawPixmap(x, y, self._plugin.decorationPixmap(resource, size))


def cellBackground(delegate, option, index):
    """The color a delegate fills a cell with, read back from a one-pixel render of the cell's corner.

    The mod list works out its rows' highlights in its own delegate, the model does not have them.
    """
    sample = QStyleOptionViewItem(option)
    sample.state &= ~QStyle.StateFlag.State_HasFocus
    # Laid out two pixels wide at the cell's right edge: the delegate still fills the background there,
    # but has next to no text to lay out.
    sample.rect = QRect(option.rect.right() - 1, option.rect.top(), 2, option.rect.height())
    image = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.translate(-(option.rect.right() - 1), -(option.rect.top() + 1))
    delegate.paint(painter, sample, index)
    painter.end()
    color = image.pixelColor(0, 0)
    return color if color.alpha() > 0 else None


def fillRowBackground(view: QAbstractItemView, delegate, styler, painter: QPainter, option, index):
    """Fills what a highlighted row's name cell leaves to the list's background with the cell's color.

    That is the indentation left of it and the square around the checkbox, which showed around the
    checkbox's rounded corners. The cell's own drawing covers the rest, and the color is often
    see-through, so it must not go under that too or the cell shows it twice. The styler is a delegate
    of this plugin's, which can set up an option for the cell.
    """
    if index.column() != 0:
        return
    color = cellBackground(delegate, option, index)
    if color is None:
        return
    # MO2 draws a separator's mods from the separator's own left edge, its view reports where.
    cellLeft = min(option.rect.left(), view.visualRect(index).left())
    rect = QRect(cellLeft, option.rect.top(), option.rect.right() + 1 - cellLeft, option.rect.height())
    left = view.header().sectionViewportPosition(0)
    if rect.left() > left:
        painter.fillRect(QRect(left, rect.top(), rect.left() - left, rect.height()), color)
    checkOption = QStyleOptionViewItem(option)
    checkOption.rect = rect
    styler.initStyleOption(checkOption, index)
    if checkOption.features & QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator:
        painter.fillRect(view.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, checkOption, view), color)
    if view.model().hasChildren(index) and option.rect.left() > left:
        drawBranch(view, painter, option, index, QRect(left, rect.top(), option.rect.left() - left, rect.height()))


class RowFillDelegate(ForwardingDelegate):
    """Lets a highlighted row's color reach across the whole row, see fillRowBackground."""

    def paint(self, painter, option, index):
        fillRowBackground(self.parent(), self._original, self, painter, option, index)
        self._original.paint(painter, option, index)


def visibleColumns(header: QHeaderView) -> list:
    """A header's shown columns, left to right as the user arranged them."""
    columns = [column for column in range(header.count()) if not header.isSectionHidden(column)]
    return sorted(columns, key=header.visualIndex)


def drawBranch(view: QAbstractItemView, painter: QPainter, option, index, rect: QRect):
    """Draws the expand arrow of a tree view's row, as the view draws it for a row that is not hovered."""
    branch = QStyleOptionViewItem(option)
    branch.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)
    branch.rect = rect
    # The stylesheet draws a branch only for an item view's option, as the tree view itself passes.
    branch.state |= QStyle.StateFlag.State_Item
    if view.model().hasChildren(index):
        branch.state |= QStyle.StateFlag.State_Children
    if view.isExpanded(index):
        branch.state |= QStyle.StateFlag.State_Open
    if index.sibling(index.row() + 1, 0).isValid():
        branch.state |= QStyle.StateFlag.State_Sibling
    view.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorBranch, branch, painter, view)


class SeparatorDelegate(ForwardingDelegate):
    """Draws the mod list's separators as rounded bars with some room around them, and fills its other
    highlighted rows across, see fillRowBackground.

    MO2 fills every cell of a separator with its color. Each such cell is drawn into an image first, and a
    rounded rectangle spanning the whole row cuts it out, so the color and the name take the bar's shape;
    a separator shows no hover or selection. Qt clips to a path without antialiasing, so the image is cut
    instead. Every column's delegate draws its cell through the view's main one, so this one covers them
    all. A separator's row is taller by the margin above and below, so the bar keeps the height of a row.
    The geometry is the stylesheet's "mo2-modern-themes-separators" comment's: radius, then margins.
    """

    def __init__(self, view: QAbstractItemView, radius: float, marginX: int, marginY: int):
        super().__init__(view, view.itemDelegate())
        self.radius = radius
        self.margin = (marginX, marginY)
        self._isSizing = False

    @staticmethod
    def isSeparator(index) -> bool:
        # Only a separator has a background color in its name column.
        color = index.siblingAtColumn(0).data(Qt.ItemDataRole.BackgroundRole)
        return isinstance(color, QColor) and color.isValid()

    def sizeHint(self, option, index):
        size = self._original.sizeHint(option, index)
        if self.isSeparator(index) and not self._isSizing:
            # A row is as tall as its tallest cell, so the margin goes on top of every column's height. A
            # column delegate may ask this one in turn, which then answers for its own cell only.
            view = self.parent()
            height = size.height()
            self._isSizing = True
            try:
                for column in visibleColumns(view.header()):
                    delegate = view.itemDelegateForColumn(column)
                    if delegate is not None and delegate is not self:
                        height = max(height, delegate.sizeHint(option, index.siblingAtColumn(column)).height())
            finally:
                self._isSizing = False
            size.setHeight(height + 2 * self.margin[1])
        return size

    def paint(self, painter, option, index):
        if not self.isSeparator(index):
            fillRowBackground(self.parent(), self._original, self, painter, option, index)
            self._original.paint(painter, option, index)
            return
        view = self.parent()
        header = view.header()
        columns = visibleColumns(header)
        if not columns:
            self._original.paint(painter, option, index)
            return
        last = columns[-1]
        # The bar starts after the name column's branch arrow and ends with the last column.
        left = view.visualRect(index.siblingAtColumn(0)).left()
        right = header.sectionViewportPosition(last) + header.sectionSize(last)
        # The cell is drawn a pixel wider on both sides, so it fills the device pixel it shares with the
        # next cell at fractional scaling even when only one of them repaints.
        cellOption = QStyleOptionViewItem(option)
        cellOption.rect = option.rect.adjusted(-1, 0, 1, 0)
        # Drawn as neither hovered, selected nor focused, so MO2 fills it with the separator's own color and
        # text color, and no highlight or focus frame replaces them; neither changes the bar's color.
        isSelected = bool(option.state & QStyle.StateFlag.State_Selected)
        isHovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        cellOption.state = option.state & ~(
            QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_HasFocus
        )
        rect = cellOption.rect
        marginX, marginY = self.margin
        # The bar starts where the style puts a row's checkbox, so it lines up with the checkboxes of the
        # mods below it; their name cells start where the separator's does.
        checkOption = QStyleOptionViewItem(option)
        checkOption.rect = QRect(left, option.rect.top(), right - left, option.rect.height())
        checkOption.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        check = view.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, checkOption, view)
        barLeft = check.left() if check.isValid() and check.left() >= left else left + marginX
        ratio = painter.device().devicePixelRatioF()
        toDevice = painter.deviceTransform()
        fromDevice, isInvertible = toDevice.inverted()
        # The bar's top and bottom lie on whole pixels of the window, so every cell's piece of it has the
        # same edges.
        top, bottom = rect.top() + marginY, rect.top() + rect.height() - marginY
        if isInvertible:
            top = fromDevice.map(QPointF(0, round(toDevice.map(QPointF(0, top)).y()))).y()
            bottom = fromDevice.map(QPointF(0, round(toDevice.map(QPointF(0, bottom)).y()))).y()
        bar = QRectF(barLeft, top, right - marginX - barLeft, bottom - top)
        if isSelected:
            # Qt fills a selected row's background only left of the bar; the cell gets the same selected
            # row background before the bar goes on top.
            rowOption = QStyleOptionViewItem(option)
            view.style().drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewRow, rowOption, painter, view)
        elif isHovered:
            # Qt fills a hovered row with the stylesheet's hover color behind its cells, the strip with the
            # arrow included. A separator shows no hover, so its row goes back to the list's background,
            # and the name's cell draws the arrow again.
            viewport = view.viewport()
            area = QRect(option.rect)
            if index.column() == 0:
                area.setLeft(0)
            painter.fillRect(area, viewport.palette().brush(viewport.backgroundRole()))
            if index.column() == 0:
                drawBranch(view, painter, option, index, QRect(0, option.rect.top(), left, option.rect.height()))
        # Every cell is drawn into an image and cut to the bar, the middle ones too: clipped straight onto
        # the list instead, they came out a device pixel lower than the ends in MO2's window at fractional
        # scaling, though the clip's edges were on whole pixels.
        # The image covers the cell's whole device pixels and starts on one. A cell edge can fall inside a
        # device pixel at fractional scaling, and an image placed there would leave a seam with the next.
        # It starts on a whole pixel of the window, not of the viewport: at fractional scaling the viewport
        # itself can sit half a pixel into one, and an image placed on its grid would land between the
        # window's pixels, its bar shifted from the checkboxes, which are drawn in place.
        corner = toDevice.map(QPointF(rect.x(), rect.y()))
        farCorner = toDevice.map(QPointF(rect.x() + rect.width(), rect.y() + rect.height()))
        deviceLeft, deviceTop = math.floor(corner.x()), math.floor(corner.y())
        deviceRight, deviceBottom = math.ceil(farCorner.x()), math.ceil(farCorner.y())
        image = QImage(deviceRight - deviceLeft, deviceBottom - deviceTop, QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        origin = fromDevice.map(QPointF(deviceLeft, deviceTop)) if isInvertible else QPointF(rect.topLeft())
        imagePainter = QPainter(image)
        imagePainter.translate(-origin)
        self._original.paint(imagePainter, cellOption, index)
        imagePainter.end()
        imagePainter = QPainter(image)
        imagePainter.translate(-origin)
        # Erases the cell around the bar. A composition mode only acts where something is drawn, so the
        # shape drawn is the cell with the bar cut out; only its coverage counts, not its color.
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRect(QRectF(origin.x(), origin.y(), image.width() / ratio, image.height() / ratio))
        path.addRoundedRect(bar, self.radius, self.radius)
        imagePainter.setRenderHint(QPainter.RenderHint.Antialiasing)
        imagePainter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        imagePainter.fillPath(path, Qt.GlobalColor.black)
        imagePainter.end()
        painter.drawImage(origin, image)


class ScrollBarOverlay:
    """Hides a scroll area's scroll bars and stands a slim vertical bar over the viewport's right edge in.

    The hidden vertical bar keeps scrolling the area, the mouse wheel included, the overlay follows it and
    sets it when dragged. Nothing replaces the horizontal bar, the area never scrolls sideways by a bar.
    The bar is as wide as the stylesheet makes a vertical scroll bar, and is named
    "modernThemesOverlayScrollBar" for a stylesheet to tell it apart.

    The bar is a small window of its own, frameless and see-through, owned by the area's window so it stays
    above it. Any widget inside the area's window would cost every scroll step a repaint of the whole list:
    Qt scrolls a viewport by moving the pixels already painted only while no sibling overlaps it, and it
    moves the viewport's own children with the content, so one there would have to be put back after every
    step, which paints the rows under it again.
    """

    def __init__(self, area: QAbstractScrollArea):
        self.area = area
        self.policies = (area.verticalScrollBarPolicy(), area.horizontalScrollBarPolicy())
        self.real = area.verticalScrollBar()
        self.isShowing = False
        self.bar = None
        if self.policies[0] != Qt.ScrollBarPolicy.ScrollBarAlwaysOff:
            self.bar = QScrollBar(Qt.Orientation.Vertical, area.window())
            self.bar.setWindowFlags(
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.NoDropShadowWindowHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.bar.setObjectName("modernThemesOverlayScrollBar")
            self.bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.bar.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.bar.hide()
            self.bar.ensurePolished()
            self._sync()
            self.real.rangeChanged.connect(self.bar.setRange)
            self.real.valueChanged.connect(self.bar.setValue)
            self.bar.valueChanged.connect(self.real.setValue)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # A scroll area's page fills it to the edge, panels and all, where a list leaves room in its last
        # column; the page keeps a gutter on its right for the bar instead.
        self.page = area.widget() if isinstance(area, QScrollArea) and self.bar is not None else None
        if self.page is not None:
            margins = self.page.contentsMargins()
            self.pageMargins = margins
            self.page.setContentsMargins(
                margins.left(), margins.top(), margins.right() + self.thickness(), margins.bottom()
            )

    def thickness(self) -> int:
        return max(1, self.bar.sizeHint().width())

    def _sync(self):
        self.bar.setRange(self.real.minimum(), self.real.maximum())
        self.bar.setPageStep(self.real.pageStep())
        self.bar.setSingleStep(self.real.singleStep())
        self.bar.setValue(self.real.value())

    def _place(self):
        # In screen coordinates, the window follows the viewport wherever its own window goes.
        viewport = self.area.viewport()
        thickness = self.thickness()
        topLeft = viewport.mapToGlobal(QPoint(viewport.width() - thickness, 0))
        place = QRect(topLeft, QSize(thickness, viewport.height()))
        if self.bar.geometry() != place:
            self.bar.setGeometry(place)

    def follow(self, cursor):
        """Shows the bar while the cursor, a global position or None, is near the right edge."""
        if self.bar is None:
            return
        self._place()
        isNear = False
        viewport = self.area.viewport()
        if cursor is not None and viewport.isVisible() and self.real.maximum() > self.real.minimum():
            globalRect = QRect(viewport.mapToGlobal(QPoint(0, 0)), viewport.size())
            isNear = globalRect.contains(cursor) and globalRect.right() - cursor.x() < SCROLL_BAR_REACH
        self._show(isNear or self.bar.isSliderDown())

    def _show(self, visible: bool):
        if visible == self.isShowing:
            return
        self.isShowing = visible
        if visible:
            self._sync()
            self._place()
            self.bar.show()
            self.bar.raise_()
        else:
            # A hidden bar takes no clicks meant for the content under it.
            self.bar.hide()

    def remove(self):
        if self.bar is not None:
            self.bar.hide()
            self.bar.deleteLater()
        self.area.setVerticalScrollBarPolicy(self.policies[0])
        self.area.setHorizontalScrollBarPolicy(self.policies[1])
        if self.page is not None and self.area.widget() is self.page:
            self.page.setContentsMargins(self.pageMargins)


class ColumnFitter:
    """Keeps a list's columns exactly as wide as its viewport.

    Dragging the edge between two columns moves just that edge, the way a splitter does: the column on its
    right gives up or takes the width, so any column can grow or shrink and the total never changes. The
    last column's right edge stays at the viewport's edge. When the viewport changes width every column
    scales with it, from proportions only the user's drags change, so a passing narrow state such as the
    window's first layout loses nothing.
    """

    def __init__(self, view: QAbstractItemView):
        self.view = view
        self.header = view.header()
        self.modes = [self.header.sectionResizeMode(column) for column in range(self.header.count())]
        self.stretchLastSection = self.header.stretchLastSection()
        self._isFitting = False
        self._isRemoved = False
        self._configure()
        self.proportions = {}
        self._rememberProportions()
        self.header.sectionResized.connect(self._onSectionResized)
        QTimer.singleShot(0, self.fit)

    def _isConfigured(self) -> bool:
        return not self.header.stretchLastSection() and all(
            self.header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
            for column in range(self.header.count())
        )

    def _configure(self):
        # Every column can be dragged, and none stretches into the space the others leave.
        self._isFitting = True
        self.header.setStretchLastSection(False)
        for column in range(self.header.count()):
            self.header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        self._isFitting = False

    def _rememberProportions(self):
        columns = visibleColumns(self.header)
        total = sum(self.header.sectionSize(column) for column in columns)
        if total > 0:
            self.proportions = {column: self.header.sectionSize(column) / total for column in columns}

    def _resize(self, column: int, size: int):
        if self.header.sectionSize(column) != size:
            self._isFitting = True
            self.header.resizeSection(column, size)
            self._isFitting = False

    def _onSectionResized(self, column: int, oldSize: int, newSize: int):
        if self._isFitting:
            return
        if not self._isConfigured():
            # MO2 sets its own resize modes once it first paints, that is no drag.
            self.fit()
            return
        if oldSize == 0 or newSize == 0:
            # A column was shown or hidden, the others make room for it or share its width.
            self._rememberProportions()
            self.fit()
            return
        columns = visibleColumns(self.header)
        if column not in columns:
            return
        position = columns.index(column)
        if position + 1 == len(columns):
            # The last column's right edge is the viewport's edge.
            self._resize(column, oldSize)
            return
        neighbor = columns[position + 1]
        minimum = self.header.minimumSectionSize()
        neighborSize = self.header.sectionSize(neighbor) - (newSize - oldSize)
        if neighborSize < minimum:
            # The column grows only as far as its neighbor can shrink.
            self._resize(column, newSize - (minimum - neighborSize))
            neighborSize = minimum
        self._resize(neighbor, neighborSize)
        self._rememberProportions()

    def fit(self):
        if self._isRemoved:
            return
        if not self._isConfigured():
            self._configure()
        # Before the window is laid out the viewport has no real width yet.
        if not self.view.isVisible():
            return
        columns = visibleColumns(self.header)
        if not columns:
            return
        if any(column not in self.proportions for column in columns):
            self._rememberProportions()
        width = self.view.viewport().width()
        minimum = self.header.minimumSectionSize()
        sizes = [max(minimum, round(self.proportions[column] * width)) for column in columns[:-1]]
        # The last column takes up the rounding, so the columns end right at the viewport's edge.
        sizes.append(max(minimum, width - sum(sizes)))
        for column, size in zip(columns, sizes):
            self._resize(column, size)

    def remove(self):
        self._isRemoved = True
        disconnect(self.header.sectionResized, self._onSectionResized)
        for column, mode in enumerate(self.modes):
            self.header.setSectionResizeMode(column, mode)
        self.header.setStretchLastSection(self.stretchLastSection)


class FrameClock(QObject):
    """Calls its listeners once for every frame the screen shows, on the GUI thread.

    Qt's timers on Windows fire on the 15.6ms system tick at best, about 64 times a second, so a glide
    driven by one stays below a high refresh screen's rate. A thread waits on DwmFlush, which returns when
    the desktop compositor has shown its next frame, and hands each frame to the GUI thread. It sleeps
    while nothing listens.
    """

    tick = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._listeners = []
        self._isWanted = threading.Event()
        self._isPending = False
        self.tick.connect(self._onTick)
        threading.Thread(target=self._run, name="Modern Themes frame clock", daemon=True).start()

    def _run(self):
        dwmFlush = ctypes.windll.dwmapi.DwmFlush
        while True:
            self._isWanted.wait()
            if dwmFlush() != 0:
                time.sleep(1 / 120)
            # A GUI thread that falls behind gets one tick, not a queue of them.
            if not self._isPending:
                self._isPending = True
                self.tick.emit()

    def _onTick(self):
        self._isPending = False
        for listener in list(self._listeners):
            listener()

    def add(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)
        self._isWanted.set()

    def remove(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)
        if not self._listeners:
            self._isWanted.clear()


def disconnect(signal, slot):
    """Disconnects the slot, if the signal and the slot are both still there."""
    try:
        signal.disconnect(slot)
    except (RuntimeError, TypeError):
        pass


def wholePixelStep(ratio: float) -> int:
    """The smallest scroll distance in logical pixels that is a whole number of device pixels."""
    for step in range(1, 9):
        if abs(step * ratio - round(step * ratio)) < 1e-6:
            return step
    return 1


class SmoothScroller:
    """Glides a list to where a wheel step takes it instead of jumping there, and scrolls it while a mod or
    a selection is dragged to its top or bottom.

    The list scrolls by pixel so it can stop between rows, and moves once per frame the screen shows. Each
    frame closes a fixed share of the remaining distance per millisecond, worked out from the time that
    really passed, so a step that comes while the list glides only moves where it is heading. Anything
    else that moves the scroll bar, a drag, the keyboard or MO2 showing an item, stops the glide.

    Qt's own edge scrolling counts in the scroll bar's units, pixels once the list scrolls by pixel, and
    starts at one a tick: it crept. This one starts as the cursor comes into the edge zone, at
    EDGE_SCROLL_SPEEDS rows a second, faster the nearer the edge, and gets up to speed within about
    EDGE_SCROLL_RAMP milliseconds.
    """

    def __init__(self, view: QAbstractItemView, plugin: "ModernThemes"):
        self.view = view
        self.mode = view.verticalScrollMode()
        self.bar = view.verticalScrollBar()
        self._plugin = plugin
        self.position = 0.0
        self.target = 0.0
        self.origin = 0
        self.step = 1
        self.interval = 1
        self.framesWaited = 0
        self.maxMove = 1
        self.isGliding = False
        self._isMoving = False
        # Whether the list still has to paint the last step, and since when.
        self._awaitingPaint = False
        self._stepTimer = QElapsedTimer()
        self.clock = QElapsedTimer()
        self.autoFill = view.viewport().autoFillBackground()
        self.autoScroll = view.hasAutoScroll()
        # Edge scrolling: "drag" while a drag is over the list, "select" while the button is down on it.
        self._edgeState = None
        self._edgePos = QPoint()
        self._edgeSpeed = 0.0
        self._edgePosition = 0.0
        self._edgeOrigin = 0
        self._edgeValue = 0
        self._edgeMoved = False
        self._edgeClock = QElapsedTimer()
        self._isEdgeScrolling = False
        self._drag = None
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setAutoScroll(False)
        self.bar.valueChanged.connect(self._onValueChanged)
        self.makeOpaque()

    def makeOpaque(self):
        """Lets Qt scroll the list by moving its pixels and painting only the rows that come into view.

        A stylesheet background turns the viewport's own fill off and draws itself instead, then Qt cannot
        tell the viewport is opaque and paints all of it again for every pixel it scrolls. The fill is the
        stylesheet's background color, so nothing looks different. Every restyle of the list turns it off
        again, MO2's filter border's too, so the event filter calls this after each. A see-through
        background stays as it is: a fill would hide what shows through it.
        """
        viewport = self.view.viewport()
        if viewport.palette().brush(viewport.backgroundRole()).isOpaque():
            viewport.setAutoFillBackground(True)

    def wheel(self, event) -> bool:
        """Starts or extends a glide for a wheel event, returns whether it took the event."""
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        delta = event.angleDelta().y()
        if delta == 0 or self.bar.maximum() <= self.bar.minimum():
            return False
        if not self.isGliding:
            self.origin = self.bar.value()
            self.position = self.target = float(self.origin)
            self.step = wholePixelStep(self.view.devicePixelRatioF())
            self.clock.start()
            self.isGliding = True
            self._plugin.frameClock.add(self._onFrame)
        # A new step speeds the glide up again.
        self.interval = 1
        self.framesWaited = 0
        rowHeight = self._rowHeight()
        # A tree view paints all of itself again, instead of moving its pixels, for a scroll of more
        # pixels than it has rows in view. A frame moves less than that, in whole steps.
        rows = max(self.view.viewport().height() // max(rowHeight, 1) - 1, 1)
        self.maxMove = max(self.step, (rows // self.step) * self.step)
        distance = -delta / 120 * self._plugin.scrollRows * rowHeight
        target = max(float(self.bar.minimum()), min(float(self.bar.maximum()), self.target + distance))
        self.target = float(self._snap(target))
        return True

    def _snap(self, position: float) -> int:
        # Qt moves the pixels already painted only by whole device pixels, any other move paints the whole
        # list again. Every value a glide passes is a whole number of steps from where it started.
        return self.origin + self.step * round((position - self.origin) / self.step)

    def _rowHeight(self) -> int:
        height = self.view.sizeHintForRow(0)
        return height if height > 0 else self.view.fontMetrics().height() + 4

    def painted(self):
        """The list painted, so the glide may take its next step."""
        self._awaitingPaint = False

    def _onFrame(self):
        # One step per paint. A frame can come before the list painted the last one, when the frame before
        # was late; a second step then made Qt paint the whole list again, a stutter, because the list's
        # children, the pinned separator and the corner caps, moved back after the first. The time waited
        # goes into the next step, which the cap on a step's size still holds.
        if self._awaitingPaint and self._stepTimer.elapsed() < SMOOTH_SCROLL_PAINT_WAIT:
            return
        # restart() counts whole milliseconds, a quarter of a frame at 240 Hz, which would make the
        # distance each frame moves wobble.
        elapsed = self.clock.nsecsElapsed() / 1e6
        self.clock.restart()
        distance = self.target - self.position
        move = distance * (1 - math.exp(-elapsed / SMOOTH_SCROLL_TIME_CONSTANT))
        if abs(move) > self.maxMove:
            move = math.copysign(self.maxMove, move)
        if abs(move) < self.step:
            # Easing alone crawls over the last pixels, a step at ever longer, uneven gaps. Here a step
            # comes every few frames instead, the gap the easing asks for but never shrinking and never
            # longer than SMOOTH_SCROLL_MAX_INTERVAL frames, so the glide slows evenly to its stop.
            wanted = round(self.step / max(abs(move), 1e-6))
            self.interval = min(SMOOTH_SCROLL_MAX_INTERVAL, max(self.interval, wanted))
            self.framesWaited += 1
            if self.framesWaited < self.interval:
                return
            self.framesWaited = 0
            move = math.copysign(self.step, distance)
            self.position = float(self._snap(self.position))
        if abs(move) >= abs(self.target - self.position):
            self.position = self.target
            self._stop()
        else:
            self.position += move
        value = self._snap(self.position)
        if value != self.bar.value():
            self._isMoving = True
            self.bar.setValue(value)
            self._isMoving = False
            self._awaitingPaint = self.view.viewport().isVisible()
            self._stepTimer.start()

    def _stop(self):
        self.isGliding = False
        self._plugin.frameClock.remove(self._onFrame)

    def viewportEvent(self, event):
        """Follows drags and button presses over the list, for edge scrolling."""
        eventType = event.type()
        if eventType in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            self._drag = (event.mimeData(), event.possibleActions(), event.buttons(), event.modifiers())
            self._followEdge("drag", event.position().toPoint())
            self._edgeMoved = True
        elif eventType in (QEvent.Type.DragLeave, QEvent.Type.Drop):
            self._edgeState = None
            self._drag = None
        elif eventType == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._followEdge("select", event.position().toPoint())
        elif eventType == QEvent.Type.MouseMove and self._edgeState == "select":
            self._edgePos = event.position().toPoint()
            self._edgeMoved = True
        elif eventType == QEvent.Type.MouseButtonRelease and self._edgeState == "select":
            self._edgeState = None

    def _followEdge(self, state: str, position: QPoint):
        if state != self._edgeState:
            # As in Qt, a press scrolls only once the mouse moves; a click near the edge stays put.
            self._edgeMoved = False
        self._edgeState = state
        self._edgePos = position
        if not self._isEdgeScrolling:
            self._isEdgeScrolling = True
            self._restartEdge()
            self._edgeClock.start()
            self._plugin.frameClock.add(self._onEdgeFrame)

    def _restartEdge(self):
        # From rest, from where the list is now.
        self._edgeSpeed = 0.0
        self._edgePosition = float(self.bar.value())
        self._edgeOrigin = self._edgeValue = self.bar.value()
        self.step = wholePixelStep(self.view.devicePixelRatioF())

    def _stopEdge(self):
        self._isEdgeScrolling = False
        self._edgeSpeed = 0.0
        self._plugin.frameClock.remove(self._onEdgeFrame)

    def _onEdgeFrame(self):
        if self._edgeState is None:
            self._stopEdge()
            return
        if self._awaitingPaint and self._stepTimer.elapsed() < SMOOTH_SCROLL_PAINT_WAIT:
            return
        elapsed = self._edgeClock.nsecsElapsed() / 1e6
        self._edgeClock.restart()
        bar = self.bar
        height = self.view.viewport().height()
        margin = max(self.view.autoScrollMargin(), 1)
        y = self._edgePos.y()
        if y < margin:
            direction, depth = -1, (margin - y) / margin
        elif y >= height - margin:
            direction, depth = 1, (y - (height - margin)) / margin
        else:
            direction, depth = 0, 0.0
        atEnd = bar.value() <= bar.minimum() if direction < 0 else bar.value() >= bar.maximum()
        if direction == 0 or atEnd or not self._edgeMoved or bar.value() != self._edgeValue:
            # Out of the edge zone, nowhere left to go, not moved yet, or scrolled by something else: the
            # next scroll starts from rest, from here.
            self._restartEdge()
            if direction == 0 or atEnd or not self._edgeMoved:
                return
        if self.isGliding:
            self._stop()
        entering, edge, beyond = EDGE_SCROLL_SPEEDS
        rows = entering + (edge - entering) * depth if depth <= 1 else edge + (beyond - edge) * min(depth - 1, 1)
        target = direction * rows * self._rowHeight() / 1000
        if self._edgeSpeed * direction < 0:
            self._edgeSpeed = 0.0
        self._edgeSpeed += (target - self._edgeSpeed) * (1 - math.exp(-elapsed / EDGE_SCROLL_RAMP))
        # A frame after a stall moves no further than a tree view still scrolls by moving its pixels.
        rowsInView = max(height // max(self._rowHeight(), 1) - 1, 1)
        move = max(-rowsInView, min(rowsInView, self._edgeSpeed * elapsed))
        self._edgePosition = max(float(bar.minimum()), min(float(bar.maximum()), self._edgePosition + move))
        step = self.step
        value = self._edgeOrigin + step * round((self._edgePosition - self._edgeOrigin) / step)
        if value != bar.value():
            self._isMoving = True
            bar.setValue(value)
            self._isMoving = False
            self._edgeValue = bar.value()
            self._awaitingPaint = self.view.viewport().isVisible()
            self._stepTimer.start()
            self._refreshEdgeTarget()

    def _refreshEdgeTarget(self):
        """Lets the list follow the still cursor over the rows that scrolled under it: the drop indicator
        while dragging, the selection while selecting, as Qt's own edge scrolling does."""
        viewport = self.view.viewport()
        if self._edgeState == "drag" and self._drag is not None:
            data, actions, buttons, modifiers = self._drag
            QApplication.sendEvent(viewport, QDragMoveEvent(self._edgePos, actions, data, buttons, modifiers))
        elif self._edgeState == "select":
            position = QPointF(self._edgePos)
            event = QMouseEvent(
                QEvent.Type.MouseMove,
                position,
                QPointF(viewport.mapToGlobal(self._edgePos)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                QApplication.keyboardModifiers(),
            )
            QApplication.sendEvent(viewport, event)

    def _onValueChanged(self, value: int):
        if not self._isMoving and self.isGliding:
            self._stop()

    def remove(self):
        self._stop()
        self._edgeState = None
        self._stopEdge()
        self.bar.valueChanged.disconnect(self._onValueChanged)
        self.view.setVerticalScrollMode(self.mode)
        self.view.setAutoScroll(self.autoScroll)
        self.view.viewport().setAutoFillBackground(self.autoFill)


class StickySeparator(QWidget):
    """Keeps the separator whose mods fill the top of the mod list pinned over the list's top edge.

    It shows while the list's top row is one of an expanded separator's mods, or the separator itself
    partly scrolled away, and the next separator pushes it up and out as it arrives. The list's own
    delegates draw it, so it looks like the separator's row. Clicking it scrolls back to the separator.

    It is a child of the viewport, so the list still scrolls by moving the pixels already painted.
    Scrolling moves it with the content and it goes back to the top after every step, which repaints
    only the row or two under it. While no separator is pinned it waits just above the list's top edge.
    """

    def __init__(self, view: QAbstractItemView):
        super().__init__(view.viewport())
        self.view = view
        self.separator = None
        self._isRemoved = False
        # It fills itself, so moving it back repaints only the strip it uncovers.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.hide()
        # Connected after the list's own handlers, so these run once the list has moved or changed.
        self._connections = [
            (view.verticalScrollBar().valueChanged, self.place),
            (view.expanded, self.place),
            (view.collapsed, self.place),
            (view.header().sectionResized, self.place),
        ]
        model = view.model()
        for signal in (model.layoutChanged, model.modelReset, model.rowsInserted, model.rowsRemoved):
            self._connections.append((signal, self._placeLater))
        for signal, slot in self._connections:
            signal.connect(slot)

    def _placeLater(self, *args):
        QTimer.singleShot(0, self.place)

    def _currentSeparator(self):
        view = self.view
        viewport = view.viewport()
        top = view.indexAt(QPoint(viewport.width() // 2, 0))
        if not top.isValid():
            return None
        top = top.siblingAtColumn(0)
        if top.parent().isValid():
            separator = top
            while separator.parent().isValid():
                separator = separator.parent()
        elif view.visualRect(top).top() < 0 and view.model().hasChildren(top):
            separator = top
        else:
            return None
        if not SeparatorDelegate.isSeparator(separator) or not view.isExpanded(separator):
            return None
        return separator

    def place(self, *args):
        if self._isRemoved:
            return
        separator = self._currentSeparator()
        if separator is None:
            # Parked just above the list rather than hidden: hiding it, or showing it again, made Qt paint
            # the whole list again, a stutter in a fast scroll. Out of view, it keeps what it showed.
            if not self.isHidden():
                parked = QRect(0, -self.height() - 1, self.view.viewport().width(), self.height())
                if self.geometry() != parked:
                    self.setGeometry(parked)
            return
        view = self.view
        height = view.visualRect(separator).height()
        top = 0
        following = separator.sibling(separator.row() + 1, 0)
        if following.isValid():
            # The next separator pushes this one up as it reaches the top.
            top = min(0, view.visualRect(following).top() - height)
        place = QRect(0, top, view.viewport().width(), height)
        if self.geometry() != place:
            self.setGeometry(place)
        if self.separator is None or QModelIndex(self.separator) != separator:
            self.separator = QPersistentModelIndex(separator)
            self.update()
        if self.isHidden():
            # Shown once; from then on it parks out of view instead of hiding.
            self.show()
            self.raise_()

    def paintEvent(self, event):
        if self.separator is None or not self.separator.isValid():
            return
        view = self.view
        header = view.header()
        index = QModelIndex(self.separator)
        viewport = view.viewport()
        painter = QPainter(self)
        painter.fillRect(self.rect(), viewport.palette().brush(viewport.backgroundRole()))
        option = QStyleOptionViewItem()
        option.initFrom(view)
        option.widget = view
        option.font = view.font()
        size = view.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize, None, view)
        option.decorationSize = QSize(size, size)
        option.displayAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        option.textElideMode = view.textElideMode()
        # The view's own state says hovered whenever the mouse is anywhere over the list; the pinned row is
        # drawn as the row is when the mouse is elsewhere, selected only if it is.
        option.state &= ~(QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_HasFocus)
        if view.selectionModel() is not None and view.selectionModel().isSelected(index):
            option.state |= QStyle.StateFlag.State_Selected
        # The name's cell starts after the indentation for the arrow, as the row's own does, so the name
        # sits where it does in the row.
        indentation = view.visualRect(index).left()
        for column in visibleColumns(header):
            left = header.sectionViewportPosition(column)
            right = left + header.sectionSize(column)
            if column == index.column():
                left = max(left, indentation)
            cell = QStyleOptionViewItem(option)
            cell.rect = QRect(left, 0, right - left, self.height())
            cellIndex = index.siblingAtColumn(column)
            view.itemDelegateForIndex(cellIndex).paint(painter, cell, cellIndex)
        # The expanded arrow in the indentation left of the name.
        if indentation > 0:
            drawBranch(view, painter, option, index, QRect(0, 0, indentation, self.height()))
        painter.end()

    def mousePressEvent(self, event):
        if self.separator is not None and self.separator.isValid():
            self.view.scrollTo(QModelIndex(self.separator), QAbstractItemView.ScrollHint.PositionAtTop)

    def remove(self):
        self._isRemoved = True
        for signal, slot in self._connections:
            disconnect(signal, slot)
        self.hide()
        self.deleteLater()


def listCornersAtBorder(view: QAbstractItemView, radius: float) -> list:
    """The corners of a list's content area that meet its rounded border, as (isRight, isBottom) pairs.

    Not under a header or beside a table's row header or a scroll bar. Qt leaves the stylesheet's margins
    out of the contents rectangle, so an edge within the corners' radius of it counts as meeting the border.
    """
    viewport = view.viewport()
    area = viewport.geometry()
    inner = view.contentsRect()
    if viewport.width() <= 2 * radius or viewport.height() <= 2 * radius:
        return []
    atLeft = area.left() - inner.left() <= radius
    atRight = inner.right() - area.right() <= radius
    atTop = area.top() - inner.top() <= radius
    atBottom = inner.bottom() - area.bottom() <= radius
    return [
        (isRight, isBottom)
        for isRight, isBottom in ((False, False), (True, False), (False, True), (True, True))
        if (atRight if isRight else atLeft) and (atBottom if isBottom else atTop)
    ]


class CornerCap(QWidget):
    """Covers one corner of a list's content area with what belongs outside the list's rounded border.

    Qt does not clip a list's rows to its rounded border, so they would draw over its corners; nor does it
    paint the frame under an opaque content area, so a mask on it would not do. The cap paints the frame's
    corner itself, the
    background behind the list and then the list's own border, and leaves the inside of the rounding
    clear, smooth-edged, for the rows. It is a child of the content area, so scrolling moves it with the
    rows; the list puts it back after every step, which repaints only its few pixels.
    """

    def __init__(self, view: QAbstractItemView, isRight: bool, isBottom: bool, radius: float):
        super().__init__(view.viewport())
        self.setObjectName("modernThemesCornerCap")
        self.view = view
        self.isRight = isRight
        self.isBottom = isBottom
        self.radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        size = math.ceil(radius)
        self.resize(size, size)
        self._image = None
        self._imageKey = None
        self.place()
        self.show()

    def invalidate(self):
        self._image = None
        self.update()

    def place(self):
        viewport = self.view.viewport()
        x = viewport.width() - self.width() if self.isRight else 0
        y = viewport.height() - self.height() if self.isBottom else 0
        if self.pos() != QPoint(x, y):
            self.move(x, y)
        self.raise_()

    def paintEvent(self, event):
        # Painted again on every scroll step it is put back after, so its image is kept until the list's
        # look or place changes.
        ratio = self.devicePixelRatioF()
        key = (ratio, self.mapTo(self.window(), QPoint(0, 0)), self.window().size())
        if self._image is None or self._imageKey != key:
            self._image = self._render(ratio)
            self._imageKey = key
        QPainter(self).drawImage(0, 0, self._image)

    def _render(self, ratio: float) -> QImage:
        image = QImage(round(self.width() * ratio), round(self.height() * ratio), QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        # Everything under the cap but the content area and its rows: the window and the widgets the list
        # sits in, then the list's frame, each without its children.
        chain = []
        widget = self.view
        while widget is not None:
            chain.append(widget)
            if widget.isWindow():
                break
            widget = widget.parentWidget()
        origin = self.mapTo(self.window(), QPoint(0, 0))
        for widget in reversed(chain):
            offset = widget.mapTo(self.window(), QPoint(0, 0)) if not widget.isWindow() else QPoint(0, 0)
            source = QRect(origin - offset, self.size())
            flags = QWidget.RenderFlag.DrawWindowBackground if widget.isWindow() else QWidget.RenderFlag(0)
            widget.render(painter, QPoint(0, 0), QRegion(source), flags)
        # The inside of the rounding is the rows'. Its center is a radius in from the list's corner.
        center = QPointF(
            self.width() - self.radius if self.isRight else self.radius,
            self.height() - self.radius if self.isBottom else self.radius,
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        disc = QPainterPath()
        disc.addEllipse(center, self.radius, self.radius)
        painter.fillPath(disc, Qt.GlobalColor.black)
        painter.end()
        return image


class ListCorners:
    """The corner caps of one list, kept in its content area's corners."""

    def __init__(self, view: QAbstractItemView):
        self.view = view
        self.caps = {}
        view.verticalScrollBar().valueChanged.connect(self.place)
        view.horizontalScrollBar().valueChanged.connect(self.place)

    def apply(self, radius: float):
        wanted = set(listCornersAtBorder(self.view, radius)) if radius else set()
        for key in list(self.caps):
            if key not in wanted or self.caps[key].radius != radius:
                self.caps.pop(key).deleteLater()
        for key in wanted - set(self.caps):
            self.caps[key] = CornerCap(self.view, key[0], key[1], radius)
        self.place()

    def place(self, *args):
        for cap in self.caps.values():
            cap.place()

    def refresh(self):
        for cap in self.caps.values():
            cap.invalidate()

    def remove(self):
        disconnect(self.view.verticalScrollBar().valueChanged, self.place)
        disconnect(self.view.horizontalScrollBar().valueChanged, self.place)
        for cap in self.caps.values():
            cap.deleteLater()
        self.caps = {}


def isPopup(widget: QWidget) -> bool:
    return isinstance(widget, QMenu) or isDropdownList(widget)


def setPopupTranslucent(widget: QWidget, isTranslucent: bool):
    if bool(widget.property("modernThemesPopup")) == isTranslucent or widget.isVisible():
        return
    # The attribute only reaches a window created after it is set. Changing the window flags
    # recreates a window that already exists, so menus MO2 built before this plugin loaded convert too.
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, isTranslucent)
    widget.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, isTranslucent)
    widget.setWindowFlag(Qt.WindowType.FramelessWindowHint, isTranslucent)
    widget.setProperty("modernThemesPopup", isTranslucent)


def isDropdownList(widget: QWidget) -> bool:
    return widget.metaObject().className() == DROPDOWN_CLASS


def alignDropdownList(container: QWidget, gap: int):
    """Puts a dropdown's list the gap under the dropdown, at least as wide as the dropdown and with its
    left edge on the dropdown's."""
    combo = container.parentWidget()
    if not isinstance(combo, QComboBox):
        return
    view = combo.view()
    # Whatever the window has around the list, such as room for a shadow, stays around it.
    offset = view.mapTo(container, QPoint(0, 0))
    extra = container.width() - view.width()
    # The dropdown as drawn, inside the stylesheet's margins. Qt puts the list on the widget's last row of
    # pixels, so the gap is measured from the drawn frame instead.
    option = QStyleOptionComboBox()
    option.initFrom(combo)
    option.rect = combo.rect()
    frame = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxFrame, combo)
    if not frame.isValid():
        frame = combo.rect()
    frame.translate(combo.mapToGlobal(QPoint(0, 0)))
    width = max(view.width(), frame.width())
    # Below the dropdown, or above it near the bottom of the screen.
    if container.y() >= frame.center().y():
        top = frame.y() + frame.height() + gap - offset.y()
    else:
        top = frame.y() - gap - offset.y() - view.height()
    geometry = QRect(frame.x() - offset.x(), top, width + extra, container.height())
    if container.geometry() != geometry:
        container.setGeometry(geometry)


def hasTitleBar(widget: QWidget) -> bool:
    return (
        sys.platform == "win32"
        and widget.isWindow()
        and widget.windowType() in (Qt.WindowType.Window, Qt.WindowType.Dialog)
        and not widget.windowFlags() & Qt.WindowType.FramelessWindowHint
        and widget.testAttribute(Qt.WidgetAttribute.WA_WState_Created)
    )


def setDwmAttribute(hwnd: int, attribute: int, value: int):
    value = wintypes.DWORD(value)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), attribute, ctypes.byref(value), 4)


def getDwmAttribute(hwnd: int, attribute: int):
    value = wintypes.DWORD()
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), attribute, ctypes.byref(value), 4)
    return value.value if result == 0 else None


def setTitleBarColors(widget: QWidget, titleBar):
    """Colors the window's title bar as the TitleBar says, or restores it when titleBar is None."""
    isColored = bool(widget.property("modernThemesTitleBar"))
    if titleBar is None and not isColored:
        return
    hwnd = int(widget.winId())
    if titleBar is None:
        for attribute in (DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR, DWMWA_BORDER_COLOR):
            setDwmAttribute(hwnd, attribute, DWMWA_COLOR_DEFAULT)
        darkMode = widget.property("modernThemesDarkMode")
        if darkMode is not None:
            setDwmAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, darkMode)
        widget.setProperty("modernThemesTitleBar", False)
        return
    if not isColored:
        # Qt may have set dark mode itself, so remember what to restore.
        widget.setProperty("modernThemesDarkMode", getDwmAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE))
    setDwmAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, int(titleBar.isDark))
    for key, attribute in (("caption", DWMWA_CAPTION_COLOR), ("text", DWMWA_TEXT_COLOR), ("border", DWMWA_BORDER_COLOR)):
        setDwmAttribute(hwnd, attribute, titleBar.colors.get(key, DWMWA_COLOR_DEFAULT))
    widget.setProperty("modernThemesTitleBar", True)


class StyleWatcher(QObject):
    """Watches the main window alone, for a change of stylesheet, whichever style is selected."""

    def __init__(self, plugin: "ModernThemes"):
        super().__init__()
        self._plugin = plugin

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.StyleChange:
            QTimer.singleShot(0, self._plugin.refresh)
        return False


class ThemeEventFilter(QObject):
    """Every event of the application, installed only while a Modern Theme is selected."""

    def __init__(self, plugin: "ModernThemes"):
        super().__init__()
        self._plugin = plugin

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # An exception here would reach Qt's event loop; one event going unhandled is the lesser harm.
        try:
            return self._handle(watched, event)
        except Exception:
            log.exception("Modern Themes: handling %s failed", event.type())
            return False

    def _handle(self, watched: QObject, event: QEvent) -> bool:
        plugin = self._plugin
        eventType = event.type()
        if not isinstance(watched, QWidget):
            return False
        if eventType == QEvent.Type.Wheel and plugin.smoothScrollers:
            # The wheel reaches a list's viewport, a child of the list, or the list's overlay scroll bar,
            # a window of its own.
            area = plugin.overlayAreas.get(id(watched))
            scroller = plugin.smoothScrollers.get(id(area if area is not None else watched.parentWidget()))
            if scroller is not None and scroller.wheel(event):
                return True
        if eventType in EDGE_SCROLL_EVENTS and plugin.smoothScrollers:
            scroller = plugin.smoothScrollers.get(id(watched.parentWidget()))
            if scroller is not None and watched is scroller.view.viewport():
                scroller.viewportEvent(event)
        if eventType == QEvent.Type.MouseButtonPress and isinstance(watched, (QPushButton, QToolButton)):
            # A button opens its menu on a press, the menu's show event knows the button by this.
            plugin.menuButton = watched
        if eventType == QEvent.Type.Polish and isPopup(watched):
            setPopupTranslucent(watched, True)
        if eventType == QEvent.Type.Show and isinstance(watched, QMenu):
            plugin.spaceMenu(watched)
            plugin.themeMenu(watched)
        if eventType == QEvent.Type.Show and isDropdownList(watched):
            alignDropdownList(watched, plugin.markers.popupGap)
        if eventType in (QEvent.Type.Show, QEvent.Type.WinIdChange) and hasTitleBar(watched):
            # A new window gets its colors before it shows, and again if Qt recreates it.
            setTitleBarColors(watched, plugin.markers.titleBar)
        if eventType == QEvent.Type.Show:
            if watched.objectName() in LAYOUTS:
                plugin.applyLayout(watched)
            if hiddenWidgetKey(watched) is not None:
                # Hiding a widget while its show event is delivered confuses the layout, so wait.
                QTimer.singleShot(0, plugin.applyHiddenWidgets)
            if plugin.scrollBarsEnabled and isinstance(watched, QAbstractScrollArea):
                plugin.attachScrollBars(watched)
            if plugin.smoothScrollingEnabled and isinstance(watched, QAbstractItemView):
                plugin.attachSmoothScrolling(watched)
            if plugin.markers.listCornerRadius and isinstance(watched, CORNERED_LISTS):
                plugin.applyListCorners(watched)
        if eventType == QEvent.Type.StyleChange:
            # A list restyled, such as by MO2's filter border, loses the opaque content area its smooth
            # scrolling needs, and would paint all of itself again for every step; it gets it back.
            scroller = plugin.smoothScrollers.get(id(watched)) or plugin.smoothScrollers.get(id(watched.parentWidget()))
            if scroller is not None:
                QTimer.singleShot(0, scroller.makeOpaque)
            if plugin.markers.filterColor is not None and watched.objectName() in FILTER_WIDGETS:
                # MO2 set its own stylesheet on it, the recolored one goes on once it has applied.
                QTimer.singleShot(0, lambda widget=watched: plugin.recolorFilter(widget))
            corners = plugin.listCorners.get(id(watched))
            if corners is not None:
                # A new look for the list's frame, such as a filter's border: the caps show it once it applies.
                QTimer.singleShot(0, corners.refresh)
        if eventType in (QEvent.Type.Resize, QEvent.Type.Move) and plugin.markers.listCornerRadius:
            # A list's content area changed size or place: its corners follow.
            view = watched.parentWidget()
            if isinstance(view, CORNERED_LISTS) and watched is view.viewport():
                plugin.applyListCorners(view)
        if eventType == QEvent.Type.Paint and plugin.smoothScrollers:
            scroller = plugin.smoothScrollers.get(id(watched.parentWidget()))
            if scroller is not None and watched is scroller.view.viewport():
                scroller.painted()
        if eventType == QEvent.Type.Paint and watched is plugin.mainWindow and not plugin.hasPainted:
            # MO2's first paint resets the lists' resize modes, put the fitted ones back after it.
            plugin.hasPainted = True
            QTimer.singleShot(0, plugin.fitColumns)
        if eventType == QEvent.Type.Resize and watched in plugin.fittedViewports:
            # Right away, while the viewport resizes: later, the list would paint once at its old widths
            # first, and every step of a window resize would jump.
            plugin.fitColumns()
        if eventType == QEvent.Type.Paint and plugin.icons and watched in plugin.iconViewports:
            # The cache may have dropped a render, put it back before MO2 looks for it.
            plugin.ensureIcons()
        if eventType in (QEvent.Type.StyleChange, QEvent.Type.Paint) and isinstance(watched, QLabel):
            if watched.autoFillBackground() and watched.objectName() in FILLED_LABELS:
                # MO2 turns the fill on right after it restyles the label, so wait for it.
                QTimer.singleShot(0, plugin.applyLabelFills)
        return False


class ModernThemes(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self._organizer = None
        self.mainWindow = None
        self.isActive = False
        self.markers = Markers("", "")
        self.icons = {}
        self.iconViewports = []
        self._iconRatio = 0.0
        self._decorationResources = {}
        self._decorationPixmaps = {}
        self.scrollBarsEnabled = False
        self._scrollOverlays = {}
        # Each overlay scroll bar's window, by id, to the scroll area it stands in for.
        self.overlayAreas = {}
        self._scrollTimer = None
        self.smoothScrollingEnabled = False
        self.smoothScrollers = {}
        self.scrollRows = SCROLL_SPEED_SETTING[2]
        self._frameClock = None
        self._iconCheck = QElapsedTimer()
        self._columnFitters = []
        self.fittedViewports = []
        self.hasPainted = False
        self._uniformRowHeights = True
        self._stickySeparator = None
        self.menuButton = None
        self.listCorners = {}
        self._themeIcons = {}
        self._pixmapKeys = {}
        self._themedActions = []
        self._eventFilter = None
        self._isEventFilterInstalled = False
        self._watcher = None
        self._fusion = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        organizer.onUserInterfaceInitialized(self._onUserInterfaceInitialized)
        organizer.onPluginSettingChanged(self._onPluginSettingChanged)
        return True

    def name(self) -> str:
        return "Modern Themes"

    def localizedName(self) -> str:
        return "Modern Themes"

    def author(self) -> str:
        return "hakasapl"

    def description(self) -> str:
        return (
            "Extends Qt stylesheets that ask for it: smooth scrolling, overlay scroll bars, list columns that fit "
            "the window, pinned and rounded separators, themed window title bars and filter borders, sharp SVG "
            "icons in place of MO2's, and see-through windows for rounded menus and dropdowns."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 29, 0)

    def settings(self) -> list:
        toggles = [*HIDDEN_WIDGETS.values(), SCROLL_BAR_SETTING, SMOOTH_SCROLL_SETTING, STICKY_SEPARATOR_SETTING]
        settings = [mobase.PluginSetting(key, description, True) for key, description in toggles]
        return [*settings, mobase.PluginSetting(*SCROLL_SPEED_SETTING)]

    def _onUserInterfaceInitialized(self, mainWindow: QMainWindow):
        self.mainWindow = mainWindow
        self._eventFilter = ThemeEventFilter(self)
        self._watcher = StyleWatcher(self)
        mainWindow.installEventFilter(self._watcher)
        self._scrollTimer = QTimer(mainWindow)
        self._scrollTimer.setInterval(SCROLL_BAR_POLL)
        self._scrollTimer.timeout.connect(self._pollScrollBars)
        QApplication.instance().applicationStateChanged.connect(self._onApplicationStateChanged)
        self.refresh()

    def _onApplicationStateChanged(self, state):
        # The overlay scroll bars follow the mouse only while MO2 is the active application.
        if state == Qt.ApplicationState.ApplicationActive:
            if self.scrollBarsEnabled:
                self._scrollTimer.start()
        else:
            self._scrollTimer.stop()
            for overlay in self._scrollOverlays.values():
                overlay.follow(None)

    @property
    def frameClock(self) -> FrameClock:
        # Its thread starts with the first glide.
        if self._frameClock is None:
            self._frameClock = FrameClock()
        return self._frameClock

    def _onPluginSettingChanged(self, pluginName: str, key: str, oldValue, newValue):
        if pluginName == self.name() and self.mainWindow is not None:
            self.applyHiddenWidgets()
            self.applyScrollBars()
            self.applySmoothScrolling()
            self.applyStickySeparator()

    def _setting(self, key: str):
        return self._organizer.pluginSetting(self.name(), key)

    def _isHideEnabled(self, key: str) -> bool:
        return bool(self._setting(HIDDEN_WIDGETS[key][0]))

    def refresh(self):
        styleSheet, folder = readStyleSheet()
        wasActive = self.isActive
        self.markers = Markers(styleSheet, folder)
        self.isActive = self.markers.isActive
        # Every event goes through the plugin only while a stylesheet asks for it.
        if self.isActive != self._isEventFilterInstalled:
            if self.isActive:
                QApplication.instance().installEventFilter(self._eventFilter)
            else:
                QApplication.instance().removeEventFilter(self._eventFilter)
            self._isEventFilterInstalled = self.isActive
        if not self.isActive and not wasActive:
            # Another style, and nothing of this plugin's to undo.
            return
        # Each part on its own: one that fails leaves the others applied, or undone.
        for step in (
            self._applyListStyles,
            self.applyHiddenWidgets,
            self.applyScrollBars,
            self.applySmoothScrolling,
            self._applyColumnFits,
            self.applyLabelFills,
            self.applyFilterToggle,
            self._applyFilterBorders,
            self._applySeparators,
            self._applyRowFills,
            self._applyLayouts,
            self._applyAllListCorners,
            self.applyStickySeparator,
            self._applyIcons,
            self._applyPopups,
            self._applyTitleBars,
        ):
            try:
                step()
            except Exception:
                log.exception("Modern Themes: %s failed", step.__name__)

    def _applyFilterBorders(self):
        for name in FILTER_WIDGETS:
            widget = self.mainWindow.findChild(QWidget, name)
            if widget is not None:
                self.recolorFilter(widget)

    def _applyAllListCorners(self):
        for widget in QApplication.allWidgets():
            if isinstance(widget, CORNERED_LISTS):
                self.applyListCorners(widget)
        if not self.markers.listCornerRadius:
            for corners in self.listCorners.values():
                corners.remove()
            self.listCorners = {}

    def _applyPopups(self):
        for widget in QApplication.allWidgets():
            if isPopup(widget):
                setPopupTranslucent(widget, self.isActive)

    def _applyTitleBars(self):
        for widget in QApplication.topLevelWidgets():
            if hasTitleBar(widget):
                setTitleBarColors(widget, self.markers.titleBar)

    def _applyListStyles(self):
        for name in CHECKABLE_LISTS:
            view = self.mainWindow.findChild(QAbstractItemView, name)
            if view is None:
                continue
            # The view reports a stylesheet wrapper as its style, so remember the change on the view.
            isFusion = bool(view.property("modernThemesFusion"))
            if self.isActive and not isFusion:
                if self._fusion is None:
                    self._fusion = QStyleFactory.create("Fusion")
                    self._fusion.setParent(self.mainWindow)
                view.setStyle(self._fusion)
                view.setProperty("modernThemesFusion", True)
            elif not self.isActive and isFusion:
                view.setStyle(None)
                view.setProperty("modernThemesFusion", False)

    def _applyIcons(self):
        iconFiles = readIconFiles(self.markers.iconFolder) if self.isActive else {}
        # Drop the previous theme's renders, MO2 loads its own icons again where no theme replaces them.
        for resource in self.icons:
            for size in ICON_SIZES:
                QPixmapCache.remove(f"{resource}_{size}")
        for key in self._pixmapKeys:
            QPixmapCache.remove(key)
        self.icons = {resource: QSvgRenderer(path) for resource, path in iconFiles.items()}
        self._themeIcons = {}
        # The images MO2 loads as pixmaps, at the size of MO2's own.
        self._pixmapKeys = {}
        for resource in self.icons:
            original = QImage(resource)
            if not original.isNull():
                self._pixmapKeys[pixmapCacheKey(resource)] = (resource, original.width())
        self._restoreMenuIcons()
        self.ensureIcons(replace=True)
        self._applyDecorations()
        self.iconViewports = []
        for name in ICON_LISTS:
            view = self.mainWindow.findChild(QAbstractItemView, name)
            if view is not None:
                self.iconViewports.append(view.viewport())
                view.viewport().update()

    def _applyDecorations(self):
        # A model icon is recognized by its image, every cell gets its own QIcon of the resource.
        self._decorationResources = {}
        for resource in self.icons:
            icon = QIcon(resource)
            if not icon.isNull():
                self._decorationResources[iconFingerprint(icon)] = resource
        self._decorationPixmaps = {}
        for name, column in DECORATION_COLUMNS:
            view = self.mainWindow.findChild(QAbstractItemView, name)
            if view is None:
                continue
            current = view.itemDelegateForColumn(column)
            isWrapped = isinstance(current, DecorationDelegate)
            if self.icons and not isWrapped:
                view.setItemDelegateForColumn(column, DecorationDelegate(view, current, self))
            elif not self.icons and isWrapped:
                view.setItemDelegateForColumn(column, current.columnDelegate)
                current.deleteLater()

    def decorationResource(self, icon: QIcon):
        return self._decorationResources.get(iconFingerprint(icon))

    def themeIcon(self, resource: str) -> QIcon:
        """The theme's icon for one of MO2's resources, rendered sharp for the window's pixel ratio."""
        ratio = self.mainWindow.devicePixelRatioF()
        key = (resource, ratio)
        if key not in self._themeIcons:
            icon = QIcon()
            for size in THEME_ICON_SIZES:
                icon.addPixmap(renderIcon(self.icons[resource], size, ratio))
            self._themeIcons[key] = icon
        return self._themeIcons[key]

    def themeMenu(self, menu: QMenu):
        """Gives the items MO2 added to a menu in code, with one of its icons, the theme's icon."""
        if not self._decorationResources:
            return
        for action in menu.actions():
            icon = action.icon()
            if icon.isNull() or action.property("modernThemesIcon"):
                continue
            resource = self.decorationResource(icon)
            if resource is None:
                continue
            action.setProperty("modernThemesOriginalIcon", icon)
            action.setProperty("modernThemesIcon", True)
            action.setIcon(self.themeIcon(resource))
            self._themedActions.append(action)

    def _restoreMenuIcons(self):
        for action in self._themedActions:
            try:
                action.setIcon(action.property("modernThemesOriginalIcon"))
                action.setProperty("modernThemesIcon", False)
            except RuntimeError:
                # The action is gone.
                pass
        self._themedActions = []

    def decorationPixmap(self, resource: str, size: int) -> QPixmap:
        ratio = self.mainWindow.devicePixelRatioF()
        key = (resource, size, ratio)
        if key not in self._decorationPixmaps:
            self._decorationPixmaps[key] = renderIcon(self.icons[resource], size, ratio)
        return self._decorationPixmaps[key]

    def ensureIcons(self, replace: bool = False):
        # MO2 draws a cached icon into a square of that many logical pixels, so a render at the window's
        # pixel ratio lands 1:1 on the screen; a 1x render gets stretched without smoothing. Moving to a
        # screen with other scaling renders them again.
        ratio = self.mainWindow.devicePixelRatioF()
        if ratio != self._iconRatio:
            self._iconRatio = ratio
            replace = True
        # The lists repaint every frame while they glide, a check on every paint would slow them.
        if not replace and self._iconCheck.isValid() and self._iconCheck.elapsed() < ICON_CHECK_INTERVAL:
            return
        self._iconCheck.start()
        for resource, renderer in self.icons.items():
            for size in ICON_SIZES:
                key = f"{resource}_{size}"
                if replace or QPixmapCache.find(key) is None:
                    QPixmapCache.insert(key, renderIcon(renderer, size, ratio))
        for key, (resource, size) in self._pixmapKeys.items():
            # MO2 paints these into images of its own pixel size, a render at the screen's ratio would
            # come out that much larger.
            if replace or QPixmapCache.find(key) is None:
                QPixmapCache.insert(key, renderIcon(self.icons[resource], size, 1))

    def spaceMenu(self, menu: QMenu):
        """Moves a menu a button opened the stylesheet's popup gap away from the button."""
        gap = self.markers.popupGap
        button = self.menuButton
        if not gap:
            return
        try:
            if button is None or not button.isVisible():
                return
            menus = [button.menu()]
            if isinstance(button, QToolButton) and button.defaultAction() is not None:
                menus.append(button.defaultAction().menu())
            if not any(candidate is menu for candidate in menus):
                return
            top = button.mapToGlobal(QPoint(0, 0)).y()
            bottom = top + button.height()
        except RuntimeError:
            # The button is gone.
            self.menuButton = None
            return
        # Qt opens the menu on the button's last row of pixels, the gap is measured from below it.
        if menu.y() >= bottom - 1:
            menu.move(menu.x(), bottom + gap)
        elif menu.y() + menu.height() <= top + 1:
            # Opened above the button, near the bottom of the screen.
            menu.move(menu.x(), top - gap - menu.height())

    def applyListCorners(self, view: QAbstractItemView):
        key = id(view)
        corners = self.listCorners.get(key)
        radius = self.markers.listCornerRadius
        if radius:
            if corners is None:
                corners = self.listCorners[key] = ListCorners(view)
                view.destroyed.connect(lambda *args, key=key: self.listCorners.pop(key, None))
            corners.apply(radius)
        elif corners is not None:
            corners.remove()
            del self.listCorners[key]

    def _applyLayouts(self):
        # Dialogs are windows of their own, so every window is searched.
        for window in QApplication.topLevelWidgets():
            for widget in [window, *window.findChildren(QWidget)]:
                if widget.objectName() in LAYOUTS:
                    self.applyLayout(widget)

    def applyLayout(self, widget: QWidget):
        layout = widget.layout()
        tweak = LAYOUTS.get(widget.objectName())
        if layout is None or tweak is None:
            return
        original = widget.property("modernThemesLayout")
        if self.isActive:
            if original is None:
                margins = layout.contentsMargins()
                original = [margins.left(), margins.top(), margins.right(), margins.bottom(), layout.spacing()]
                widget.setProperty("modernThemesLayout", original)
            wanted = tweak.get("margins", (None,) * 4)
            layout.setContentsMargins(*[old if new is None else new for old, new in zip(original[:4], wanted)])
            layout.setSpacing(tweak.get("spacing", original[4]))
        elif original is not None:
            layout.setContentsMargins(*original[:4])
            layout.setSpacing(original[4])
            widget.setProperty("modernThemesLayout", None)

    def _applyRowFills(self):
        for name in ROW_FILL_LISTS:
            view = self.mainWindow.findChild(QAbstractItemView, name)
            if view is None:
                continue
            current = view.itemDelegate()
            isWrapped = isinstance(current, RowFillDelegate)
            # The separator delegate fills the mod list's rows when there is one.
            wanted = self.isActive and not isinstance(current, SeparatorDelegate)
            if wanted and not isWrapped:
                view.setItemDelegate(RowFillDelegate(view, current))
            elif not wanted and isWrapped:
                view.setItemDelegate(current._original)
                current.deleteLater()
            view.viewport().update()

    def _applySeparators(self):
        view = self.mainWindow.findChild(QAbstractItemView, "modList")
        if view is None:
            return
        current = view.itemDelegate()
        if isinstance(current, RowFillDelegate):
            # The separator delegate fills the rows itself; the row fill goes back on after if it is wanted.
            view.setItemDelegate(current._original)
            current.deleteLater()
            current = view.itemDelegate()
        isWrapped = isinstance(current, SeparatorDelegate)
        separators = self.markers.separators if self.isActive else None
        if isWrapped and (separators is None or (current.radius, *current.margin) != separators):
            view.setItemDelegate(current._original)
            view.setUniformRowHeights(self._uniformRowHeights)
            current.deleteLater()
            isWrapped = False
        if separators is not None and not isWrapped:
            # MO2 gives every row the first one's height, separators are taller.
            self._uniformRowHeights = view.uniformRowHeights()
            view.setUniformRowHeights(False)
            view.setItemDelegate(SeparatorDelegate(view, *separators))
        view.viewport().update()

    def applyStickySeparator(self):
        view = self.mainWindow.findChild(QAbstractItemView, "modList")
        enabled = self.isActive and bool(self._setting(STICKY_SEPARATOR_SETTING[0]))
        if enabled and self._stickySeparator is None and view is not None:
            self._stickySeparator = StickySeparator(view)
            self._stickySeparator.place()
        elif not enabled and self._stickySeparator is not None:
            self._stickySeparator.remove()
            self._stickySeparator = None

    def recolorFilter(self, widget: QWidget):
        """Swaps the red of MO2's filter border on the widget for the stylesheet's color and width, or
        puts MO2's back."""
        sheet = widget.styleSheet()
        original = widget.property("modernThemesFilterSheet") or ""
        if sheet and sheet == widget.property("modernThemesRecoloredSheet"):
            # Still the recolored border of an earlier stylesheet, made from MO2's.
            sheet = original
        elif not MO2_FILTER_RED.search(sheet):
            # MO2 took its border off, or never set one.
            widget.setProperty("modernThemesFilterSheet", "")
            widget.setProperty("modernThemesRecoloredSheet", "")
            return
        markers = self.markers
        if markers.filterColor is None:
            if widget.styleSheet() != sheet:
                widget.setStyleSheet(sheet)
            widget.setProperty("modernThemesFilterSheet", "")
            widget.setProperty("modernThemesRecoloredSheet", "")
            return
        recolored = MO2_FILTER_RED.sub(markers.filterColor, sheet).replace("ridge", "solid")
        if markers.filterWidth is not None:
            recolored = MO2_BORDER_WIDTH.sub(rf"\g<1>{markers.filterWidth}px", recolored)
        widget.setProperty("modernThemesFilterSheet", sheet)
        widget.setProperty("modernThemesRecoloredSheet", recolored)
        if widget.styleSheet() != recolored:
            widget.setStyleSheet(recolored)

    def applyFilterToggle(self, *args):
        """Shows the stylesheet's icons on the filter panel's toggle in place of MO2's text arrows."""
        button = self.mainWindow.findChild(QPushButton, FILTER_TOGGLE)
        if button is None:
            return
        icons = self.markers.filterToggle if self.isActive else None
        if icons is not None and not button.property("modernThemesToggleHooked"):
            # Connected after MO2's own handler, so this runs once MO2 has set its text.
            button.toggled.connect(self.applyFilterToggle)
            button.setProperty("modernThemesToggleHooked", True)
        isOpen = button.isChecked()
        if icons is not None:
            ratio = self.mainWindow.devicePixelRatioF()
            icon = QIcon(renderIcon(QSvgRenderer(icons[isOpen]), FILTER_TOGGLE_ICON_SIZE, ratio))
            button.setText("")
            button.setIcon(icon)
            button.setIconSize(QSize(FILTER_TOGGLE_ICON_SIZE, FILTER_TOGGLE_ICON_SIZE))
        elif button.property("modernThemesToggleHooked"):
            disconnect(button.toggled, self.applyFilterToggle)
            button.setProperty("modernThemesToggleHooked", False)
            button.setIcon(QIcon())
            button.setText(FILTER_TOGGLE_TEXT[isOpen])

    def applyLabelFills(self):
        for name in FILLED_LABELS:
            label = self.mainWindow.findChild(QLabel, name)
            if label is None:
                continue
            if self.isActive and label.autoFillBackground():
                label.setAutoFillBackground(False)
                label.setProperty("modernThemesNoFill", True)
                label.update()
            elif not self.isActive and label.property("modernThemesNoFill"):
                label.setAutoFillBackground(True)
                label.setProperty("modernThemesNoFill", False)

    def applyScrollBars(self):
        self.scrollBarsEnabled = self.markers.overlayScrollBars and bool(self._setting(SCROLL_BAR_SETTING[0]))
        if self.scrollBarsEnabled:
            for widget in QApplication.allWidgets():
                if isinstance(widget, QAbstractScrollArea):
                    self.attachScrollBars(widget)
            self._scrollTimer.start()
        else:
            self._scrollTimer.stop()
            for overlay in self._scrollOverlays.values():
                overlay.remove()
            self._scrollOverlays = {}
            self.overlayAreas = {}

    def applySmoothScrolling(self):
        self.smoothScrollingEnabled = self.isActive and bool(self._setting(SMOOTH_SCROLL_SETTING[0]))
        try:
            self.scrollRows = max(float(self._setting(SCROLL_SPEED_SETTING[0])), 0.1)
        except (TypeError, ValueError):
            self.scrollRows = SCROLL_SPEED_SETTING[2]
        if self.smoothScrollingEnabled:
            for widget in QApplication.allWidgets():
                if isinstance(widget, QAbstractItemView):
                    self.attachSmoothScrolling(widget)
            for scroller in self.smoothScrollers.values():
                scroller.makeOpaque()
        else:
            for scroller in self.smoothScrollers.values():
                scroller.remove()
            self.smoothScrollers = {}

    def attachSmoothScrolling(self, view: QAbstractItemView):
        key = id(view)
        if key in self.smoothScrollers:
            return
        self.smoothScrollers[key] = SmoothScroller(view, self)
        view.destroyed.connect(lambda *args, key=key: self.smoothScrollers.pop(key, None))

    def _applyColumnFits(self):
        if self.isActive and not self._columnFitters:
            for name in FITTED_LISTS:
                view = self.mainWindow.findChild(QAbstractItemView, name)
                if view is not None:
                    self._columnFitters.append(ColumnFitter(view))
        elif not self.isActive:
            for fitter in self._columnFitters:
                fitter.remove()
            self._columnFitters = []
        self.fittedViewports = [fitter.view.viewport() for fitter in self._columnFitters]

    def fitColumns(self):
        for fitter in self._columnFitters:
            fitter.fit()

    def attachScrollBars(self, area: QAbstractScrollArea):
        key = id(area)
        if key in self._scrollOverlays:
            return
        overlay = ScrollBarOverlay(area)
        self._scrollOverlays[key] = overlay
        overlayKey = id(overlay.bar) if overlay.bar is not None else None
        if overlayKey is not None:
            self.overlayAreas[overlayKey] = area

        def forget(*args):
            # The bar is a window of the area's window, which may outlive the area.
            gone = self._scrollOverlays.pop(key, None)
            self.overlayAreas.pop(overlayKey, None)
            if gone is not None and gone.bar is not None:
                gone.bar.deleteLater()

        area.destroyed.connect(forget)

    def _pollScrollBars(self):
        cursor = QCursor.pos()
        # The innermost scroll area under the cursor; its overlay bar is a window of its own.
        hovered = None
        widget = QApplication.widgetAt(cursor)
        area = self.overlayAreas.get(id(widget)) if widget is not None else None
        if area is not None:
            widget = area
        while widget is not None and hovered is None:
            hovered = self._scrollOverlays.get(id(widget))
            widget = widget.parentWidget()
        for overlay in list(self._scrollOverlays.values()):
            if overlay is hovered:
                overlay.follow(cursor)
            elif overlay.isShowing:
                overlay.follow(None)

    def applyHiddenWidgets(self):
        for key in HIDDEN_WIDGETS:
            # Dialogs are windows of their own, so every window is searched.
            name = key.rpartition("/")[2]
            widgets = [
                widget
                for window in QApplication.topLevelWidgets()
                for widget in [window, *window.findChildren(QWidget, name)]
                if widget.objectName() == name and hiddenWidgetKey(widget) == key
            ]
            shouldHide = self.isActive and self._isHideEnabled(key)
            for widget in widgets:
                self._applyHidden(widget, shouldHide)

    def _applyHidden(self, widget: QWidget, shouldHide: bool):
        if shouldHide and widget.isVisibleTo(widget.parentWidget()):
            widget.setVisible(False)
            widget.setProperty("modernThemesHidden", True)
        elif not shouldHide and widget.property("modernThemesHidden"):
            # Only widgets this plugin hid come back, MO2 may hide them for its own reasons.
            widget.setVisible(True)
            widget.setProperty("modernThemesHidden", False)


def createPlugin() -> mobase.IPlugin:
    return ModernThemes()
