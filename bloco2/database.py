# Aqui, vamos criar o banco de dados responsável pela memória (Cache).
# A ideia é sempre guardar as legendas do último vídeo que o usuário requeriu. 
# Se ele pedir o mesmo vídeo novamente, basta entregar as legendas presentes na Cache.
from pydantic import BaseModel
from typing import List
import json
import os

# Cada bloco de legenda tem os seguintes atributos:
class BlocoLegenda(BaseModel):
    id_do_bloco: int
    texto_limpo: str
    tempo_inicio: float
    tempo_fim: float

# [ MEMBRO 3 - BLOCO 3]:
# Aqui, terá uma nova classe que servirá exclusivamente para juntar as informações: tipo de legenda (manual/automática) + blocos de legenda.
class LegendasCompletas(BaseModel):
    legenda_manual: bool
    legendas: List[BlocoLegenda]
    
# O último vídeo que o usuário carregou tem sua respectiva ID, e as legendas do vídeo propriamente ditas:
class UltimoVideo(BaseModel):
    video_id: str
    dados: LegendasCompletas

# O arquivo que guardará as legendas do último vídeo:
ARQUIVO_CACHE = "ultimo_video.json"

# Aqui, vem a função que serve para salvar as legendas de um certo vídeo na memória criada:
def salvar_na_cache(video_id: str, dados_para_salvar: dict): # Adapatando os dados para um dicionário ao invés de lista
    """ Valida as legendas do último vídeo e salva elas, sobrescrevendo as anteriores, caso existirem. """
    try:
        objeto_ultimo_video = UltimoVideo(video_id=video_id, dados=dados_para_salvar)
        with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
            f.write(objeto_ultimo_video.model_dump_json(indent=4))
        print(f"O vídeo que possui a respectiva ID: ({video_id}) foi salvo na Cache.")
    except Exception as e:
        print(f"Erro ao salvar na Cache: {e}")

# E aqui a função que verifica se o novo vídeo carregado é o mesmo que o anterior. Se for, basta retornar as legendas da Cache:
def carregar_da_cache(video_id: str):
    """ Verificando se o vídeo requerido já é o que tem legendas salvas na Cache. Se for, pegamos as legendas dela, ao invés do Youtube. """
    if not os.path.exists(ARQUIVO_CACHE):
        return None
    try:
        with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
            conteudo = json.load(f)
            if conteudo["video_id"] == video_id:
                print(f"As legendas do vídeo de ID: ({video_id}) foram encontradas na Cache.\nEntão, nenhuma requisição ao Youtube foi necessária agora.")
                return conteudo["dados"]
            else:
                print(f"As legendas do vídeo de ID: ({video_id}) requeridas não estão na Cache.\nA requisição ao Youtube então será providenciada.")
    except Exception as e:
        print(f"Erro ao ler arquivo da Cache: {e}")
        return None
    return None
