// [MANTIDO]: Variáveis de estado para controlar as frases.
let blocosDeEstudo = [];  // guarda o JSON com as frases 
let blocoAtualIndex = 0;  // qual frase o usuário está no momento

// INICIAR SESSÃO
async function iniciarSessao(youtubeLink) {
    try {
        // [MANTIDO]: Controle da tela de carregamento.
        let carregamento = document.getElementById('carregamento')
        carregamento.style.display = "flex";

        const legendaDiv = document.getElementById('legenda');
        const resposta = await fetch(`/api/legenda?url=${encodeURIComponent(youtubeLink)}`);
        
        carregamento.style.display = "none";

        const jsonResponse = await resposta.json(); 
        
        if (!resposta.ok) { 
            // [MANTIDO]: Tratamento de limite de tokens retornado pela API.
            if (jsonResponse.tokens_restantes !== undefined) {
                atualizarInterfaceTokens(jsonResponse.tokens_restantes);
            }
            // NOVO (BLOCO 3):
            // Na versão anterior do projeto, tinham essas linhas exatamente no lugar desse comentário: 
            // const erroData = await resposta.json(); 
            // throw new Error(erroData.detail || "Erro ao carregar legenda. Verifique se o vídeo possui legendas manuais em inglês.");
            // Mas isso estava gerando um erro na hora de imprimir a mensagem para avisar que os tokens zeraram para o usuário, pois o json estava sendo obtido duas vezes por causa da variável erroData.
            // Por isso, removi essa leitura duplicada e agora a mensagem de limite de tokens atigindo aparece normalmente para o usuário, usando a linha abaixo:
            throw new Error(jsonResponse.detail || "Erro ao carregar legenda.");
        }

        // [NOVO]: ATENÇÃO AQUI! A estrutura do JSON mudou. 
        // Antes era a lista direta, agora encapsulamos os dados dentro de 'jsonResponse.dados' 
        // para trafegar os tokens_restantes na mesma requisição com mais segurança.
        blocosDeEstudo = jsonResponse.dados;
        
        atualizarInterfaceTokens(jsonResponse.tokens_restantes);
        
        blocoAtualIndex = 0;
        currentVideoId = extractVideoId(youtubeLink); 
        
        carregarFraseAtual();
        loadVideo(currentVideoId);

    } catch (erro) {
        // [NOVO]: Integração com o novo Modal de erro.
        const erroModal = document.getElementById('erroModal');
        const erroText = document.getElementById('erro');
        if(erroModal) {
            erroText.innerText = erro.message;
            erroModal.style.display = "block";
        }
        console.error("Falha na integração:", erro);
    }
}

// [MANTIDO]: Função gerenciar tokens.
function atualizarInterfaceTokens(valor) {
    localStorage.setItem('tokens_restantes', valor);
    const el = document.getElementById('token-count');
    if (el) {
        el.innerText = valor;
        if (parseInt(valor) === 0) {
            el.classList.add('token-low'); 
        } else {
            el.classList.remove('token-low');
        }
    }
}

// TELA E VÍDEO
function carregarFraseAtual() {
    if (!blocosDeEstudo || blocosDeEstudo.length === 0) return;

    const bloco = blocosDeEstudo[blocoAtualIndex];
    const legendaDiv = document.getElementById('legenda');
    if (legendaDiv) legendaDiv.innerText = bloco.texto_limpo;

    startTime = bloco.tempo_inicio; 
    endTime = bloco.tempo_fim; 

    // [NOVO]: Em vez de esconder o painel INTEIRO (o que sumia com o microfone),
    // agora escondemos apenas a onda (canvas) e o texto (transcript). 
    // Assim o botão vermelho do microfone fica sempre visível e fixo na tela.
    const wave = document.getElementById("wave");
    const transcript = document.getElementById("transcript");
    
    if (wave) wave.style.display = "none";
    if (transcript) {
        transcript.style.display = "none";
        transcript.innerText = "Fale algo...";
    }
    
    // [MANTIDO]: Loop da frase.
    if (player && typeof player.seekTo === 'function') {
        player.seekTo(startTime, true);
        player.playVideo();
        startLoop();
    }
}

// BOTÕES
document.addEventListener('click', function(event) {
    // [NOVO]: O botão de erro agora apenas fecha o modal.
    if(event.target.id === 'botaoErro'){
        document.getElementById('erroModal').style.display = "none";
    }

    // [MANTIDO]: Navegação entre frases.
    if (event.target.id === 'protecaoButton') {
        document.getElementById('protecaoPlayer').style.display = "none";
        blocoAtualIndex++;
        carregarFraseAtual();
    }
    if (event.target.id === 'proximo') {
        if (blocoAtualIndex < blocosDeEstudo.length - 1) {
            blocoAtualIndex++;
            carregarFraseAtual();
        }
    }
    if (event.target.id === 'anterior') {
        if (blocoAtualIndex > 0) {
            blocoAtualIndex--;
            carregarFraseAtual();
        }
    }
});

// [NOVO]: FUNÇÃO DE CHECAGEM (PÁGINA 1) - TRATAMENTO DE ERROS PARA USUÁRIO
// Antigamente o HTMX trocava para a página 2 logo no clique. Se a API desse erro, 
// o usuário ficava preso numa página 2 quebrada. 
// Agora, esta função intercepta o formulário, checa a API primeiro e SÓ permite o HTMX
// avançar se o vídeo realmente tiver legenda e o usuário tiver tokens.
async function verificarVideo(event) {
    event.preventDefault(); 
    
    const input = document.querySelector('.url-input');
    const link = input ? input.value : null;
    if(!link) return;

    const btnLoad = document.querySelector('.btn-load');
    const textoOriginal = btnLoad.innerText;
    btnLoad.innerText = "VERIFICANDO...";
    btnLoad.disabled = true;

    try {
        const resposta = await fetch(`/api/legenda?url=${encodeURIComponent(link)}`);
        const jsonResponse = await resposta.json();

        if (!resposta.ok) {
            if (jsonResponse.tokens_restantes !== undefined) {
                atualizarInterfaceTokens(jsonResponse.tokens_restantes);
            }
            throw new Error(jsonResponse.detail || "Erro desconhecido ao carregar legenda.");
        }

        // Dispara o HTMX manualmente via JS para mudar de tela.
        htmx.ajax('GET', `/legenda?link=${encodeURIComponent(link)}`, {target: 'main'}).then(() => {
            window.history.pushState(null, '', `/legenda?link=${encodeURIComponent(link)}`);
        });

    } catch (erro) {
        // Exibe o erro na própria Página 1.
        const erroModal = document.getElementById('erroModal');
        const erroText = document.getElementById('erro');
        if (erroModal && erroText) {
            erroText.innerText = erro.message;
            erroModal.style.display = "block";
        }
    } finally {
        if (btnLoad) {
            btnLoad.innerText = textoOriginal;
            btnLoad.disabled = false;
        }
    }
}
