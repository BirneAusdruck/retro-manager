"""Aktivitätsanzeige: Feld im Banner mit dem ersten Vorgang, beim Überfahren ausrollende Liste."""

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.activity_controller import Activity, ActivityController

INDICATOR_WIDTH = 380
_SPINNER = "◐◓◑◒"
_SPIN_INTERVAL_MS = 150
_ROLL_DURATION_MS = 180
_CLOSE_DELAY_MS = 300


def _progress_bar(object_name: str) -> QProgressBar:
    bar = QProgressBar()
    bar.setObjectName(object_name)
    bar.setTextVisible(False)
    bar.setRange(0, 1000)
    return bar


def _set_progress(bar: QProgressBar, progress: float | None) -> None:
    if progress is None:
        bar.setRange(0, 0)  # unbestimmt: laufender Balken
    else:
        bar.setRange(0, 1000)
        bar.setValue(int(progress * 1000))


class ActivityIndicator(QFrame):
    """Kompaktes Feld: Drehsymbol, Titel des ersten Vorgangs, Fortschritt, Anzahl weiterer."""

    hovered = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spin_index = 0
        self._build_ui()
        self._connect_signals()
        self.hide()

    def _build_ui(self) -> None:
        self.setObjectName("activityIndicator")
        self.setFixedWidth(INDICATOR_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._spinner = QLabel(_SPINNER[0])
        self._spinner.setObjectName("activitySpinner")
        self._title = QLabel()
        self._title.setObjectName("activityTitle")
        self._detail = QLabel()
        self._detail.setObjectName("activityDetail")
        self._bar = _progress_bar("activityBar")
        self._more = QLabel()
        self._more.setObjectName("activityMore")

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self._title)
        text.addWidget(self._detail)
        text.addWidget(self._bar)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.addWidget(self._spinner)
        layout.addLayout(text, stretch=1)
        layout.addWidget(self._more)

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(_SPIN_INTERVAL_MS)

    def _connect_signals(self) -> None:
        self._spin_timer.timeout.connect(self._spin)

    def show_activities(self, activities: list[Activity]) -> None:
        if not activities:
            self._spin_timer.stop()
            self.hide()
            return
        first = activities[0]
        width = INDICATOR_WIDTH - 90
        metrics = self._title.fontMetrics()
        self._title.setText(metrics.elidedText(first.label, Qt.TextElideMode.ElideRight, width))
        detail = first.detail if first.running else self.tr("wartet")
        self._detail.setText(
            self._detail.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideRight, width)
        )
        _set_progress(self._bar, first.progress)
        others = len(activities) - 1
        self._more.setText(f"+{others}" if others else "")
        self._more.setToolTip(self.tr("{0} weitere Vorgänge").format(others) if others else "")
        if not self._spin_timer.isActive():
            self._spin_timer.start()
        self.show()

    def _spin(self) -> None:
        self._spin_index = (self._spin_index + 1) % len(_SPINNER)
        self._spinner.setText(_SPINNER[self._spin_index])

    def enterEvent(self, event: QEnterEvent) -> None:
        self.hovered.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.hovered.emit(False)
        super().leaveEvent(event)


class _ActivityRow(QFrame):
    """Eine Zeile der Liste; Klick meldet den zuständigen Reiter."""

    clicked = Signal(str)

    def __init__(self, activity: Activity, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tab = activity.tab
        self.setObjectName("activityRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title = QLabel()
        self._title.setObjectName("activityRowTitle")
        self._title.setWordWrap(True)
        self._state = QLabel()
        self._state.setObjectName("activityRowState")
        self._detail = QLabel()
        self._detail.setObjectName("activityRowDetail")
        self._detail.setWordWrap(True)
        self._bar = _progress_bar("activityRowBar")
        header = QHBoxLayout()
        header.addWidget(self._title, stretch=1)
        header.addWidget(self._state)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)
        layout.addLayout(header)
        layout.addWidget(self._detail)
        layout.addWidget(self._bar)
        self.update_activity(activity)

    def update_activity(self, activity: Activity) -> None:
        self._tab = activity.tab
        self._title.setText(activity.label)
        self._state.setText(self.tr("läuft") if activity.running else self.tr("wartet"))
        self._detail.setText(activity.detail)
        self._detail.setVisible(activity.running and bool(activity.detail))
        self._bar.setVisible(activity.running)
        _set_progress(self._bar, activity.progress)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._tab)
        super().mouseReleaseEvent(event)


class ActivityPanel(QFrame):
    """Schwebende Liste aller Vorgänge unter dem Feld; rollt per Animation aus und ein."""

    hovered = Signal(bool)
    activity_clicked = Signal(str)  # Reiter

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        self.setObjectName("activityPanel")
        self._keys: list[str] = []
        self._row_widgets: list[_ActivityRow] = []
        self._content = QWidget()
        self._content.setObjectName("activityContent")
        self._rows = QVBoxLayout(self._content)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(1)
        self._rows.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("activityScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.setDuration(_ROLL_DURATION_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_activities(self, activities: list[Activity]) -> None:
        keys = [activity.key for activity in activities]
        if keys == self._keys:
            # Nur Fortschritt/Text geändert: Zeilen behalten (kein Flackern, Klicks bleiben).
            for row, activity in zip(self._row_widgets, activities, strict=True):
                row.update_activity(activity)
            return
        for row in self._row_widgets:
            self._rows.removeWidget(row)
            row.deleteLater()
        self._row_widgets = []
        for index, activity in enumerate(activities):
            row = _ActivityRow(activity)
            row.clicked.connect(self.activity_clicked)
            self._rows.insertWidget(index, row)
            self._row_widgets.append(row)
        self._keys = keys

    def enterEvent(self, event: QEnterEvent) -> None:
        self.hovered.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.hovered.emit(False)
        super().leaveEvent(event)


class ActivityPopup(QObject):
    """Verbindet Feld und Liste: Ausrollen beim Überfahren, verzögertes Einrollen, Position."""

    activity_clicked = Signal(str)

    def __init__(
        self,
        activities: ActivityController,
        indicator: ActivityIndicator,
        panel: ActivityPanel,
        anchor_bottom: QWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._activities = activities
        self._indicator = indicator
        self._panel = panel
        self._anchor_bottom = anchor_bottom  # Unterkante des Banners
        self._open = False
        self._hover = {"indicator": False, "panel": False}
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(_CLOSE_DELAY_MS)
        self._connect_signals()

    def _connect_signals(self) -> None:
        self._activities.changed.connect(self._refresh)
        self._indicator.hovered.connect(lambda inside: self._set_hover("indicator", inside))
        self._panel.hovered.connect(lambda inside: self._set_hover("panel", inside))
        self._panel.activity_clicked.connect(self._on_clicked)
        self._close_timer.timeout.connect(self.close)
        self._panel.animation.finished.connect(self._on_animation_finished)

    def is_open(self) -> bool:
        return self._open

    def _refresh(self) -> None:
        entries = self._activities.activities()
        self._indicator.show_activities(entries)
        self._panel.show_activities(entries)
        if not entries:
            self.close()

    def _set_hover(self, part: str, inside: bool) -> None:
        self._hover[part] = inside
        if any(self._hover.values()):
            self._close_timer.stop()
            if part == "indicator" and inside:
                self.open()
        else:
            self._close_timer.start()

    def _on_clicked(self, tab: str) -> None:
        self.activity_clicked.emit(tab)
        self.close()

    def _rects(self) -> tuple[QRect, QRect]:
        """Eingerollte und ausgerollte Geometrie im Koordinatensystem des Elternfensters."""
        parent = self._panel.parentWidget()
        assert parent is not None
        top_right = self._indicator.mapTo(parent, self._indicator.rect().topRight())
        top = self._anchor_bottom.mapTo(parent, self._anchor_bottom.rect().bottomLeft()).y() + 1
        width = max(self._indicator.width(), INDICATOR_WIDTH)
        left = top_right.x() - width + 1
        height = max(0, parent.height() - top)
        return QRect(left, top, width, 0), QRect(left, top, width, height)

    def open(self) -> None:
        if not self._indicator.isVisible():
            return
        closed, opened = self._rects()
        self._open = True
        self._panel.animation.stop()
        if not self._panel.isVisible():
            self._panel.setGeometry(closed)
            self._panel.show()
        self._panel.raise_()
        self._panel.animation.setStartValue(self._panel.geometry())
        self._panel.animation.setEndValue(opened)
        self._panel.animation.start()

    def close(self) -> None:
        if not self._open:
            return
        self._open = False
        closed, _ = self._rects()
        self._panel.animation.stop()
        self._panel.animation.setStartValue(self._panel.geometry())
        self._panel.animation.setEndValue(closed)
        self._panel.animation.start()

    def relayout(self) -> None:
        """Bei Größenänderung des Fensters die ausgerollte Liste anpassen."""
        if self._open and self._panel.animation.state() != QPropertyAnimation.State.Running:
            self._panel.setGeometry(self._rects()[1])

    def _on_animation_finished(self) -> None:
        if not self._open:
            self._panel.hide()
