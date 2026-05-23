# [ MEMBRO 3 - BLOCO 3 ]:
# Agora, este novo database.py tem uma função específica: Ele cria o banco de dados, implementando os modelos (classes) presentes no models.py.
import models
from sqlmodel import SQLModel, create_engine, Session

arquivo_sqlite = "estudos.db"
url_sqlite = f"sqlite:///{ARQUIVO_BANCO}"

engine = create_engine(url_sqlite)

def criar_bd_e_tabelas():
    """Cria o arquivo estudos.db e as tabelas mapeadas no models.py, se não existirem."""
    SQLModel.metadata.create_all(engine)
    print("Banco de dados SQLite foi inicializado adequadamente.")
