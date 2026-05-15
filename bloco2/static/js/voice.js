
// Removemos as variáveis de HTML globais. Só deixamos a lógica de áudio.
let recognition;
let audioCtx, analyser, dataArray;
let isRecording = false;
let silenceTimer = null;

const SILENCE_DELAY = 1200;

function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        console.error("Speech API não suportada neste navegador.");
        return;
    }
    
    recognition = new SR();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = e => {
        let text = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
            text += e.results[i][0].transcript;
        }
        
        // Puxa a div dinamicamente
        const transcript = document.getElementById("transcript");
        if (transcript) transcript.innerText = text;
    };

    recognition.onend = () => {};
}

async function initAudio() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    audioCtx = new AudioContext();
    analyser = audioCtx.createAnalyser();

    const src = audioCtx.createMediaStreamSource(stream);
    src.connect(analyser);

    dataArray = new Uint8Array(analyser.fftSize);
}

function drawWave() {
    // Puxa o canvas dinamicamente a cada frame para evitar erros do HTMX
    const canvas = document.getElementById("wave");
    if (!canvas) return; 
    
    const ctx = canvas.getContext("2d");

    analyser.getByteTimeDomainData(dataArray);

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.beginPath();

    let slice = canvas.width / dataArray.length;
    let x = 0;
    let sum = 0;

    for (let i = 0; i < dataArray.length; i++) {
        let v = dataArray[i] / 128;
        let y = (v - 1) * canvas.height / 2 + canvas.height / 2;

        sum += Math.abs(v - 1);

        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);

        x += slice;
    }

    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 2;
    ctx.stroke();

    let volume = sum / dataArray.length;

    if (volume < 0.01) {
        if (!silenceTimer) {
            silenceTimer = setTimeout(() => {
                stopRecording();
            }, SILENCE_DELAY);
        }
    } else {
        if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
        }
    }

    if (isRecording) requestAnimationFrame(drawWave);
}

// A função que é chamada pelo botão
function startRecording() {
    if (isRecording) return;
    

    // Busca os elementos APENAS quando o botão é clicado
    const panel = document.getElementById("panel");
    const transcript = document.getElementById("transcript");
    const micBtn = document.getElementById("gravar");

    if (panel) panel.classList.remove("hidden");
    if (transcript) {
        transcript.style.display = "block";
        transcript.innerText = "Listening...";
    }

    if (!recognition) initSpeech();

    // Tenta ligar o microfone
    initAudio().then(() => {
        isRecording = true;
        if (micBtn) micBtn.classList.add("recording");

        recognition.start();
        drawWave();
    }).catch((err) => {
        console.error("Microfone bloqueado ou erro: ", err);
        if (transcript) transcript.innerText = "Erro: Permita o uso do microfone no navegador.";
    });
}

function stopRecording() {
    isRecording = false;

    const micBtn = document.getElementById("gravar");
    if (micBtn) micBtn.classList.remove("recording");

    if (recognition) recognition.stop();

    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }
}