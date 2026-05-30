# [ MEMBRO 3 - BLOCO 3]
# Aqui é onde ficarão as classes que serão usadas para salvar os Flashcards de revisão, e organizá-los em Decks.
from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel

class DeckVideo(SQLModel, table=True):
    """Agrupa os cards gerados por um vídeo do YouTube em um único Deck."""
    video_id: str = Field(primary_key=True, index=True)
    titulo: Optional[str] = None
    
    cards: List["Card"] = Relationship(back_populates="deck_video")

class Card(SQLModel, table=True):
    """Modelo dos flashcards salvos para revisão espaçada."""
    id: Optional[int] = Field(default=None, primary_key=True)
    texto_legenda: str = Field(min_length=1)
    start_time: float
    end_time: float
    data_criacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_proxima_revisao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Adicionei também algumas outras propriedades que podem ser úteis no futuro:
    
    # Histórico de acertos seguidos (essencial para resetar ou avançar o Card):
    revisoes_consecutivas: int = Field(default=0)
    # Intervalo atual do card em dias (começa em 0 para revisão no mesmo dia):
    intervalo_dias: int = Field(default=0)
    # Fator de facilidade:
    fator_facilidade: float = Field(default=2.5)

    video_id: str = Field(foreign_key="deckvideo.video_id", index=True)
    deck_video: Optional[DeckVideo] = Relationship(back_populates="cards")
