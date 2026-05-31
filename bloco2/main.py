from fastapi import FastAPI, Request, Form, HTTPException 
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi 
# [ MEMBRO 3 - BLOCO 3 ]: Apenas para não haver confusão de nomes, a próxima linha mudou levemente. Eu explico melhor essa mudança na linha de import do SQLModel:
from requests import Session as RequestsSession
import re 
# Alguns novos imports serão necessários para implementar o Token Bucket e a Cache:
# Para a funcionalidade do Token Bucket, precisaremos de:
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from limits import parse
# Para a funcionalidade da Cache, precisaremos de:
# [ MEMBRO 3 - BLOCO 3 ]: Mudei o nome do antigo database.py para cache.py, como está comentado no próprio arquivo cache.py.
# [ MEMBRO 3 - BLOCO 3 ]: Então, note que diferente da versão antiga do projeto, agora importo as funções salvar_na_cache e carregar_da_cache do arquivo cache.py, ao invés do database.py:
from cache import salvar_na_cache, carregar_da_cache  
# [ MEMBRO 3 - BLOCO 3 ]: Para configurar o Banco de Dados e a Engine, será necessário:
from contextlib import asynccontextmanager # [ MEMBRO 3 - BLOCO 3 ]: Servirá para ligar e desligar o servidor
from sqlmodel import SQLModel, create_engine, select, Session # [ MEMBRO 3 - BLOCO 3 ]: O SQLModel também possui uma classe chamada Session, assim como requests lá em cima. Por isso, renomeei o de cima.
from models import DeckVideo, Card # [ MEMBRO 3 - BLOCO 3 ]: É no models.py que definimos os modelos de Decks e Cards, e agora vamos importar eles.
# [ MEMBRO 3 - BLOCO 3 ]: Para a manutenção das datas de revisão dos Cards, será necessário:
from datetime import datetime, timezone

# [ MEMBRO 3 - BLOCO 3 ]: Configuração do BD com SQLite:
arquivo_sqlite = "estudos.db"
url_sqlite = f"sqlite:///{arquivo_sqlite}"

# [ MEMBRO 3 - BLOCO 3 ]: Criação da Engine do BD:
engine = create_engine(url_sqlite)

def criar_db_e_tabelas():
    """Cria o arquivo estudos.db e os modelos de Decks e Cards, caso não existam ainda."""
    SQLModel.metadata.create_all(engine)
    print("O Banco de Dados contendo os modelos de Decks e Cards foi criado e está pronto para ser povoado.")

# [ MEMBRO 3 - BLOCO 3 ]: É aqui ocorre a ativação e desativação do servidor (lifespan):
@asynccontextmanager
async def initFunction(app: FastAPI):
    # [ MEMBRO 3 - BLOCO 3 ]: Executado exatamente no momento em que o servidor liga:
    criar_db_e_tabelas()
    yield
    # [ MEMBRO 3 - BLOCO 3 ]: Executado no momento em que o servidor desliga:
    print("Servidor finalizado adequadamente.")
    
# Começamos definindo o limitador:
# Ele servirá para restringir a quantidade de requisições que o usuário poderá fazer ao Youtube
limitador = Limiter(key_func=get_remote_address) # limitador por IP
# [ MEMBRO 3 - BLOCO 3 ]: Colocando o lifespan junto com o limitador:
app = FastAPI(lifespan=initFunction)
app.state.limiter = limitador

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #permitindo qualquer site
    allow_methods=["*"], #quais "verbos" HTTP o site pode acessar, nesse caso permitindo todos
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=["templates", "templates/Partials"])

# para evitar bloqueios cookie do Youtube
http_session = RequestsSession() # [ MEMBRO 3 - BLOCO 3 ]: Agora, como renomeei a classe Session do requests para RequestsSession, essa linha mudou um pouco.

# ROTAS E NAVEGAÇÃO

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "pagina":"/pagina1"
            }
        )

@app.get("/pagina1", response_class=HTMLResponse)
async def pag1(request: Request):
    if (not "HX-Request" in request.headers):
        return templates.TemplateResponse(
            request,
            "home.html",
            context={
                "pagina":"/pagina1",
            }
        )
    return templates.TemplateResponse(request, "pagina1.html")

@app.get("/legenda", response_class=HTMLResponse)
async def pagina2(request: Request):
    if (not "HX-Request" in request.headers):
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={"pagina": "/legenda"}
        )
    return templates.TemplateResponse(
            request=request, 
            name="pagina2.html", 
        ) 

@app.get("/revisao",response_class=HTMLResponse)
async def revisar(request:Request):
    if (not "HX-Request" in request.headers):
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={"pagina": "/revisao"}
        )
    return templates.TemplateResponse(
            request=request, 
            name="pagina3.html", 
        )

# ROTAS DE API E DADOS

def limpar_url_extrair_id(url: str):
    padrao = r'(?:v=|/|be/)([0-9A-Za-z_-]{11})'
    encaixou = re.search(padrao, url)
    if encaixou:
        return encaixou.group(1)
    else:
        return None

# GET para pegar as legendas, adaptado para a Cache e o Token Bucket.
# [ MEMBRO 3 - BLOCO 3 ]: E agora também adaptado para legendas automáticas e para extrair o título dos vídeos (apenas para ficar mais informativo para o usuário):

@app.get("/api/legenda")
async def obter_legenda(request: Request, url: str):
    video_id = limpar_url_extrair_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="URL do YouTube inválida.")
    
    # Aqui vem a parte mais importante: 
    # Definir quantos tokens o usuário tem, para cada certo período de tempo.
    limite = parse("5/5 minute") # Tomei a liberdade de fornecer inicialmente 5 tokens para o usuário poder gastar.
    # A cada 5 minutos, a quantidade de tokens do usuário (bucket) reseta para 5 novamente.
    # Se achar 5 minutos demais, basta trocar o segundo 5 da linha de código acima pela quantidade de minutos que desejar =)
    ip_do_usuario = get_remote_address(request)
    cache = carregar_da_cache(video_id)

    if cache:
        # Se o vídeo estiver na cache, não é necessário descontar um token, pois puxamos as legendas da memória:
        dados_do_usuario = limitador.limiter.get_window_stats(limite, ip_do_usuario, "obter_legenda")
        tokens_restantes = dados_do_usuario.remaining

        # [ MEMBRO 3 - BLOCO 3 ]:

        # Antes, a cache salvava as legendas como uma lista de frases. Agora, temos a informação sobre o tipo da legenda (manual/automática) sendo adicionada.
        # Então, para garantir que um vídeo que esteja no formato antigo dentro cache (lista de frases) seja adaptado para o novo formato (dicionário: tipo da legenda + lista de frases), será necessário:
        # Como o que está dentro da cache agora será um dicionário, basta extrair esse tipo, juntamente com as legendas:
        era_manual = cache.get("legenda_manual", True)
        legendas = cache.get("legendas", [])

        # [ MEMBRO 3 - BLOCO 3 ]: 
        # Adicionemos uma nova funcionalidade: Extrair o título do vídeo do Youtube que o usuário está estudando.
        # Assumindo que existe o título do vídeo no dicionário armazenado dentro da Cache, podemos tentar extrair ele:
        titulo_salvo = cache.get("titulo_video")

        # Quando clicamos no botão para usar esse método GET, é desejável que ele seja utilizado apenas uma vez. Mas não é isso que acontece na prática.
        # Como é possível ver no terminal quando esse código roda, o HTMX acaba fazendo requisições extras, mesmo apertando o botão uma única vez.
        # Isso pode criar um cenário de duas requisições praticamente simultâneas (condição de corrida). 
        # Dessa forma, o título pode acabar sendo lido de forma errônea.
        # Se não houver título salvo dentro da Cache, ou se esse título dummy estiver lá:
        if not titulo_salvo or titulo_salvo == "Vídeo do YouTube":
            try:
                # É possível extrair a URL limpa do vídeo (limpa no sentido de não ter marcações de tempo ou algo assim):
                url_limpa_youtube = f"https://www.youtube.com/watch?v={video_id}"
                # E então, podemos usar a URL oEmbed para tentar extrair o título. Essa URL é um formato que o Youtube disponibiliza para ter acesso aos metadados do vídeo.
                # No nosso caso, a informação de interesse é o título, e queremos que isso venha no formato JSON:
                url_oembed = f"https://www.youtube.com/oembed?url={url_limpa_youtube}&format=json"
                # E então, a requisição do Youtube para extrair os metadados:
                resposta_oembed = http_session.get(url_oembed)

                if resposta_oembed.status_code == 200:
                    # Aqui, se tudo der certo, podemos pegar o JSON que o Youtube forneceu como resposta e procurar o atributo "title", e depois guardar na Cache:
                    titulo_salvo = resposta_oembed.json().get("title", "Vídeo do YouTube")
                    cache["titulo_video"] = titulo_salvo
                    salvar_na_cache(video_id, cache)

                else:
                    titulo_salvo = "Vídeo do YouTube"

            except Exception:
                titulo_salvo = "Vídeo do YouTube"

        # [ MEMBRO 3 - BLOCO 3 ]: Com a variável era_manual, é possível lançar um aviso no Back-End para informar que as legendas do vídeo estavam na Cache, e também o tipo de sua legenda:
        if era_manual:
            tipo_legenda = "MANUAL"
        else:
            tipo_legenda = "AUTOMÁTICA - Erros de transcrição são possíveis nesse caso"

        print(f"Tipo de legenda (Cache): {tipo_legenda} | Título: {titulo_salvo}")

        # [ MEMBRO 3 - BLOCO 3 ]: Retornamos os dados da cache, o saldo de tokens, a característica da legenda, o título e um aviso que será usado no Front-End, idêntico ao do Back-End:
        return JSONResponse(content={
            "dados": legendas,
            "tokens_restantes": tokens_restantes,
            "legenda_manual": era_manual,
            "titulo_video": titulo_salvo,
            "aviso_legenda": f"Tipo de legenda (Cache): {tipo_legenda} | Título: {titulo_salvo}"
        })
    
    # Se o usuário gastar todos os seus tokens e zerar seu saldo, um JSON avisando isso é mostrado para o usuário:
    if not limitador.limiter.hit(limite, ip_do_usuario, "obter_legenda"):
        return JSONResponse(
            status_code=429,
            content={"detail": "O limite de 5 tokens foi atingido. Espere 5 minutos para ter mais 5 tokens.", "tokens_restantes": 0}
        )
    
    # Obtendo novamente o saldo de tokens do usuário:
    dados_do_usuario = limitador.limiter.get_window_stats(limite, ip_do_usuario, "obter_legenda")
    tokens_restantes = dados_do_usuario.remaining

    # Se o código chegar nas próximas linhas, é porque o vídeo é novo. Logo, 1 token deve ser cobrado do usuário.
    # Como a ID do vídeo não está na memória e usuário ainda tem tokens para gastar nesse ponto do código, aí sim uma requisição ao Youtube deve ser feita:
    try:
        youtube_api = YouTubeTranscriptApi(http_client=http_session)
        lista_de_legendas = youtube_api.list(video_id)
        # [ MEMBRO 3 - BLOCO 3 ]: Se o vídeo não estiver na Cache, começamos definindo o título dummy "Vídeo do Youtube":
        titulo_video = "Vídeo do YouTube"

        try:
            # [ MEMBRO 3 - BLOCO 3 ]: Aqui, fazemos o mesmo processo de antes para extrair o título do vídeo do Youtube:
            url_limpa_youtube = f"https://www.youtube.com/watch?v={video_id}"
            url_oembed = f"https://www.youtube.com/oembed?url={url_limpa_youtube}&format=json"
            resposta_oembed = http_session.get(url_oembed)

            if resposta_oembed.status_code == 200:
                titulo_video = resposta_oembed.json().get("title", "Vídeo do YouTube")
            else:
                print(f"oEmbed respondeu com status {resposta_oembed.status_code} para o ID {video_id}")

        except Exception as e:
            print(f"Erro ao buscar oEmbed: {e}")
            pass

        # [ MEMBRO 3 - BLOCO 3 ]:

        # Nessa etapa do projeto, é desejável que as legendas automáticas também sejam uma opção, além das manuais que já estão implementadas.
        # Porém, se a legenda extraída do vídeo for automática, um aviso no Back-End e Front-End deve ser lançado avisando que podem haver erros nela, diferente das manuais.
        # Inicialização das variáveis que serão usadas:
        legenda_objeto = None # Variável que guardará as legendas em si (sejam elas manuais ou automáticas).
        tem_legenda_manual = True # Variável que indicará se as legendas são manuais ou automáticas. Suponhamos inicialmente que um vídeo genérico possua legendas manuais.

        try:
            # Primeiro, vou tentar extrair as legendas manuais do vídeo. Se elas existirem, essa linha será suficiente para extraí-las:
            legenda_objeto = lista_de_legendas.find_manually_created_transcript(['en'])
            print(f"Tipo de legenda: MANUAL | Título: {titulo_video}")

        except Exception:

            try:
                # Se falhar, isso significa que as legendas manuais não existem. Então, como segunda opção, tentarei extrair as legendas automáticas:
                legenda_objeto = lista_de_legendas.find_generated_transcript(['en'])
                tem_legenda_manual = False # Aviso ao sistema que essa legenda não é manual.
                print(f"Tipo de legenda: AUTOMÁTICA - Erros de transcrição são possíveis nesse caso. | Título: {titulo_video}")

            except Exception:
                # Se falhar novamente, isso significa que não há legendas em inglês disponíveis para esse vídeo específico:
                raise HTTPException(status_code=404, detail="O vídeo não possui nenhuma legenda em inglês disponível")

        blocos_brutos = legenda_objeto.fetch()
        legendas_formatadas = []
        texto_anterior = ""

        for bloco in blocos_brutos:
            texto_limpo = " ".join(bloco.text.split())
            
            # Aqui, vem a parte da limpeza das legendas. Os objetivos são:
            # Limpar blocos de duração pequena demais (duração menor ou igual a 1 segundo).
            # Remover legendas repetidas.

            if texto_limpo and bloco.duration >= 1.0 and texto_limpo != texto_anterior:
                tempo_fim_calculado = bloco.start + bloco.duration
                legendas_formatadas.append({
                    "id_do_bloco": len(legendas_formatadas),
                    "texto_limpo": texto_limpo,    
                    "tempo_inicio": bloco.start,
                    "tempo_fim": tempo_fim_calculado
                })

                texto_anterior = texto_limpo

        #  [ MEMBRO 3 - BLOCO 3 ]: É necessário então sobrescrever a cache com o novo vídeo:
        # Agora, além de guardar somente as legendas_formatadas (como era na versão antiga), vou guardar também a varíavel tem_legenda_manual e o titulo_video:
        dados_para_salvar = {
            "legendas": legendas_formatadas,
            "legenda_manual": tem_legenda_manual,
            "titulo_video": titulo_video
        }

        salvar_na_cache(video_id, dados_para_salvar)

        # Para finalizar antes de retornar o JSON completo, falta apenas o texto de aviso para o Front-End, que será baseado no tipo de legenda capturado:
        if tem_legenda_manual:
            texto_aviso = f"Tipo de legenda: MANUAL | Título: {titulo_video}"
        else:
            texto_aviso = f"Tipo de legenda: AUTOMÁTICA - Erros de transcrição são possíveis nesse caso. | Título: {titulo_video}"

        # Depois, basta retornar as legendas, os tokens restantes que o usuário possui, o tipo de legenda, o título do vídeo e por fim o aviso da legenda:
        return JSONResponse(content={
            "dados": legendas_formatadas,
            "tokens_restantes": tokens_restantes,
            "legenda_manual": tem_legenda_manual,
            "titulo_video": titulo_video,
            "aviso_legenda": texto_aviso
        })

    except Exception as e:
        mensagem_de_erro = str(e)
        if "Could not retrieve a transcript" in mensagem_de_erro:
            raise HTTPException(status_code=404, detail="Vídeo sem legendas disponíveis em inglês.") #  [ MEMBRO 3 - BLOCO 3 ]:  Mensagem de erro adaptada, pois agora o projeto aceita legendas automáticas também.
        print(f"Erro técnico: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar legendas.") 

# [ MEMBRO 3 - BLOCO 3 ]: ROTAS PARA MANUTENÇÃO DOS CARDS E DECKS

# ROTA 1: Recebe os dados do bloco de legenda que o usuário desejou salvar através do clique no botão "Estudar depois", e salva ele no Banco de Dados. 

@app.post("/salvar_card")
# Aqui há a assinatura da função. Passamos todos os dados do bloco de legenda necessários para a criação do Card:
def salvar_card_bd(
    request: Request,
    video_id: str = Form(...), # Cada Deck terá o mesmo ID do vídeo que ele representa, aproveitando que o ID do Youtube já é único mesmo.            
    titulo_video: str = Form(...), # O título do Deck será o próprio título do vídeo do Youtube que ele representa.   
    texto_legenda: str = Form(...), # O conteúdo do Card propriamente dito, ou seja, um pedaço da legenda do vídeo.
    start_time: float = Form(...), # O tempo de ínicio desse bloco de legenda que será salvo.
    end_time: float = Form(...) # Analogamente, o tempo de fim.
):
    with Session(engine) as session:

        # Começamos criando uma variável que será útil para informar ao usuário a criação de Decks e Cards que está sendo feita:
        logs_para_modal = ""
        
        # Antes de lidar com o Card do bloco da legenda de um vídeo, primeiro precisamos saber se já existe um Deck (conjunto de Cards) associado a aquele vídeo:
        deck = session.get(DeckVideo, video_id)
        
        # Se não existir um Deck associado ao vídeo em questão, criamos ele usando as informações do ID e do título do vídeo:
        if not deck:
            deck = DeckVideo(video_id=video_id, titulo=titulo_video)
            session.add(deck)
            session.commit()
            session.refresh(deck)
            print(f"Novo Deck criado: {titulo_video}")
            # Mas o aviso da linha anterior só aparece no Back-End. É justamente por isso que a variável logs_para_modal será usada:
            # Ela armazenará esses prints para futuramente mostrar elas para o usuário através de um modal:
            logs_para_modal += f"Novo Deck criado: {titulo_video}\n"

        # Além disso, existe o risco do usuário clicar múltiplas vezes no botão "Salvar Card", para o mesmo pedaço de legenda. 
        # Seria bom se o sistema evitasse criar múltiplos Cards idênticos nessa situação. Para evitar isso:
        query_duplicado = select(Card).where(
            Card.video_id == video_id, 
            Card.texto_legenda == texto_legenda
        )
        card_existente = session.exec(query_duplicado).first()
        
        # Então, se acharmos um Card igual ao que o usuário tentou salvar:
        if card_existente:
            print(f"Você já salvou um Card igual nesse Deck: {texto_legenda}")
            logs_para_modal += f"Você já salvou um Card igual nesse Deck: {texto_legenda}"
            return JSONResponse(
                status_code=200, 
                content={
                    "status": "duplicado",
                    "mensagem": "Este card já foi salvo anteriormente.",
                    "texto": logs_para_modal
                 }
            )
 
        # A essa altura, o Deck do vídeo em questão com certeza existe. Logo, podemos salvar o Card, que será associado ao Deck pela propriedade video_id:
        novo_card = Card(
            texto_legenda=texto_legenda,
            start_time=start_time,
            end_time=end_time,
            video_id=video_id 
        )
        session.add(novo_card)
        session.commit()
        print(f"Novo Card salvo: {texto_legenda}")
        logs_para_modal += f"Novo Card salvo: {texto_legenda}"
        
        return JSONResponse(
            status_code=200, 
            content={
                "status": "sucesso",
                "mensagem": "Card salvo com sucesso.",
                "texto": logs_para_modal
                  }
        )

# ROTA 2: Fornece para o usuário todos os Cards que ele precisa revisar no dia que ele clicar no botão "Revisão diária":

@app.get("/api/revisao_diaria")
def listar_cards_hoje():
    # Tudo começa obtendo o momento de agora:
    agora = datetime.now(timezone.utc)
    
    with Session(engine) as session:
        # E então, vamos usar uma query para selecionar todos os Cards cujo momento de revisão é agora, ou se o momento de revisão já passou:
        query = select(Card).where(Card.data_proxima_revisao <= agora)
        cards_hoje = session.exec(query).all()
        
        # Se a lista estiver vazia, isso significa que não há Cards para o usuário revisar hoje:
        if not cards_hoje:
            print("Nenhum card para revisar hoje.")
            return JSONResponse(content={"status": "sucesso", "mensagem": "Nenhum card para revisar hoje.", "Quantidade": 0})
        
        # Se houver Cards para revisar:
        print("\n=== Cards para revisar hoje ===")
        for card in cards_hoje:
            # Podemos extrair o título do vídeo do Deck daqueles Cards:
            titulo_video = card.deck_video.titulo if card.deck_video else "Vídeo Desconhecido"
            
            print(f"Deck do Card: {titulo_video}")
            print(f"Card: {card.texto_legenda}")
            print("-" * 30)
        print("===============================\n")
        
        # Retorna a resposta para o JavaScript saber que deu tudo certo:
        return JSONResponse(content={"status": "sucesso", "quantidade": len(cards_hoje)})

# ROTA 3: Serve para checar se um certo Card já foi salvo num Deck específico. Isso será útil para saber quando é possível deletar um Card ou não (mais sobre isso no integracao.js):

@app.get("/api/checar_card")
async def checar_card(video_id: str, texto_legenda: str):
    try:
        # Abrindo a sessão:
        with Session(engine) as session:
            # Usamos a mesma query para detectar cards duplicados:
            query_busca = select(Card).where(
                Card.video_id == video_id, 
                Card.texto_legenda == texto_legenda
            )
            card_existente = session.exec(query_busca).first()
            
            # Se encontrarmos, o Card existe. Se não, não existe.
            existe_no_banco = card_existente is not None
            
            return JSONResponse(content={"existe": existe_no_banco})
            
    except Exception as e:
        print(f"Erro técnico ao checar card no banco: {e}")
        # Se algo der errado na conexão, retornamos False por segurança para não travar o app:
        return JSONResponse(content={"existe": False})

# ROTA 4: Exclusão definitiva de um Card específico do banco de dados via SQLModel:

@app.post("/api/deletar_card")
async def deletar_card(video_id: str = Form(...), texto_legenda: str = Form(...)):
    try:
        # Abrindo a sessão com o BD:
        with Session(engine) as session:
            
            # É possível usar uma query para achar o card exato que bate com o ID do vídeo e o texto da legenda:
            query_busca = select(Card).where(
                Card.video_id == video_id, 
                Card.texto_legenda == texto_legenda
            )
            card_para_deletar = session.exec(query_busca).first()
            
            # 3. Se o card for encontrado, realizamos a deleção:
            if card_para_deletar:
                session.delete(card_para_deletar)
                session.commit() 
                
                print(f"Card deletado com sucesso: {texto_legenda}")
                
                return JSONResponse(
                    status_code=200, 
                    content={"status": "sucesso", "mensagem": "Card removido do banco de dados."}
                )

            else:
                # Caso o card não seja encontrado:
                print(f"Aviso: Tentativa de deletar card inexistente.")
                return JSONResponse(
                    status_code=404, 
                    content={"status": "aviso", "mensagem": "Card não encontrado para deleção."}
                )
            
    except Exception as e:
        print(f"Erro técnico ao deletar card no SQLite: {e}")
        return JSONResponse(
            status_code=500, 
            content={"status": "erro", "mensagem": f"Erro interno: {str(e)}"}
        )

# ROTA 5: Checar se o Deck do vídeo existe:
@app.get("/api/checar_deck")
async def checar_deck(video_id: str):
    try:
        with Session(engine) as session:
            deck = session.get(DeckVideo, video_id)
            return JSONResponse(content={"existe": deck is not None})
    except Exception as e:
        return JSONResponse(content={"existe": False})

# ROTA 6: Deletar o Deck e todos os Cards associados em cascata (ou seja, deletar o Deck significa deletar todos os Cards dele também):
@app.post("/api/deletar_deck")
async def deletar_deck(video_id: str = Form(...)):
    try:
        with Session(engine) as session:
            deck = session.get(DeckVideo, video_id)
            if deck:
                session.delete(deck) # O SQLModel cuida do delete em cascata dos cards
                session.commit()
                print(f"Deck deletado em cascata: ID - {video_id}")
                return JSONResponse(content={"status": "sucesso", "mensagem": "Deck e cards associados foram deletados."})
            return JSONResponse(status_code=404, content={"status": "erro", "mensagem": "Deck não encontrado."})
    except Exception as e:
        print(f"Erro ao deletar deck: {e}")
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})
