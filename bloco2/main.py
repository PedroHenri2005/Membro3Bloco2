from fastapi import FastAPI, Request, Form, HTTPException 
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi 
# [ MEMBRO 3 - BLOCO 3]: Apenas para não haver confusão de nomes, a próxima linha mudou levemente:
from requests import Session as RequestsSession
import re 
# Alguns novos imports serão necessários para implementar o Token Bucket e a Cache:
# Para a funcionalidade do Token Bucket, precisaremos de:
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from limits import parse
# Para a funcionalidade da Cache, precisaremos de:
# [ MEMBRO 3 - BLOCO 3]: Mudei o nome do antigo database.py para cache.py:
from cache import salvar_na_cache, carregar_da_cache  
# Para configurar o banco de dados e a Engine, será necessário:
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, create_engine, select, Session
from models import DeckVideo, Card
# Para a manutenção das datas de revisão dos Cards, será necessário:
from datetime import datetime, timezone

# Configuração do Banco de Dados SQLite
arquivo_sqlite = "estudos.db"
url_sqlite = f"sqlite:///{arquivo_sqlite}"

# Criação da Engine do BD:
engine = create_engine(url_sqlite)

def criar_db_e_tabelas():
    """Cria o arquivo estudos.db e as tabelas caso não existam."""
    SQLModel.metadata.create_all(engine)
    print("O Banco de Dados contendo os modelos de Decks e Cards foi criado e está pronto para ser povoado.")

@asynccontextmanager
async def initFunction(app: FastAPI):
    # Executado exatamente no momento em que o servidor liga:
    criar_db_e_tabelas()
    yield
    # Executado no momento em que o servidor desliga:
    print("Servidor finalizado adequadamente.")
    
# Começamos definindo o limitador:
# Ele servirá para restringir a quantidade de requisições que o usuário poderá fazer ao Youtube
limitador = Limiter(key_func=get_remote_address) # limitador por IP

# AJUSTE: Colocando o lifespan junto com o limitador:
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
http_session = RequestsSession()

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
# [ MEMBRO 3 - BLOCO 3 ] E agora também adaptado para legendas automáticas e para extrair o título dos vídeos (apenas para ficar mais informativo para o usuário):

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

        # [ MEMBRO 3 - BLOCO 3]: 
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
                    # Aqui, se tudo der certo, podemos extrair pegar o JSON que o Youtube forneceu como resposta e procurar o atributo "title", e depois guardar na Cache:
                    titulo_salvo = resposta_oembed.json().get("title", "Vídeo do YouTube")
                    cache["titulo_video"] = titulo_salvo
                    salvar_na_cache(video_id, cache)

                else:
                    titulo_salvo = "Vídeo do YouTube"

            except Exception:
                titulo_salvo = "Vídeo do YouTube"

        # Com a variável era_manual, é possível lançar um aviso no Back-End para informar que as legendas do vídeo estavam na Cache, e também o tipo de sua legenda:
        if era_manual:
            tipo_legenda = "MANUAL"
        else:
            tipo_legenda = "AUTOMÁTICA - Erros de transcrição são possíveis nesse caso"

        print(f"Tipo de legenda (Cache): {tipo_legenda} | Título: {titulo_salvo}")

        # Retornamos os dados da cache, o saldo de tokens, a característica da legenda e o título:
        return JSONResponse(content={
            "dados": legendas,
            "tokens_restantes": tokens_restantes,
            "legenda_manual": era_manual,
            "titulo_video": titulo_salvo
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
        # Porém, se a legenda extraída do vídeo for automática, um aviso no Back-End deve ser lançado avisando que podem haver erros nela, diferente das manuais.
        # Inicialização das variáveis que serão usadas:
        legenda_objeto = None # Variável que guardará as legendas em si (sejam elas manuais ou automáticas)
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

        # É necessário então sobrescrever a cache com o novo vídeo:
        # Agora, além de guardar as legendas_formatadas, vou guardar também a varíavel tem_legenda_manual:
        dados_para_salvar = {
            "legendas": legendas_formatadas,
            "legenda_manual": tem_legenda_manual,
            "titulo_video": titulo_video
        }

        salvar_na_cache(video_id, dados_para_salvar)

        # Depois, basta retornar as legendas, juntamente com os tokens restantes que o usuário possui, e a característica da legenda:
        return JSONResponse(content={
            "dados": legendas_formatadas,
            "tokens_restantes": tokens_restantes,
            "legenda_manual": tem_legenda_manual,
            "titulo_video": titulo_video
        })

    except Exception as e:
        mensagem_de_erro = str(e)
        if "Could not retrieve a transcript" in mensagem_de_erro:
            raise HTTPException(status_code=404, detail="Vídeo sem legendas disponíveis em inglês.") # Mensagem de erro adaptada, pois agora o projeto aceita legendas automáticas também.
        
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
        
        # Antes de lidar com o Card do bloco da legenda de um vídeo, primeiro precisamos saber se já existe um Deck (conjunto de Cards) associado a aquele vídeo:
        deck = session.get(DeckVideo, video_id)
        
        # Se não existir um Deck associado ao vídeo em questão, criamos ele usando as informações do ID e do título do vídeo:
        if not deck:
            deck = DeckVideo(video_id=video_id, titulo=titulo_video)
            session.add(deck)
            session.commit()
            session.refresh(deck)
            print(f"Novo Deck criado para o vídeo com o seguinte título: {titulo_video}")

        # Além disso, existe o risco do usuário clicar múltiplas vezes no botão "Salvar Card", para o mesmo pedaço de legenda. 
        # Seria bom se o sistema evitasse criar múltiplos Cards idênticos nessa situação. Para evitar isso:
        query_duplicado = select(Card).where(
            Card.video_id == video_id, 
            Card.texto_legenda == texto_legenda
        )
        card_existente = session.exec(query_duplicado).first()
        
        # Então, se acharmos um Card igual ao que o usuário tentou salvar:
        if card_existente:
            print(f"Você já salvou um Card com essa frase nesse Deck: {texto_legenda}")
            return JSONResponse(
                status_code=200, 
                content={"status": "duplicado", "mensagem": "Este card já foi salvo anteriormente."}
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
        
        return JSONResponse(
            status_code=200, 
            content={"status": "sucesso", "mensagem": "Card salvo com sucesso."}
        )

# ROTA 2: Fornece para o usuário todos os Cards que ele precisa revisar no dia que ele clicar no botão "Revisão do dia".

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
            print("Nenhum card para revisar hoje.\n")
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
        
        # Retorna a resposta para o JavaScript saber que deu tudo certo
        return JSONResponse(content={"status": "sucesso", "quantidade": len(cards_hoje)})
