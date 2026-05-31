# [ MEMBRO 3 - BLOCO 3 ]: Aqui é onde ficarão as classes que serão usadas para salvar os Cards de revisão, que serão organizados em Decks:
from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel

class DeckVideo(SQLModel, table=True):
    """Agrupa os cards gerados por um vídeo do YouTube em um único Deck."""
    video_id: str = Field(primary_key=True, index=True) # O ID do vídeo é a própria ID única de 11 dígitos que caracteriza ele na URL do Youtube.
    titulo: Optional[str] = None # O título do vídeo do Youtube.
    cards: List["Card"] = Relationship(back_populates="deck_video", cascade_delete = True) # Aqui, relaciono o Deck com todos os Cards dele.

class Card(SQLModel, table=True):
    """Modelo dos Cards salvos para revisão espaçada."""
    id: Optional[int] = Field(default=None, primary_key=True)
    texto_legenda: str = Field(min_length=1)
    start_time: float
    end_time: float
    # Por padrão, a data de criação e de revisão de um Card novo será o momento atual:
    data_criacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_proxima_revisao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Adicionei também algumas outras propriedades que podem ser úteis no futuro, para implementar um algoritmo de repetição espaçada:
    
    # Histórico de acertos seguidos (essencial para resetar ou avançar o Card):
    revisoes_consecutivas: int = Field(default=0)
    # Intervalo atual do card em dias (começa em 0 para revisão no mesmo dia):
    intervalo_dias: int = Field(default=0)
    # Fator de facilidade:
    fator_facilidade: float = Field(default=2.5)

    video_id: str = Field(foreign_key="deckvideo.video_id", index=True)
    deck_video: Optional[DeckVideo] = Relationship(back_populates="cards")
