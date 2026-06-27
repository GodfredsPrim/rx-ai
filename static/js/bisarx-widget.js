(function() {
    // --- Widget Configuration ---
    const scriptTag = document.currentScript;
    const API_BASE = scriptTag ? scriptTag.getAttribute('data-api-url') : 'https://rx-ai-production.up.railway.app';
    const CSS_URL = `${API_BASE}/css/bisarx-widget.css`;
    const SNWOLLEY_BASE = `${API_BASE}/api/snwolley`;
    const SNWOLLEY_CHAT_MODEL = (window.BISARX_SNWOLLEY_MODEL || 'gpt-4o-mini');

    // --- State ---
    let isOpen = false;
    let isRecording = false;
    let recognition = null;
    let mediaRecorder = null;
    let mediaStream = null;
    let mediaChunks = [];
    let selectedImage = null;
    let currentCaseId = null;
    let chatHistory = [];
    let caseWs = null;

    // --- DOM Elements (will be created) ---
    let wrapper, fab, chatWindow, messagesContainer, textarea, sendBtn, micBtn, cameraBtn, imagePreview;

    // --- Initialization ---
    function init() {
        // Load CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = CSS_URL;
        document.head.appendChild(link);

        // Create UI
        createUI();
        setupEventListeners();
        addBotMessage("What are your symptoms? Describe what you're experiencing and how long it has been going on.");
    }

    function createUI() {
        wrapper = document.createElement('div');
        wrapper.className = 'bisarx-widget-wrapper';
        wrapper.innerHTML = `
            <div class="bx-window" id="bx-window">
                <div class="bx-header">
                    <div class="bx-header-info">
                        <div class="bx-header-text">
                            <h3>Ask BisaRx</h3>
                            <span>AI Symptom Triage</span>
                        </div>
                    </div>
                    <button class="bx-close" id="bx-close">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                    </button>
                </div>
                <div class="bx-messages" id="bx-messages"></div>
                <div class="bx-input-area">
                    <div id="bx-image-preview" style="display:none; margin-bottom: 8px; position:relative;">
                        <img src="" style="height:60px; border-radius:8px; border:1px solid #ddd;">
                        <button style="position:absolute; top:-5px; right:-5px; background:red; color:white; border:none; border-radius:50%; width:18px; height:18px; font-size:10px; cursor:pointer;">✕</button>
                    </div>
                    <div class="bx-input-container">
                        <button class="bx-btn-icon" id="bx-camera-btn">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                        </button>
                        <button class="bx-btn-icon" id="bx-mic-btn">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>
                        </button>
                        <textarea class="bx-textarea" placeholder="Describe symptoms..." rows="1"></textarea>
                        <button class="bx-btn-send" id="bx-send-btn">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                        </button>
                    </div>
                </div>
            </div>
            <button class="bx-fab" id="bx-fab">
                <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </button>
            <input type="file" id="bx-file-input" style="display:none;" accept="image/*">
        `;
        document.body.appendChild(wrapper);

        fab = document.getElementById('bx-fab');
        chatWindow = document.getElementById('bx-window');
        messagesContainer = document.getElementById('bx-messages');
        textarea = wrapper.querySelector('.bx-textarea');
        sendBtn = document.getElementById('bx-send-btn');
        micBtn = document.getElementById('bx-mic-btn');
        cameraBtn = document.getElementById('bx-camera-btn');
        imagePreview = document.getElementById('bx-image-preview');
    }

    function setupEventListeners() {
        fab.onclick = toggleWindow;
        document.getElementById('bx-close').onclick = toggleWindow;
        sendBtn.onclick = handleSend;
        
        textarea.oninput = () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        };

        textarea.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        };

        cameraBtn.onclick = () => document.getElementById('bx-file-input').click();
        document.getElementById('bx-file-input').onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (re) => {
                    selectedImage = re.target.result;
                    imagePreview.querySelector('img').src = selectedImage;
                    imagePreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        };

        imagePreview.querySelector('button').onclick = () => {
            selectedImage = null;
            imagePreview.style.display = 'none';
        };

        micBtn.onclick = toggleVoice;
    }

    function extractText(payload) {
        if (!payload) return '';
        if (typeof payload === 'string') return payload;
        if (Array.isArray(payload)) {
            for (const item of payload) {
                const result = extractText(item);
                if (result) return result;
            }
            return '';
        }
        if (typeof payload === 'object') {
            if (typeof payload.reply === 'string') return payload.reply;
            if (typeof payload.text === 'string') return payload.text;
            if (typeof payload.transcript === 'string') return payload.transcript;
            const choiceText = payload?.choices?.[0]?.message?.content || payload?.choices?.[0]?.text;
            if (typeof choiceText === 'string') return choiceText;
            for (const value of Object.values(payload)) {
                const nested = extractText(value);
                if (nested) return nested;
            }
        }
        return '';
    }

    async function postSnwolley(endpoint, body) {
        const response = await fetch(`${SNWOLLEY_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {}),
        });
        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json') ? await response.json() : await response.text();
        if (!response.ok) {
            throw new Error(typeof payload === 'string' ? payload : (extractText(payload) || payload?.detail || 'Snwolley request failed'));
        }
        return payload;
    }

    async function requestSnwolleyChat(messages) {
        const payload = await postSnwolley('/chat/completions', {
            model: SNWOLLEY_CHAT_MODEL,
            messages,
        });
        const text = extractText(payload);
        if (!text) throw new Error('Empty Snwolley chat response');
        return text;
    }

    async function requestSnwolleyVision(imageData, prompt) {
        const payload = await postSnwolley('/vision', {
            image_data: imageData,
            prompt: prompt || 'Describe medically relevant findings in this image.',
        });
        return extractText(payload);
    }

    async function requestSnwolleyStt(blob) {
        const base64Audio = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = String(reader.result || '');
                resolve(result.includes(',') ? result.split(',')[1] : result);
            };
            reader.onerror = () => reject(new Error('Failed to read captured audio'));
            reader.readAsDataURL(blob);
        });
        const payload = await postSnwolley('/stt', {
            audio_base64: base64Audio,
            mime_type: blob.type || 'audio/webm',
        });
        return extractText(payload);
    }

    async function requestSnwolleyTts(text) {
        if (!text) return;
        try {
            const payload = await postSnwolley('/tts', { text });
            if (payload?.audio_url) {
                const audio = new Audio(payload.audio_url);
                await audio.play();
                return;
            }
            if (payload?.audio_base64) {
                const mimeType = payload?.mime_type || 'audio/mpeg';
                const audio = new Audio(`data:${mimeType};base64,${payload.audio_base64}`);
                await audio.play();
            }
        } catch (e) {
            console.warn('Widget TTS failed', e);
        }
    }

    function toggleWindow() {
        isOpen = !isOpen;
        chatWindow.classList.toggle('open', isOpen);
    }

    async function handleSend() {
        const text = textarea.value.trim();
        if (!text && !selectedImage) return;

        textarea.value = '';
        textarea.style.height = 'auto';
        
        addUserMessage(text, selectedImage);
        
        const currentSelectedImage = selectedImage;
        selectedImage = null;
        imagePreview.style.display = 'none';

        chatHistory.push({ role: 'user', content: text });
        
        try {
            let enrichedText = text;
            if (currentSelectedImage) {
                try {
                    const visionContext = await requestSnwolleyVision(currentSelectedImage, text);
                    if (visionContext) {
                        enrichedText = `${text}\n\n[Vision context]\n${visionContext}`;
                    }
                } catch (visionErr) {
                    console.warn('Widget vision call failed, continuing without vision context', visionErr);
                }
            }

            let data = { reply: '' };
            try {
                const reply = await requestSnwolleyChat([
                    ...chatHistory.slice(0, -1),
                    { role: 'user', content: enrichedText },
                ]);
                data.reply = reply;
            } catch (snErr) {
                console.warn('Snwolley chat failed; falling back to /api/chat', snErr);
                const fallbackResponse = await fetch(`${API_BASE}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: chatHistory,
                        image_data: currentSelectedImage,
                    }),
                });
                data = await fallbackResponse.json();
            }
            
            if (data.reply) {
                addBotMessage(data.reply);
                chatHistory.push({ role: 'assistant', content: data.reply });
                requestSnwolleyTts(data.reply);
            }

            if (data.case_id && !currentCaseId) {
                currentCaseId = data.case_id;
                addBotMessage(`Your case has been sent to a licensed pharmacist (Case ID: ${data.case_id}). I'll notify you here when they respond.`);
                connectWebSocket(data.case_id);
            }
        } catch (err) {
            addBotMessage("Sorry, I'm having trouble connecting right now.");
        }
    }

    function addUserMessage(text, image) {
        const msg = document.createElement('div');
        msg.className = 'bx-msg user';
        msg.innerHTML = `
            ${image ? `<img src="${image}" style="width:100%; border-radius:8px; margin-bottom:8px;">` : ''}
            <div>${text}</div>
        `;
        messagesContainer.appendChild(msg);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addBotMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'bx-msg bot';
        msg.innerHTML = `<div>${text.replace(/\n/g, '<br>')}</div>`;
        messagesContainer.appendChild(msg);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    async function toggleVoice() {
        if (isRecording) {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            } else if (recognition) {
                recognition.stop();
            }
            return;
        }

        if (navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined') {
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaChunks = [];
                mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data?.size) mediaChunks.push(event.data);
                };
                mediaRecorder.onstop = async () => {
                    try {
                        const blob = new Blob(mediaChunks, { type: 'audio/webm' });
                        const transcript = await requestSnwolleyStt(blob);
                        if (transcript) {
                            textarea.value = transcript;
                            textarea.style.height = 'auto';
                            textarea.style.height = textarea.scrollHeight + 'px';
                        }
                    } catch (sttErr) {
                        console.warn('Snwolley STT failed in widget', sttErr);
                    } finally {
                        if (mediaStream) {
                            mediaStream.getTracks().forEach(track => track.stop());
                            mediaStream = null;
                        }
                        mediaChunks = [];
                        isRecording = false;
                        micBtn.classList.remove('active');
                    }
                };
                mediaRecorder.start();
                isRecording = true;
                micBtn.classList.add('active');
                return;
            } catch (err) {
                console.warn('Widget MediaRecorder unavailable, trying browser speech API', err);
            }
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Voice input is not supported in this browser.");
            return;
        }
        isRecording = true;
        micBtn.classList.add('active');
        recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            textarea.value = transcript;
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        };
        recognition.onend = () => {
            isRecording = false;
            micBtn.classList.remove('active');
        };
        recognition.onerror = () => {
            isRecording = false;
            micBtn.classList.remove('active');
        };
        recognition.start();
    }

    function playLoudNotification() {
        const audio = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
        audio.volume = 1.0;
        audio.play().catch(e => console.warn('Audio play blocked', e));
    }

    function cleanEvalText(text) {
        if (!text) return '';
        return text.replace(/\*\*/g, '').replace(/📢/g, '').trim();
    }

    function generateEvaluationHTML(data) {
        const drugName = cleanEvalText(data.drug_name);
        const feedback = cleanEvalText(data.pharmacist_feedback);
        const referral = cleanEvalText(data.referral_advice);
        const followUp = cleanEvalText(data.follow_up_instructions);

        return `
            <div class="clinical-evaluation-card">
                <div class="cec-header">
                    <div class="cec-header-icon">⚕</div>
                    <div class="cec-header-title">Clinical Report</div>
                </div>
                
                ${drugName ? `
                <div class="cec-section">
                    <div class="cec-label">Medication</div>
                    <div class="cec-drug-box">
                        <div class="cec-drug-name">${drugName}</div>
                    </div>
                </div>
                ` : ''}

                <div class="cec-section">
                    <div class="cec-label">Instructions</div>
                    <div class="cec-content">${feedback || 'No specific instructions.'}</div>
                </div>

                ${referral ? `
                <div class="cec-section">
                    <div class="cec-label">Referral / Critical Action</div>
                    <div class="cec-referral">${referral}</div>
                </div>
                ` : ''}
            </div>
        `;
    }

    function connectWebSocket(caseId) {
        const wsProto = API_BASE.startsWith('https') ? 'wss' : 'ws';
        const wsUrl = `${API_BASE.replace(/^https?/, wsProto)}/ws/case/${caseId}`;
        
        if (caseWs) try { caseWs.close(); } catch(e){}
        
        caseWs = new WebSocket(wsUrl);
        caseWs.onopen = () => console.log('BisaRx: Connected to real-time updates');
        caseWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'case_updated' && data.pharmacist_feedback) {
                    if (data.play_loud_sound) playLoudNotification();
                    const evaluationHTML = generateEvaluationHTML(data);
                    addBotMessage(evaluationHTML);
                    // Successfully received evaluation
                    currentCaseId = null; 
                }
            } catch (e) {}
        };
        caseWs.onclose = () => {
            if (currentCaseId) setTimeout(() => connectWebSocket(caseId), 5000);
        };
    }

    async function checkCaseStatus() {
        if (!currentCaseId) return;
        try {
            const res = await fetch(`${API_BASE}/api/cases/guest/${currentCaseId}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'Reviewed' || data.pharmacist_feedback) {
                const evaluationHTML = generateEvaluationHTML(data);
                addBotMessage(evaluationHTML);
                playLoudNotification();
                currentCaseId = null; // Stop polling
            }
        } catch (e) {}
        if (currentCaseId) setTimeout(checkCaseStatus, 15000); // Poll every 15s
    }

    // Start polling if we have a case
    setInterval(() => { if (currentCaseId) checkCaseStatus(); }, 60000); // Safety check every minute

    init();
})();
