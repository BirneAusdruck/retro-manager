"""Lädt SVG-Grafiken aus dem Ressourcen-Paket als Pixmaps und Icons."""

from importlib import resources

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON = "icon.svg"
LOGO = "logo.svg"
SPLASH = "splash.svg"

_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def _renderer(name: str) -> QSvgRenderer:
    data = resources.files("retro_manager.resources").joinpath("icons", name).read_bytes()
    return QSvgRenderer(QByteArray(data))


def svg_pixmap(name: str, height: int, device_pixel_ratio: float | None = None) -> QPixmap:
    """Rendert eine SVG-Datei scharf in der gewünschten logischen Höhe (Seitenverhältnis bleibt)."""
    if device_pixel_ratio is None:
        device_pixel_ratio = QGuiApplication.primaryScreen().devicePixelRatio()
    renderer = _renderer(name)
    default = renderer.defaultSize()
    width = round(height * default.width() / default.height())

    pixmap = QPixmap(QSize(width, height) * device_pixel_ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    return pixmap


def app_icon() -> QIcon:
    """Programm-Icon in allen gängigen Größen."""
    icon = QIcon()
    for size in _ICON_SIZES:
        icon.addPixmap(svg_pixmap(ICON, size, device_pixel_ratio=1.0))
    return icon
