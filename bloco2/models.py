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
    
    video_id: str = Field(foreign_key="deckvideo.video_id", index=True)
    deck_video: Optional[DeckVideo] = Relationship(back_populates="cards")
