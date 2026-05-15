
let blocosDeEstudo = [];  // guarda o JSON com as frases 
let blocoAtualIndex = 0;  // qual frase o usuário está no momento

//  INICIAR SESSÃO

async function iniciarSessao(youtubeLink) {
    try {
        const legendaDiv = document.getElementById('legenda');
        if (legendaDiv) legendaDiv.innerText = "Carregando legendas...";

        const resposta = await fetch(`/api/legenda?url=${encodeURIComponent(youtubeLink)}`);
        const jsonResponse = await resposta.json(); // Aqui recebemos o objeto completo

        if (!resposta.ok) {
            // Se der erro (como o 429), tentamos atualizar os tokens se o servidor enviou
            if (jsonResponse.tokens_restantes !== undefined) {
                atualizarInterfaceTokens(jsonResponse.tokens_restantes);
            }
            throw new Error(jsonResponse.detail || "Erro ao carregar.");
        }

        // ATENÇÃO AQUI
        // Antigamente 'jsonResponse' era a lista direta. 
        // Agora a lista está em 'jsonResponse.dados'
        blocosDeEstudo = jsonResponse.dados;
        
        // Atualizamos o contador na tela
        atualizarInterfaceTokens(jsonResponse.tokens_restantes);
        
        blocoAtualIndex = 0;
        currentVideoId = extractVideoId(youtubeLink); 
        
        carregarFraseAtual();
        loadVideo(currentVideoId);

    } catch (erro) {
        const legendaDiv = document.getElementById('legenda');
        if (legendaDiv) legendaDiv.innerText = erro.message;
    }
}

// Função auxiliar para atualizar os tokens
function atualizarInterfaceTokens(valor) {
    // Salva na memória do navegador para a Home consultar depois
    localStorage.setItem('tokens_restantes', valor);

    // Atualiza o elemento visual se ele existir na página atual
    const el = document.getElementById('token-count');
    if (el) {
        el.innerText = valor;
        
        // Troca a cor se chegar a zero
        if (parseInt(valor) === 0) {
            el.classList.add('token-low'); // Usando a classe CSS que sugerimos antes
        } else {
            el.classList.remove('token-low');
        }
    }
}

//  TELA E VÍDEO
function carregarFraseAtual() {
    // PRECISA TEM DADO AQUI se nao não faz nada
    if (!blocosDeEstudo || blocosDeEstudo.length === 0) return;

    // Pega o bloco
    const bloco = blocosDeEstudo[blocoAtualIndex];

    // Atualiza o texto legenda
    const legendaDiv = document.getElementById('legenda');
    if (legendaDiv) legendaDiv.innerText = bloco.texto_limpo;

    // Atualiza os tempos de corte para o looping
    startTime = bloco.tempo_inicio; //esta em voice.js
    endTime = bloco.tempo_fim; //esta em voice.js

    // Reseta gravação
    const panel = document.getElementById("panel");
    const transcript = document.getElementById("transcript");
    if (panel) panel.classList.add("hidden");
    if (transcript) transcript.innerText = "Fale algo...";

    // looping das partes
    if (player && typeof player.seekTo === 'function') {
        player.seekTo(startTime, true);
        player.playVideo();
        startLoop();
    }
}

// BOTÕES
document.addEventListener('click', function(event) {
    
    // Próxima Frase
    if (event.target.id === 'proximo') {
        if (blocoAtualIndex < blocosDeEstudo.length - 1) {
            blocoAtualIndex++;
            carregarFraseAtual();
        }
    }
    
    //Frase Anterior
    if (event.target.id === 'anterior') {
        if (blocoAtualIndex > 0) {
            blocoAtualIndex--;
            carregarFraseAtual();
        }
    }
    //salvar pro anki vai ficar aqui 
});