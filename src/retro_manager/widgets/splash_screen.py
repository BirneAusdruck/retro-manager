"""Startbild, das beim Programmstart angezeigt wird."""

from PySide6.QtWidgets import QSplashScreen

from retro_manager.widgets import images

SPLASH_HEIGHT = 420


class SplashScreen(QSplashScreen):
    """Zeigt das Startbild, bis der Startablauf das nächste Fenster öffnet."""

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("splashScreen")
        self.setPixmap(images.svg_pixmap(images.SPLASH, SPLASH_HEIGHT))
