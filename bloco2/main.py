from fastapi import FastAPI, Request, Form, HTTPException 
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi 
from requests import Session
import re 
# Alguns novos imports serão necessários para implementar o Token Bucket e a Cache:
# Para a funcionalidade do Token Bucket, precisaremos de:
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from limits import parse
# Para a funcionalidade da Cache, precisaremos de:
from database import salvar_na_cache, carregar_da_cache


# Começamos definindo o limitador:
# Ele servirá para restringir a quantidade de requisições que o usuário poderá fazer ao Youtube
limitador = Limiter(key_func=get_remote_address) # limitador por IP
app = FastAPI()
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
session = Session()

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

# GET para pegar as legendas, adaptado para a Cache e o Token Bucket:

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

        # NOVO (BLOCO 3):

        # Antes, a cache salvava as legendas como uma lista de frases. Agora, temos a informação sobre o tipo da legenda (manual/automática) sendo adicionada.
        # Então, para garantir que um vídeo que esteja no formato antigo dentro cache (lista de frases) seja adaptado para o novo formato (dicionário: tipo da legenda + lista de frases), será necessário:
        if isinstance(cache, dict):
            # Se o que estiver dentro da cache for um dicionário, então já está no formato novo. Logo, basta extrair esse tipo:
            era_manual = cache.get("legenda_manual", True)
            legendas = cache.get("legendas", cache)
        else:
            # Se a cache for do formato antigo (lista de frases):
            era_manual = True
            legendas = cache

        # Com a variável era_manual, é possível lançar um aviso no Back-End para informar que as legendas do vídeo estavam na Cache, e também o tipo de sua legenda:
        if era_manual:
            tipo_legenda = "MANUAL"
        else:
            tipo_legenda = "AUTOMÁTICA - Erros de transcrição são possíveis nesse caso"

        print(f"Tipo de legenda: {tipo_legenda}")

        # Retornamos os dados da cache, o saldo de tokens e a característica da legenda:
        return JSONResponse(content={
            "dados": legendas,
            "tokens_restantes": tokens_restantes,
            "legenda_manual": era_manual
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
        youtube_api = YouTubeTranscriptApi(http_client=session)
        lista_de_legendas = youtube_api.list(video_id)

        # NOVO (BLOCO 3):  

        # Nessa etapa do projeto, é desejável que as legendas automáticas também sejam uma opção, além das manuais que já estão implementadas.
        # Porém, se a legenda extraída do vídeo for automática, um aviso no Back-End deve ser lançado avisando que podem haver erros nela, diferente das manuais.
        # Inicialização das variáveis que serão usadas:
        legenda_objeto = None # Variável que guardará as legendas em si (sejam elas manuais ou automáticas)
        tem_legenda_manual = True # Variável que indicará se as legendas são manuais ou automáticas. Suponhamos inicialmente que um vídeo genérico possua legendas manuais.

        try:
            # Primeiro, vou tentar extrair as legendas manuais do vídeo. Se elas existirem, essa linha será suficiente para extraí-las:
            legenda_objeto = lista_de_legendas.find_manually_created_transcript(['en'])
            print(f"Tipo de legenda: MANUAL")

        except Exception:

            try:
                # Se falhar, isso significa que as legendas manuais não existem. Então, como segunda opção, tentarei extrair as legendas automáticas:
                legenda_objeto = lista_de_legendas.find_generated_transcript(['en'])
                tem_legenda_manual = False # Aviso ao sistema que essa legenda não é manual.
                print(f"Tipo de legenda: AUTOMÁTICA - Erros de transcrição são possíveis nesse caso")

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
        # NOVO (BLOCO 3):
        # Agora, além de guardar as legendas_formatadas, vou guardar também a varíavel tem_legenda_manual:
        dados_para_salvar = {
            "legendas": legendas_formatadas,
            "legenda_manual": tem_legenda_manual
        }

        salvar_na_cache(video_id, dados_para_salvar)

        # Depois, basta retornar as legendas, juntamente com os tokens restantes que o usuário possui, e a característica da legenda:
        return JSONResponse(content={
            "dados": legendas_formatadas,
            "tokens_restantes": tokens_restantes,
            "legenda_manual": tem_legenda_manual
        })

    except Exception as e:
        mensagem_de_erro = str(e)
        if "No transcript found" in mensagem_de_erro or "Could not find" in mensagem_de_erro:
            raise HTTPException(status_code=404, detail="Vídeo sem legendas disponíveis em inglês.")
        
        print(f"Erro técnico: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar legendas.")
