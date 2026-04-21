"""
main.py — Ponto de entrada do Navegador SamWeb
===============================================
Autor: Equipe SamWeb / EEEP Salomão Alves de Moura
Descrição: Inicializa a aplicação PyQt6, aplica o tema visual
           e exibe a janela principal do navegador.
"""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QPalette, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QToolBar,
    QLineEdit,
    QPushButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QProgressBar,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings,
)

from storage.database import DatabaseManager
from core.history_view import HistoryDialog
from core.tab_widget import ChromeTabWidget

# ---------------------------------------------------------------------------
# Constantes de caminho — resolvidas de forma absoluta a partir do main.py
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
HOME_PAGE: Path = BASE_DIR / "home_screen" / "index.html"
HOME_URL: QUrl = QUrl.fromLocalFile(str(HOME_PAGE))
PROFILE_DIR: Path = BASE_DIR / "profile"
QSS_DARK_PATH: Path = BASE_DIR / "assets" / "styles.qss"
QSS_LIGHT_PATH: Path = BASE_DIR / "assets" / "styles_light.qss"
ICON_PATH: Path = BASE_DIR / "assets" / "images" / "sam-logo.png"

_HOME_URL_STR: str = HOME_URL.toString()

# Estado global do tema para aplicar em buscas
TEMA_ATUAL: str = "light"

# Instância global de conexão com o banco de dados
DB_MANAGER: DatabaseManager = DatabaseManager(PROFILE_DIR / "History.db")


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def carregar_qss(caminho: Path) -> str:
    """
    Lê e retorna o conteúdo do arquivo QSS.

    Parâmetros:
        caminho (Path): Caminho absoluto para o arquivo .qss.

    Retorna:
        str: Conteúdo do arquivo ou string vazia em caso de erro.
    """
    try:
        conteudo = caminho.read_text(encoding="utf-8")
        # Converte caminhos de ícones "icons/" para caminhos absolutos do sistema
        # Para que o PyQt os encontre, independentemente do Current Working Directory.
        base_uri = (BASE_DIR / "assets").as_posix()
        conteudo = conteudo.replace("url('icons/", f"url('{base_uri}/icons/")
        return conteudo
    except FileNotFoundError:
        print(f"[AVISO] QSS não encontrado: {caminho}")
        return ""
    except OSError as erro:
        print(f"[ERRO] Falha ao ler QSS: {erro}")
        return ""


def formatar_url(texto: str) -> QUrl:
    """
    Converte o texto da omnibox em QUrl válida.

    Regras:
        - Começa com http:// ou https://:  usa diretamente.
        - Contém ponto sem espaço:         assume domínio → adiciona https://.
        - Demais casos:                    pesquisa no Google.

    Parâmetros:
        texto (str): Texto bruto digitado pelo usuário.

    Retorna:
        QUrl: URL formatada pronta para navegação.
    """
    texto = texto.strip()
    if texto.startswith(("http://", "https://")):
        return QUrl(texto)
    if "." in texto and " " not in texto:
        return QUrl(f"https://{texto}")
    return QUrl(f"https://www.google.com/search?q={texto.replace(' ', '+')}")


def _modo_escuro() -> bool:
    """
    Detecta se o sistema operacional está em modo escuro.

    Baseia-se na luminosidade da cor de fundo da paleta Qt ativa.

    Retorna:
        bool: True se o fundo for escuro (luminosidade < 128).
    """
    bg = QApplication.palette().color(QPalette.ColorRole.Window)
    return bg.lightness() < 128


def _aplicar_tema(app: QApplication, forcar: Optional[str] = None) -> None:
    """
    Carrega e aplica o arquivo QSS correspondente ao tema atual.

    Parâmetros:
        app (QApplication): Instância principal da aplicação.
        forcar (str | None): Se 'dark' ou 'light', ignora a preferência do sistema.
    """
    global TEMA_ATUAL
    if forcar == "dark":
        escuro = True
    elif forcar == "light":
        escuro = False
    else:
        escuro = _modo_escuro()

    TEMA_ATUAL = "dark" if escuro else "light"

    caminho = QSS_DARK_PATH if escuro else QSS_LIGHT_PATH
    estilo = carregar_qss(caminho)
    if not estilo:                          # fallback para dark
        estilo = carregar_qss(QSS_DARK_PATH)
    if estilo:
        app.setStyleSheet(estilo)


# ---------------------------------------------------------------------------
# SamWebPage — página com target='_blank' e bridge de tema dark/light
# ---------------------------------------------------------------------------

class SamWebPage(QWebEnginePage):
    """
    Página web customizada do SamWeb.

    Responsabilidades:
        - Interceptar links target='_blank' e window.open() para abrir
          novas abas internas ao invés de janelas separadas.
        - Capturar a mensagem 'SAMWEB_THEME:dark/light' enviada pelo
          JavaScript da homepage quando o usuário alterna o tema.

    Parâmetros:
        perfil  (QWebEngineProfile): Perfil de sessão compartilhado.
        janela  (MainWindow):        Referência à janela principal.
        parent:                      Widget pai opcional.
    """

    # Sinal emitido quando o usuário alterna o tema na homepage
    tema_alterado: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        perfil: QWebEngineProfile,
        janela: "MainWindow",
        parent=None,
    ) -> None:
        super().__init__(perfil, parent)
        self._janela = janela

    def createWindow(
        self, window_type: QWebEnginePage.WebWindowType
    ) -> "QWebEnginePage":
        """
        Intercepta abertura de nova janela e cria uma nova aba no SamWeb.

        Parâmetros:
            window_type: Tipo de janela solicitado pelo motor Chromium.

        Retorna:
            QWebEnginePage: Página da nova aba (o motor carregará a URL nela).
        """
        nova_aba = self._janela._abrir_nova_aba(sem_home=True)
        return nova_aba.page()

    def javaScriptConsoleMessage(
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        line_number: int,
        source_id: str,
    ) -> None:
        """
        Escuta mensagens do console JavaScript.

        Quando detecta 'SAMWEB_THEME:dark' ou 'SAMWEB_THEME:light' — enviadas
        pela homepage ao acionar o botão de tema — emite o sinal tema_alterado
        para sincronizar o chrome (barra de navegação) com a preferência do usuário.

        Parâmetros:
            level:       Nível de severidade (info, warning, error).
            message:     Texto da mensagem de console.
            line_number: Linha do script que gerou a mensagem.
            source_id:   Origem do script.
        """
        if message.startswith("SAMWEB_THEME:"):
            tema = message.split(":", 1)[1].strip()
            if tema in ("dark", "light"):
                self.tema_alterado.emit(tema)


# ---------------------------------------------------------------------------
# BrowserTab — aba individual de navegação
# ---------------------------------------------------------------------------

class BrowserTab(QWebEngineView):
    """
    Aba individual do Navegador SamWeb.

    Usa SamWebPage para suporte a target='_blank' e sincronização de tema.
    Garante expansão responsiva preenchendo toda a área disponível.

    Parâmetros:
        perfil (QWebEngineProfile): Perfil de sessão compartilhado.
        janela (MainWindow):        Referência à janela principal.
        parent (QWidget | None):    Widget pai opcional.
    """

    def __init__(
        self,
        perfil: QWebEngineProfile,
        janela: "MainWindow",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sam_page = SamWebPage(perfil, janela, self)
        self.setPage(self._sam_page)
        # Expande para preencher toda a área da aba (responsividade)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Hook: Registrar histórico de onde navegou ao terminar de carregar
        self.loadFinished.connect(self._registrar_historico)

    def _registrar_historico(self, ok: bool) -> None:
        """Salva a página no banco de dados SQLite caso não seja a Home."""
        if ok and not self.eh_home():
            titulo = self.title()
            url_str = self.url().toString()
            global DB_MANAGER
            DB_MANAGER.adicionar_historico(url_str, titulo)

    def carregar_home(self) -> None:
        """
        Carrega a Home Screen local (index.html).

        Após o carregamento, injeta JS para:
          - Aplicar o tema do sistema (se sem preferência salva pelo usuário).
          - Interceptar o botão de alternância de tema da homepage.
        """
        if not HOME_PAGE.exists():
            self.setHtml(
                "<html><body style='font-family:sans-serif;color:#e74c3c;padding:40px'>"
                "<h2>⚠️ Home Screen não encontrada</h2>"
                f"<p>Caminho esperado: <code>{HOME_PAGE}</code></p>"
                "</body></html>"
            )
            return

        self.setUrl(HOME_URL)
        tema = "dark" if _modo_escuro() else "light"

        def _ao_carregar(ok: bool, t: str = tema) -> None:
            if ok:
                self._injetar_tema(t)
            # Desconecta após o primeiro carregamento para não acumular callbacks
            try:
                self._sam_page.loadFinished.disconnect(_ao_carregar)
            except RuntimeError:
                pass

        self._sam_page.loadFinished.connect(_ao_carregar)

    def _injetar_tema(self, tema: str) -> None:
        """
        Injeta código JavaScript na homepage para sincronizar o tema.

        O JS injeto realiza duas ações:
          1. Aplica a classe 'dark' ou 'light' no <html> se não houver
             preferência salva no localStorage.
          2. Envolve (hooks) a função toggleTheme() original para enviar
             'SAMWEB_THEME:<tema>' via console.log, notificando o Python.

        Parâmetros:
            tema (str): Tema do sistema — 'dark' ou 'light'.
        """
        js = f"""
        (function() {{
            const html = document.documentElement;

            // Aplica o tema do sistema se não houver preferência no site
            const salvo = localStorage.getItem('theme');
            if (!salvo) {{
                if ('{tema}' === 'dark') html.classList.add('dark');
                else html.classList.remove('dark');
            }}

            // INFORMA O TEMA ATUAL PARA O PYTHON (sincroniza no startup)
            const t_init = html.classList.contains('dark') ? 'dark' : 'light';
            console.log('SAMWEB_THEME:' + t_init);

            // Hook do toggleTheme garantindo sincronização ao clicar
            if (!window._samWebThemeHooked) {{
                window._samWebThemeHooked = true;
                const orig = window.toggleTheme;
                window.toggleTheme = function() {{
                    orig.call(this);
                    const t = html.classList.contains('dark') ? 'dark' : 'light';
                    console.log('SAMWEB_THEME:' + t);
                }};
            }}
        }})();
        """
        self._sam_page.runJavaScript(js)

    def eh_home(self) -> bool:
        """Retorna True se a aba estiver exibindo a Home Screen."""
        return self.url().toString() == _HOME_URL_STR


# ---------------------------------------------------------------------------
# MainWindow — janela principal do navegador
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """
    Janela principal do Navegador SamWeb.

    Responsabilidades:
        - Barra de navegação superior (omnibox, botões circulares, nova aba).
        - QTabWidget com múltiplas abas de navegação.
        - Sincronização bidirecional do tema dark/light entre a homepage e
          o chrome (barra de ferramentas e abas) do navegador.
    """

    def __init__(self) -> None:
        super().__init__()
        self._configurar_perfil()
        self._configurar_janela()
        self._criar_barra_navegacao()
        self._criar_abas()
        self._configurar_atalhos()
        self._abrir_nova_aba()      # Primeira aba com a Home Screen

    # ------------------------------------------------------------------
    # Atalhos e Ferramentas Globais
    # ------------------------------------------------------------------
    def _configurar_atalhos(self) -> None:
        """Configura os atalhos de teclado do navegador."""
        atalho_hist = QShortcut(QKeySequence("Ctrl+H"), self)
        atalho_hist.activated.connect(self._abrir_historico)

    def _abrir_historico(self) -> None:
        """Abre a janela de visualização do Histórico local."""
        dialog = HistoryDialog(DB_MANAGER, self)
        dialog.url_selecionada.connect(self._abrir_url_do_historico)
        dialog.show()

    def _abrir_url_do_historico(self, url: QUrl) -> None:
        """Abre a URL selecionada no histórico na aba atual."""
        if aba := self._aba_atual():
            aba.setUrl(url)
        else:
            self._abrir_nova_aba(url)

    # ------------------------------------------------------------------
    # Perfil persistente
    # ------------------------------------------------------------------

    def _configurar_perfil(self) -> None:
        """
        Cria o QWebEngineProfile apontando para profile/ e habilita as
        permissões necessárias para que o index.html local carregue
        recursos externos (Tailwind CDN, Google Fonts, imagens locais).
        """
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._perfil = QWebEngineProfile("SamWebProfile", self)
        self._perfil.setPersistentStoragePath(str(PROFILE_DIR))
        self._perfil.setCachePath(str(PROFILE_DIR / "Cache"))
        self._perfil.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        # -- Configuração WebEngine
        cfg = self._perfil.settings()
        cfg.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        cfg.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        cfg.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        cfg.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

    # ------------------------------------------------------------------
    # Configuração da janela
    # ------------------------------------------------------------------

    def _configurar_janela(self) -> None:
        """Define título, tamanho mínimo e ícone da janela principal."""
        self.setWindowTitle("SamWeb — EEEP Salomão Alves de Moura")
        self.setMinimumSize(400, 300)       # Mais flexível para redimensionamento
        self.resize(1024, 768)
        self.statusBar().hide()
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

    # ------------------------------------------------------------------
    # Barra de navegação
    # ------------------------------------------------------------------

    def _criar_barra_navegacao(self) -> None:
        """
        Constrói a barra superior do navegador com três zonas:

          [← → ↻]   [omnibox expansível]   [+]

          - Grupo nav:  três botões circulares com container agrupador.
          - Omnibox:    campo de URL/pesquisa expansível (pill shape).
          - Nova aba:   botão circular verde.
        """
        toolbar = QToolBar("Navegação")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setObjectName("toolbar_principal")
        toolbar.setContentsMargins(12, 6, 12, 6)
        self.addToolBar(toolbar)

        # ── Grupo: Voltar / Avançar / Recarregar ─────────────────────
        nav_group = QWidget()
        nav_group.setObjectName("nav_group")
        nav_layout = QHBoxLayout(nav_group)
        nav_layout.setContentsMargins(4, 3, 4, 3)
        nav_layout.setSpacing(1)

        self._btn_voltar = QPushButton()
        self._btn_voltar.setObjectName("btn_nav_voltar")
        self._btn_voltar.setFixedSize(34, 34)
        self._btn_voltar.setToolTip("Voltar  (Alt + ←)")
        self._btn_voltar.clicked.connect(self._navegar_voltar)

        self._btn_avancar = QPushButton()
        self._btn_avancar.setObjectName("btn_nav_avancar")
        self._btn_avancar.setFixedSize(34, 34)
        self._btn_avancar.setToolTip("Avançar  (Alt + →)")
        self._btn_avancar.clicked.connect(self._navegar_avancar)

        self._btn_recarregar = QPushButton()
        self._btn_recarregar.setObjectName("btn_nav_recarregar")
        self._btn_recarregar.setFixedSize(34, 34)
        self._btn_recarregar.setToolTip("Recarregar  (F5)")
        self._btn_recarregar.clicked.connect(self._recarregar_pagina)

        nav_layout.addWidget(self._btn_voltar)
        nav_layout.addWidget(self._btn_avancar)
        nav_layout.addWidget(self._btn_recarregar)
        toolbar.addWidget(nav_group)

        # ── Separador ────────────────────────────────────────────────
        _sep = QWidget()
        _sep.setFixedWidth(10)
        toolbar.addWidget(_sep)

        # ── Omnibox (Barra de Endereços) ──────────────────────────────
        self._omnibox = QLineEdit()
        self._omnibox.setObjectName("omnibox")
        self._omnibox.setPlaceholderText("Pesquise ou digite um endereço…")
        self._omnibox.setFixedHeight(36)
        self._omnibox.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._omnibox.returnPressed.connect(self._navegar_por_omnibox)
        toolbar.addWidget(self._omnibox)

        # ── Separador + Botão de Histórico ───────────────────────────
        _sep2 = QWidget()
        _sep2.setFixedWidth(6)
        toolbar.addWidget(_sep2)

        self._btn_historico = QPushButton()
        self._btn_historico.setObjectName("btn_historico")
        self._btn_historico.setFixedSize(34, 34)
        self._btn_historico.setToolTip("Histórico  (Ctrl + H)")
        self._btn_historico.clicked.connect(self._abrir_historico)
        toolbar.addWidget(self._btn_historico)

    # ------------------------------------------------------------------
    # Widget de abas e Container (Com Barra de Progresso)
    # ------------------------------------------------------------------

    def _criar_abas(self) -> None:
        """Inicializa um layout vertical contendo a progress bar e o tab widget customizado.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra de progresso fina
        self._progressbar = QProgressBar()
        self._progressbar.setFixedHeight(2)
        self._progressbar.setTextVisible(False)
        self._progressbar.hide()

        # Widget de navegação
        self._abas = ChromeTabWidget(self)
        
        self._abas.btn_nova_aba.clicked.connect(self._abrir_nova_aba)
        self._abas.tabCloseRequested.connect(self._fechar_aba)
        self._abas.currentChanged.connect(self._ao_trocar_aba)

        layout.addWidget(self._progressbar)
        layout.addWidget(self._abas)
        self.setCentralWidget(container)

    # ------------------------------------------------------------------
    # Gerenciamento de abas
    # ------------------------------------------------------------------

    def _abrir_nova_aba(
        self,
        url: QUrl | None = None,
        sem_home: bool = False,
    ) -> BrowserTab:
        """
        Cria e insere uma nova aba no QTabWidget.

        Parâmetros:
            url (QUrl | None): URL inicial. Se None e sem_home=False, carrega home.
            sem_home (bool):   Se True, cria aba vazia (usado por createWindow).

        Retorna:
            BrowserTab: A nova aba criada.
        """
        aba = BrowserTab(perfil=self._perfil, janela=self, parent=self)

        # Sincroniza o tema da homepage com o chrome do navegador
        aba._sam_page.tema_alterado.connect(self._ao_tema_web_alterado)
        aba.urlChanged.connect(self._ao_mudar_url)
        aba.titleChanged.connect(self._ao_mudar_titulo)
        
        # Conecta eventos de progresso de rede à interface global
        aba.loadProgress.connect(self._ao_progresso)
        aba.loadFinished.connect(self._ao_fim_carregamento)

        indice = self._abas.addTab(aba, "Nova Aba")
        self._abas.setCurrentIndex(indice)

        if url:
            aba.setUrl(url)
        elif not sem_home:
            aba.carregar_home()

        return aba

    def _fechar_aba(self, indice: int) -> None:
        """
        Fecha a aba no índice fornecido.
        Garante que ao menos uma aba permaneça aberta (reinicia com a home).

        Parâmetros:
            indice (int): Posição da aba a ser fechada.
        """
        if self._abas.count() > 1:
            self._abas.removeTab(indice)
        else:
            if aba := self._aba_atual():
                aba.carregar_home()

    def _aba_atual(self) -> BrowserTab | None:
        """
        Retorna a aba atualmente visível, ou None.

        Retorna:
            BrowserTab | None: A aba ativa, ou None se não houver.
        """
        widget = self._abas.currentWidget()
        return widget if isinstance(widget, BrowserTab) else None

    # ------------------------------------------------------------------
    # Ações de navegação
    # ------------------------------------------------------------------

    def _navegar_voltar(self) -> None:
        """Navega para a página anterior no histórico da aba ativa."""
        if aba := self._aba_atual():
            aba.back()

    def _navegar_avancar(self) -> None:
        """Avança para a próxima página no histórico da aba ativa."""
        if aba := self._aba_atual():
            aba.forward()

    def _recarregar_pagina(self) -> None:
        """Recarrega a página da aba ativa."""
        if aba := self._aba_atual():
            aba.reload()

    def _navegar_por_omnibox(self) -> None:
        """
        Processa o texto da omnibox e navega para a URL resultante.
        Usa formatar_url() para distinguir entre URL, domínio e pesquisa.
        """
        texto = self._omnibox.text().strip()
        if not texto:
            return
        if aba := self._aba_atual():
            aba.setUrl(formatar_url(texto))

    # ------------------------------------------------------------------
    # Slots de atualização da interface
    # ------------------------------------------------------------------

    def _ao_mudar_url(self, url: QUrl) -> None:
        """
        Atualiza a omnibox quando a URL da aba ativa muda.
        Limpa o campo quando a aba está na Home Screen.

        Parâmetros:
            url (QUrl): Nova URL carregada.
        """
        if self.sender() is self._aba_atual():
            url_str = url.toString()
            if url_str in (_HOME_URL_STR, "", "about:blank"):
                self._omnibox.clear()
            else:
                self._omnibox.setText(url_str)

    def _ao_mudar_titulo(self, titulo: str) -> None:
        """
        Atualiza o rótulo da aba e o título da janela.

        Parâmetros:
            titulo (str): Título da página carregada.
        """
        emissora = self.sender()
        idx = self._abas.indexOf(emissora)
        if idx != -1:
            curto = (titulo[:22] + "…") if len(titulo) > 22 else titulo
            self._abas.setTabText(idx, curto or "Nova Aba")
        if emissora is self._aba_atual():
            self.setWindowTitle(f"{titulo} — SamWeb" if titulo else "SamWeb")

    def _ao_trocar_aba(self, indice: int) -> None:
        """
        Sincroniza a omnibox ao trocar de aba.

        Parâmetros:
            indice (int): Índice da aba recém-selecionada.
        """
        aba = self._abas.widget(indice)
        if isinstance(aba, BrowserTab):
            url_str = aba.url().toString()
            if url_str in ("", "about:blank", _HOME_URL_STR):
                self._omnibox.clear()
            else:
                self._omnibox.setText(url_str)
        self._progressbar.hide()   # Esconde a barra ao pular entre abas para evitar sujeira visual

    def _ao_progresso(self, progresso: int) -> None:
        """Atualiza a QProgressBar durante o carregamento da rede."""
        emissora = self.sender()
        if emissora is self._aba_atual():
            if progresso < 100:
                self._progressbar.show()
                self._progressbar.setValue(progresso)
            else:
                self._progressbar.hide()

    def _ao_fim_carregamento(self, ok: bool) -> None:
        """Mantém a barra cheia por um breve momento e então oculta."""
        emissora = self.sender()
        if emissora is self._aba_atual():
            self._progressbar.setValue(100)
            
            def esconder():
                self._progressbar.hide()
                self._progressbar.setValue(0)
                
            QTimer.singleShot(600, esconder)

    def _ao_tema_web_alterado(self, tema: str) -> None:
        """
        Sincroniza o tema do chrome PyQt6 e das páginas.
        """
        app = QApplication.instance()
        if app:
            _aplicar_tema(app, forcar=tema)
            escuro = (tema == "dark")
            
            # (WebAttribute.ForceDarkMode falha no PyQt6 nativo mais antigo)
            # Como fallback pra outros sites compatíveis com prefers-color-scheme
            js_comum = f"document.documentElement.style.colorScheme = '{tema}';"
            js_home = f"if ('{tema}' === 'dark') document.documentElement.classList.add('dark'); else document.documentElement.classList.remove('dark');"

            for i in range(self._abas.count()):
                t = self._abas.widget(i)
                if isinstance(t, BrowserTab):
                    if t.eh_home():
                        t.page().runJavaScript(js_home)
                    else:
                        t.page().runJavaScript(js_comum)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Inicializa a QApplication, aplica o tema detectado do sistema,
    configura o listener de mudança de paleta e exibe a MainWindow.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("SamWeb")
    app.setOrganizationName("EEEP Salomao Alves de Moura")

    # Aplica o tema correto (escuro ou claro) conforme preferência do sistema
    _aplicar_tema(app)

    # Reaplica automaticamente se o usuário mudar o modo no SO
    app.paletteChanged.connect(lambda _: _aplicar_tema(app))

    janela = MainWindow()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
