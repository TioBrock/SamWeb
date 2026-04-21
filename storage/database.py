import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime

class DatabaseManager:
    """
    Gerenciador do banco de dados SQLite3 do SamWeb.
    Lida com a criação de tabelas e a inserção segura de dados, como o histórico.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._inicializar_banco()

    def _inicializar_banco(self) -> None:
        """Cria as tabelas necessárias se não existirem."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS historico (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        titulo TEXT,
                        data_acesso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"[DB_ERROR] Falha ao criar banco de dados: {e}")

    def adicionar_historico(self, url: str, titulo: Optional[str] = None) -> None:
        """
        Adiciona uma entrada ao histórico de navegação.
        Ignora páginas internas como about:blank.
        """
        if not url or url == "about:blank" or url.startswith("file://"):
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO historico (url, titulo) VALUES (?, ?)",
                    (url, titulo or "Sem Título")
                )
                conn.commit()
        except sqlite3.Error as e:
            print(f"[DB_ERROR] Erro ao gravar no histórico: {e}")

    def obter_historico(self, limite: int = 100, busca: str = "") -> list:
        """
        Retorna o histórico salvo. Se `busca` for provida, filtra pelo título ou URL.
        Retorna lista de tuplas: (id, url, titulo, data_acesso).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if busca:
                    termo = f"%{busca}%"
                    cursor.execute("""
                        SELECT id, url, titulo, data_acesso FROM historico 
                        WHERE titulo LIKE ? OR url LIKE ? 
                        ORDER BY id DESC LIMIT ?
                    """, (termo, termo, limite))
                else:
                    cursor.execute("""
                        SELECT id, url, titulo, data_acesso FROM historico 
                        ORDER BY id DESC LIMIT ?
                    """, (limite,))
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"[DB_ERROR] Erro ao carregar histórico: {e}")
            return []

    def deletar_historico(self, id_registro: int) -> None:
        """
        Remove um único registro do histórico pelo seu ID.

        Parâmetros:
            id_registro (int): O ID da linha a ser deletada.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM historico WHERE id = ?", (id_registro,))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[DB_ERROR] Erro ao deletar entrada do histórico: {e}")

    def limpar_historico(self) -> None:
        """Remove todos os registros do histórico de navegação."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM historico")
                conn.commit()
        except sqlite3.Error as e:
            print(f"[DB_ERROR] Erro ao limpar histórico: {e}")
