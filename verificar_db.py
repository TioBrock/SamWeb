import sqlite3
from pathlib import Path

def verificar_historico():
    db_path = Path("profile/History.db")
    print("\n" + "="*50)
    print(" Verificação do Banco de Dados: SamWeb History.db")
    print("="*50)

    if not db_path.exists():
        print(f"❌ O arquivo do banco de dados não foi encontrado em: {db_path.absolute()}")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, titulo, url, data_acesso FROM historico ORDER BY id DESC LIMIT 5")
            rows = cursor.fetchall()
            
            print(f"✅ Banco de dados encontrado e conectado com sucesso!")
            print(f"   (Tamanho: {db_path.stat().st_size / 1024:.1f} KB)\n")
            
            if not rows:
                print("📝 O banco de dados está vazio. Nenhum histórico foi salvo ainda.")
            else:
                print("ÚLTIMOS SITES VISITADOS (Top 5):\n" + "-"*40)
                for r in rows:
                    print(f"[{r[0]}] {r[3][:16]}")
                    print(f" ╰─ {r[1][:50]}")
                    print(f" ╰─ {r[2][:50]}\n")
                    
    except sqlite3.Error as e:
        print(f"❌ Erro ao acessar o banco de dados: {e}")
    except Exception as e:
        print(f"❌ Erro desconhecido: {e}")

if __name__ == "__main__":
    verificar_historico()
