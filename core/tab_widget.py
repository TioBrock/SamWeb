from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabBar,
    QStackedWidget, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

class ChromeTabWidget(QWidget):
    """
    Um substituto customizado para QTabWidget que permite que o botão '+'
    acompanhe as abas dinamicamente até o limite da tela, momento em que
    fica fixo na direita.
    """
    tabCloseRequested = pyqtSignal(int)
    currentChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Top Bar (TabBar + Button + Stretch) ---
        self.top_bar = QWidget()
        self.top_bar.setObjectName("top_bar")
        self.top_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("widget_abas") # Mantém a compatibilidade com o QSS
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)

        self.btn_nova_aba = QPushButton("+")
        self.btn_nova_aba.setObjectName("btn_nova_aba")
        self.btn_nova_aba.setFixedSize(28, 28)
        self.btn_nova_aba.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nova_aba.setToolTip("Nova Aba  (Ctrl + T)")

        top_layout.addWidget(self.tab_bar)
        top_layout.addWidget(self.btn_nova_aba)
        top_layout.addStretch() # Empurra tudo para a esquerda

        # --- Conteúdo (Páginas) ---
        self.stacked_widget = QStackedWidget()

        layout.addWidget(self.top_bar)
        layout.addWidget(self.stacked_widget)

        # Conexões de eventos
        self.tab_bar.tabCloseRequested.connect(self.tabCloseRequested.emit)
        self.tab_bar.currentChanged.connect(self._on_current_changed)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)

    def _on_current_changed(self, index: int):
        if index >= 0:
            self.stacked_widget.setCurrentIndex(index)
        self.currentChanged.emit(index)

    def _on_tab_moved(self, from_index: int, to_index: int):
        # Quando a aba é arrastada, precisamos reordenar o StackedWidget também
        widget = self.stacked_widget.widget(from_index)
        self.stacked_widget.removeWidget(widget)
        self.stacked_widget.insertWidget(to_index, widget)

    # --- QTabWidget API Wrapper ---
    def addTab(self, widget, title: str) -> int:
        index = self.tab_bar.addTab(title)
        self.stacked_widget.insertWidget(index, widget)
        return index

    def removeTab(self, index: int):
        self.tab_bar.removeTab(index)
        widget = self.stacked_widget.widget(index)
        if widget:
            self.stacked_widget.removeWidget(widget)
            widget.deleteLater()

    def setCurrentIndex(self, index: int):
        self.tab_bar.setCurrentIndex(index)

    def currentIndex(self) -> int:
        return self.tab_bar.currentIndex()

    def currentWidget(self):
        return self.stacked_widget.currentWidget()

    def indexOf(self, widget) -> int:
        return self.stacked_widget.indexOf(widget)

    def widget(self, index: int):
        return self.stacked_widget.widget(index)

    def setTabText(self, index: int, text: str):
        self.tab_bar.setTabText(index, text)

    def tabText(self, index: int) -> str:
        return self.tab_bar.tabText(index)

    def count(self) -> int:
        return self.tab_bar.count()
