"""
history_view.py — Painel de Histórico de Navegação do SamWeb
=============================================================
Exibe o histórico salvo no SQLite, com busca em tempo real,
favicon de cada site, exclusão individual e limpeza total.
Herda o tema dark/light automaticamente via QSS do QApplication.
"""

from urllib.parse import urlparse

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QAbstractItemView, QPushButton, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QUrl, QByteArray, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest


class HistoryDialog(QDialog):
    """
    Janela de Histórico de Navegação do SamWeb.

    Funcionalidades:
        - Tabela com favicon, data, título e URL.
        - Busca em tempo real filtrando por título ou URL.
        - Deletar um único registro via botão de lixeira por linha.
        - Limpar todo o histórico com confirmação.
        - Segue automaticamente o tema claro/escuro do navegador.
    """

    url_selecionada = pyqtSignal(QUrl)

    _COLUNAS = ["", "Data/Hora", "Título", "URL", ""]  # "" = favicon e ação

    def __init__(self, db_manager, parent=None) -> None:
        super().__init__(parent)
        self.db_manager = db_manager
        self._network = QNetworkAccessManager(self)
        self._favicon_cache: dict[str, QIcon] = {}

        self.setWindowTitle("Histórico — SamWeb")
        self.setObjectName("history_dialog")
        self.resize(860, 560)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._configurar_ui()
        self._carregar_dados()

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def _configurar_ui(self) -> None:
        """Monta todos os componentes visuais da janela."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Topo: título + busca ──────────────────────────────────────
        topo = QHBoxLayout()

        titulo_lbl = QLabel("Histórico de Navegação")
        titulo_lbl.setObjectName("history_title")

        self._busca = QLineEdit()
        self._busca.setObjectName("omnibox")
        self._busca.setPlaceholderText("Pesquise por título ou URL…")
        self._busca.setFixedWidth(260)
        self._busca.setFixedHeight(34)
        self._busca.textChanged.connect(self._ao_buscar)

        topo.addWidget(titulo_lbl)
        topo.addStretch()
        topo.addWidget(self._busca)
        layout.addLayout(topo)

        # ── Tabela principal ──────────────────────────────────────────
        self._tabela = QTableWidget(0, 5)
        self._tabela.setObjectName("history_table")
        self._tabela.setHorizontalHeaderLabels(
            ["", "Data/Hora", "Título", "URL", ""]
        )
        self._tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabela.setAlternatingRowColors(True)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.setShowGrid(False)
        self._tabela.setIconSize(QSize(16, 16))

        hdr = self._tabela.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)          # favicon
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # data
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)         # título
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)         # url
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)           # ação
        self._tabela.setColumnWidth(0, 28)
        self._tabela.setColumnWidth(4, 36)
        self._tabela.verticalHeader().setDefaultSectionSize(30)
        
        self._tabela.cellDoubleClicked.connect(self._ao_clicar_duplo_linha)

        layout.addWidget(self._tabela)

        # ── Rodapé: contador + limpar ─────────────────────────────────
        rodape = QHBoxLayout()

        self._lbl_contador = QLabel()
        self._lbl_contador.setObjectName("history_counter")

        btn_limpar = QPushButton("🗑  Limpar Todo o Histórico")
        btn_limpar.setObjectName("btn_limpar_historico")
        btn_limpar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_limpar.clicked.connect(self._limpar_tudo)

        rodape.addWidget(self._lbl_contador)
        rodape.addStretch()
        rodape.addWidget(btn_limpar)
        layout.addLayout(rodape)

    # ------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------

    def _carregar_dados(self, busca: str = "") -> None:
        """Carrega registros do SQLite e preenche a tabela."""
        registros = self.db_manager.obter_historico(limite=200, busca=busca)
        self._tabela.setRowCount(0)  # limpa sem artefatos

        for linha_idx, registro in enumerate(registros):
            id_db, url, titulo, data_acesso = registro

            # Formata data
            data_str = str(data_acesso).split(".")[0] if "." in str(data_acesso) else str(data_acesso)

            self._tabela.insertRow(linha_idx)

            # Col 0 — Favicon (placeholder por enquanto, depois preenche assíncrono)
            item_icon = QTableWidgetItem()
            item_icon.setData(Qt.ItemDataRole.UserRole, id_db)  # guarda o ID
            item_icon.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tabela.setItem(linha_idx, 0, item_icon)
            self._solicitar_favicon(url, linha_idx)

            # Col 1 — Data
            item_data = QTableWidgetItem(data_str)
            item_data.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tabela.setItem(linha_idx, 1, item_data)

            # Col 2 — Título
            item_titulo = QTableWidgetItem(str(titulo))
            item_titulo.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            self._tabela.setItem(linha_idx, 2, item_titulo)

            # Col 3 — URL
            item_url = QTableWidgetItem(str(url))
            item_url.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            self._tabela.setItem(linha_idx, 3, item_url)

            # Col 4 — Botão deletar
            btn_del = QPushButton("🗑")
            btn_del.setObjectName("btn_deletar_linha")
            btn_del.setFixedSize(28, 24)
            btn_del.setToolTip("Remover esta entrada")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda _, rid=id_db: self._deletar_linha(rid))
            self._tabela.setCellWidget(linha_idx, 4, btn_del)

        total = len(registros)
        self._lbl_contador.setText(
            f"{total} entrada{'s' if total != 1 else ''} encontrada{'s' if total != 1 else ''}"
        )

    def _ao_clicar_duplo_linha(self, row: int, col: int) -> None:
        """Emite o sinal com a URL clicada e fecha a janela."""
        item_url = self._tabela.item(row, 3)
        if item_url:
            url_str = item_url.text()
            self.url_selecionada.emit(QUrl(url_str))
            self.accept()

    # ------------------------------------------------------------------
    # Favicon assíncrono
    # ------------------------------------------------------------------

    def _solicitar_favicon(self, url: str, linha: int) -> None:
        """Baixa o favicon do site via API pública do Google."""
        try:
            dominio = urlparse(url).netloc
            if not dominio:
                return

            if dominio in self._favicon_cache:
                self._aplicar_favicon(self._favicon_cache[dominio], linha)
                return

            favicon_url = f"https://www.google.com/s2/favicons?domain={dominio}&sz=16"
            req = QNetworkRequest(QUrl(favicon_url))
            reply = self._network.get(req)

            # Captura `linha` e `dominio` no closure
            reply.finished.connect(
                lambda r=reply, l=linha, d=dominio: self._ao_receber_favicon(r, l, d)
            )
        except Exception:
            pass

    def _ao_receber_favicon(self, reply, linha: int, dominio: str) -> None:
        """Callback quando o favicon é baixado."""
        try:
            dados = reply.readAll()
            if dados:
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray(dados))
                if not pixmap.isNull():
                    icon = QIcon(pixmap)
                    self._favicon_cache[dominio] = icon
                    self._aplicar_favicon(icon, linha)
        except Exception:
            pass
        finally:
            reply.deleteLater()

    def _aplicar_favicon(self, icon: QIcon, linha: int) -> None:
        """Aplica o ícone na célula da tabela (se a linha ainda existir)."""
        if linha < self._tabela.rowCount():
            item = self._tabela.item(linha, 0)
            if item:
                item.setIcon(icon)

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _ao_buscar(self, texto: str) -> None:
        """Recarrega os dados filtrando pelo texto digitado."""
        self._carregar_dados(busca=texto)

    def _deletar_linha(self, id_registro: int) -> None:
        """Remove uma única entrada do histórico e atualiza a tabela."""
        self.db_manager.deletar_historico(id_registro)
        self._carregar_dados(busca=self._busca.text())

    def _limpar_tudo(self) -> None:
        """Pede confirmação e limpa todo o histórico."""
        resposta = QMessageBox.question(
            self,
            "Limpar Histórico",
            "Tem certeza que deseja apagar todo o histórico de navegação?\n"
            "Essa ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.db_manager.limpar_historico()
            self._carregar_dados()
