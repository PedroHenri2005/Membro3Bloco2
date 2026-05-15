// CODIGO YOUTUBE PLAYER

let player, loopRAF;
let startTime = 0, endTime = 0; 
let currentVideoId;
let isPaused = false;

function handleLoadVideo() {
    const link = document.getElementById("youtubeLink").value;
    const id = extractVideoId(link);
    currentVideoId = id;
    loadVideo(id);
}

function extractVideoId(url) {
    try {
        const u = new URL(url);
        return u.searchParams.get("v") || u.pathname.split("/").pop();
    } catch {
        return null;
    }
}

let apiPronta = false;

// Esta função é chamada AUTOMATICAMENTE pelo YouTube quando tudo carregar
function onYouTubeIframeAPIReady() {
    apiPronta = true;
    console.log("API do YouTube pronta para uso.");
}

function loadVideo(videoId) {
    // Se a API ainda não sinalizou que está pronta, esperamos um pouco
    if (!apiPronta) {
        console.log("Aguardando sinal da API do YouTube...");
        setTimeout(() => loadVideo(videoId), 200);
        return;
    }

    if (player && typeof player.cueVideoById === 'function') {
        player.cueVideoById({ videoId: videoId, startSeconds: startTime });
    } else {
        player = new YT.Player("player", {
            videoId: videoId,
            events: { onReady: onReady }
        });
    }
}

function onReady() {
    player.cueVideoById({
        videoId: currentVideoId,
        startSeconds: startTime
    });
}

function playVideo() {
    player.seekTo(startTime, true);
    player.playVideo();
    startLoop();
}

function togglePause() {
    if (!player) return;

    const btn = document.getElementById("toggleBtn");

    if (!isPaused) {
        player.pauseVideo();
        stopLoop();
        if(btn) btn.innerText = "Continuar";
    } else {
        player.playVideo();
        startLoop();
        if(btn) btn.innerText = "Pause";
    }

    isPaused = !isPaused;
}

function startLoop() {
    function check() {
        let t = player.getCurrentTime();
        if (t >= endTime - 0.05) {
            player.seekTo(startTime, true);
        }
        loopRAF = requestAnimationFrame(check);
    }
    check();
}

function stopLoop() {
    cancelAnimationFrame(loopRAF);
}