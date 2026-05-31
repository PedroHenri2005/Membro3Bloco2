// [MANTIDO]: Variáveis de estado para controlar as frases.
let blocosDeEstudo = [];  // guarda o JSON com as frases 
let blocoAtualIndex = 0;  // qual frase o usuário está no momento
// [ MEMBRO 3 - BLOCO 3 ]: Algumas variáveis novas serão úteis aqui: 
currentVideoTitle = "Vídeo do Youtube"; // O título do vídeo do Youtube. Por padrão, deixarei ela inicialmente como essa string.
currentVideoId = ""; // O ID do vídeo.
startTime = 0; // O tempo de início da legenda.
endTime = 0; // O tempo de fim da legenda.

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
            // [ MEMBRO 3 - BLOCO 3]:
            // Na versão anterior do projeto, tinham essas linhas exatamente no lugar desse comentário: 
            // const erroData = await resposta.json(); 
            // throw new Error(erroData.detail || "Erro ao carregar legenda. Verifique se o vídeo possui legendas manuais em inglês.");
            // Mas isso estava gerando um erro na hora de imprimir a mensagem para avisar que os tokens zeraram para o usuário, pois o JSON estava sendo obtido duas vezes por causa da variável erroData.
            // Por isso, removi essa leitura duplicada e agora a mensagem de limite de tokens atigindo aparece normalmente para o usuário, usando a linha abaixo:
            throw new Error(jsonResponse.detail || "Erro ao carregar legenda.");
        }

        // [NOVO]: ATENÇÃO AQUI! A estrutura do JSON mudou. 
        // Antes era a lista direta, agora encapsulamos os dados dentro de 'jsonResponse.dados' 
        // para trafegar os tokens_restantes na mesma requisição com mais segurança.
        blocosDeEstudo = jsonResponse.dados;
        // [ MEMBRO 3 - BLOCO 3]: Agora, o título do Youtube é extraído:
        currentVideoTitle = jsonResponse.titulo_video;
        
        atualizarInterfaceTokens(jsonResponse.tokens_restantes);
        
        blocoAtualIndex = 0;
        currentVideoId = extractVideoId(youtubeLink); 
        
        carregarFraseAtual();
        loadVideo(currentVideoId);

        // [ MEMBRO 3 - BLOCO 3 ]: Tenho que começar checando se o vídeo já possui um Deck associado no Banco de Dados.
        // Faço isso pois se o vídeo não o possuir, não faz sentido mostrar o botão Deletar Deck pro usuário. 
        // Só mostro esse botão se existir o Deck:
        const btnDeletarDeck = document.getElementById('deletardeck');
        if (btnDeletarDeck && currentVideoId) {
            fetch(`/api/checar_deck?video_id=${currentVideoId}`)
                .then(res => res.json())
                .then(dadosDeck => {
                    if (dadosDeck.existe) {
                        btnDeletarDeck.style.display = "block"; // Se o Deck existe, o botão aparece pro usuário.
                    } else {
                        btnDeletarDeck.style.display = "none"; // Se o Deck não existe, o botão não deve aparecer.
                    }
                })
                .catch(erro => console.error("Erro ao checar existência do Deck:", erro));
        }

        // [ MEMBRO 3 - BLOCO 3]: Aqui vem a lógica para disparar o aviso para o usuário a respeito do tipo da legenda:
        // Usando o texto vindo diretamente do atributo "aviso_legenda" criado no main.py:
        // Aqui, reaproveitei o estilo e o texto do outro modal que eu já havia feito, sobre salvamento de Decks e Cards:
        const modalSucesso = document.getElementById('modalSucessoCard');
        const textoLogs = document.getElementById('textologs');

        if (modalSucesso && textoLogs && jsonResponse.aviso_legenda) {
            // Aqui, converto quebras de linha brutas do Python (\n) em quebras de linha HTML (<br>)
            textoLogs.innerHTML = jsonResponse.aviso_legenda.replace(/\n/g, '<br>');

            // Posso também marcar o modal, indicando que ele é apenas um aviso inicial indicando o tipo da legenda (manual/automática):
            modalSucesso.dataset.tipoModal = "aviso_inicial"
    
            // Abre o modal na tela para o usuário ver as especificações do vídeo:
            modalSucesso.style.display = "block";
        }

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
function carregarFraseAtual(iniciarAutoplay = true) { // [ MEMBRO 3 - BLOCO 3]: Agora, essa função tem um atributo opcional iniciarAutoplay (por padrão será true), para regular quando o vídeo deve tocar ou não:
    if (!blocosDeEstudo || blocosDeEstudo.length === 0) return;

    const bloco = blocosDeEstudo[blocoAtualIndex];
    const legendaDiv = document.getElementById('legenda');
    if (legendaDiv) legendaDiv.innerText = bloco.texto_limpo;

    // [ MEMBRO 3 - BLOCO 3 ]: Vamos adicionar a lógica dos botões Estudar Depois e Deletar Card:
    const btnEstudarDepois = document.getElementById('estudardepois');
    const btnDeletarCard = document.getElementById('deletarcard');

    // A lógica é a seguinte, só há 2 cenários possíveis:
    // [ CASO 1 ]: 
    // Se o Card daquele determinado bloco de legenda não existe no BD, isso significa que o usuário não o salvou.
    // Então, o botão que deve aparecer para o usuário é o Estudar Depois, para permitir o salvamento desse Card caso o usuário queira em algum momento.
    // [ CASO 2 ]: 
    // Contudo, também pode ser que o Card esteja salvo no BD (isto é, pode ser que em algum momento anterior o usuário já tenha salvado esse Card usando o botão Estudar Depois).
    // Nesse caso, o botão que deve aparecer é o Deletar Card.

    if (btnEstudarDepois && btnDeletarCard) {
        const parametros = new URLSearchParams({
            video_id: currentVideoId,
            texto_legenda: bloco.texto_limpo
        });

        // Verificamos usando a ROTA 3 do main.py a existência do Card:
        fetch(`/api/checar_card?${parametros.toString()}`)
            .then(resposta => resposta.json())
            .then(dados => {
                // Quando o BD responder, aplicamos a lógica que descrevi anteriormente:
                // [ CASO 1 ] - Se o Card já existe no BD:
                if (dados.existe) {
                    btnEstudarDepois.style.display = "none"; // O botão Estudar Depois NÃO deve aparecer.
                    btnDeletarCard.style.display = "block"; // Mas o botão Deletar Card deve.
                } 
                // [ CASO 2 ] - Se o Card não existe no BD, é o inverso do CASO 1:
                else {
                    btnEstudarDepois.style.display = "block"; // O botão Estudar Depois deve aparecer.
                    btnDeletarCard.style.display = "none"; // Mas o botão Deletar Card NÃO deve.
                }
            })
            .catch(erro => {
                console.error("Erro ao checar card:", erro);
                btnEstudarDepois.style.display = "block";
                btnDeletarCard.style.display = "none";
            });
    }

    // Aqui, fornecemos o tempo de início e fim para o funcionamento do Loop:
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
    
    // [ MEMBRO 3 - BLOCO 3 ]Só dá play e inicia o loop se iniciarAutoplay for verdadeiro. Veremos o uso dessa variável booleana logo abaixo, nos novos botões implementados:
    if (iniciarAutoplay && player && typeof player.seekTo === 'function') {
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

    // [ MEMBRO 3 - BLOCO 3 ]: Eu adicionei 2 novos modais para o usuário ser informado no Front-End: 
    // MODAL TIPO 1:
    // Um deles é o que aparece sempre que qualquer URL de vídeo é carregada na home. Ele informa o usuário sobre o tipo de legenda, e sobre o título do vídeo.
    // MODAL TIPO 2:
    // O outro é sobre o salvamento de Decks e Cards. Ele aparece sempre que o usuário clica em Estudar Depois.
    // Em ambos esses modais, o usuário deve clicar em continuar para fechá-los.
    // Nova regra para fazer o botão verde "continuar" fechar o modal:
    // Fecha o modal e força a atualização do estado dos botões pelo banco:
    if(event.target.id === 'botaoContinuarCard'){
        const modalSucesso = document.getElementById('modalSucessoCard');
        if (modalSucesso) {
            // Verificamos se o modal é do TIPO 1 usando a variável aviso_inicial:
            if (modalSucesso.dataset.tipoModal === "aviso_inicial") {
                // Começamos fechando o modal:
                modalSucesso.style.display = "none";
                
                // Limpo a marcação para os próximos usos (salvamentos de card):
                delete modalSucesso.dataset.tipoModal;

                // Pauso o player explicitamente por segurança:
                if (player && typeof player.pauseVideo === 'function') {
                    player.pauseVideo();
                }
                
                // E carrego os elementos visuais da frase, mas digo para NÃO iniciar o vídeo/loop ainda:
                if (typeof carregarFraseAtual === 'function') {
                    carregarFraseAtual(false); 
                }

            }

            else {
                // Se caiu aqui, o modal é do TIPO 2. Começamos fechando o modal:
                modalSucesso.style.display = "none";

                // Como nesse caso o usuário acabou de salvar um Card, podemos mostrar o botão Deletar Card agora:
                const btnDeletarDeck = document.getElementById('deletardeck');
                if (btnDeletarDeck) {
                    btnDeletarDeck.style.display = "block";
                }
                
                if (typeof carregarFraseAtual === 'function') {
                    carregarFraseAtual(false); // Aqui se o usuário tiver pausado o vídeo, ele continua pausado enquanto o modal abre e fecha.
                }
            }
        }
    }

    // [ MEMBRO 3 - BLOCO 3 ]: Lógica de transferência de dados do vídeo através do botão "Estudar Depois":
    if (event.target.id === 'estudardepois') {
        // Se não houver frases carregadas, não é necessário fazer nada:
        if (!blocosDeEstudo || blocosDeEstudo.length === 0) return;

        // Precisamos então pegar os dados do bloco de legenda que está aparecendo na tela:
        const blocoAtual = blocosDeEstudo[blocoAtualIndex];

        // E então, simular um formulário (Form(...)) que o FastAPI espera na rota POST do main.py:
        const dadosFormulario = new URLSearchParams();
        dadosFormulario.append('video_id', currentVideoId);
        dadosFormulario.append('titulo_video', currentVideoTitle); 
        dadosFormulario.append('texto_legenda', blocoAtual.texto_limpo);
        dadosFormulario.append('start_time', blocoAtual.tempo_inicio);
        dadosFormulario.append('end_time', blocoAtual.tempo_fim);

        // Enviando para o Back-End em segundo plano (nada muda na tela):
        fetch('/salvar_card', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: dadosFormulario
        })
        .then(resposta => resposta.json())
        .then(dados => {
            // Capturando os elementos do novo modal HTML:
            const modalSucesso = document.getElementById('modalSucessoCard');
            const textoLogs = document.getElementById('textologs');
            
            if (modalSucesso && textoLogs) {

                delete modalSucesso.dataset.tipoModal;
                // Então, é injetada a string de logs acumulada no Python (dados.texto):
                // O .replace(/\n/g, '<br>') transforma as quebras de linha do Python em quebras visíveis no HTML:
                textoLogs.innerHTML = dados.texto.replace(/\n/g, '<br>');
                
                // Abre o modal na tela exibindo o resultado em verde
                modalSucesso.style.display = "block";
            }

            // Imprime o resultado silenciosamente apenas no console para acompanhar:
            console.log("Resposta do servidor:", dados.mensagem);
        })
        .catch(erro => {
            console.error("Erro ao salvar o card e abrir o modal:", erro);
        });
    }

    // [ MEMBRO 3 - BLOCO 3 ]: Lógica para o botão de "Revisão diária":
    if (event.target.id === 'revisaodiaria') {
        fetch('/api/revisao_diaria')
        .then(resposta => resposta.json())
        .then(dados => {
            console.log("Busca de revisão executada com sucesso. Verifique o terminal.");
        })
        .catch(erro => {
            console.error("Erro ao buscar cards do dia:", erro);
        });
    }

    // [ MEMBRO 3 - BLOCO 3 ]: Lógica para o botão "Deletar Card"
    if (event.target.id === 'deletarcard') {
        if (!blocosDeEstudo || blocosDeEstudo.length === 0) return;

        // Começo obtendo os dados do bloco de legenda atual:
        const blocoAtual = blocosDeEstudo[blocoAtualIndex];

        // Preparo então o formulário que o Python espera receber via POST, enviando o ID do vídeo e o texto exato da legenda para a rota:
        const dadosFormulario = new URLSearchParams();
        dadosFormulario.append('video_id', currentVideoId);
        dadosFormulario.append('texto_legenda', blocoAtual.texto_limpo);

        // Disparamos a requisição de deleção para o Back-End:
        fetch('/api/deletar_card', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: dadosFormulario
        })
        .then(resposta => resposta.json())
        .then(dados => {
            console.log("Resposta do servidor:", dados.mensagem);
            // Depois de Deletar um Card específico, o botão Estudar Depois volta a aparecer para o usuário no pedaço de legenda desse Card.
            // Isso caso o usuário queira salvar esse Card que ele deletou novamente em outro momento.
            document.getElementById('estudardepois').style.display = "block";
            event.target.style.display = "none";
        })
        .catch(erro => {
            console.error("Erro ao solicitar deleção do card:", erro);
        });
    }

    // [ MEMBRO 3 - BLOCO 3 ]: Lógica para deletar o Deck inteiro em cascata:
    if (event.target.id === 'deletardeck') {

        const dadosFormulario = new URLSearchParams();
        dadosFormulario.append('video_id', currentVideoId);

        fetch('/api/deletar_deck', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: dadosFormulario
        })
        .then(resposta => resposta.json())
        .then(dados => {
            console.log("Resposta do servidor:", dados.mensagem);
            
            // Esconde o botão de Deletar Deck da tela:
            event.target.style.display = "none";
            
            // Atualiza a frase atual para resetar o botão de Estudar depois/ Deletar Card, com a lógica já descrita lá em cima:
            carregarFraseAtual(false);
        })
        .catch(erro => console.error("Erro ao deletar deck:", erro));
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