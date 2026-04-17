(function() {
    // --- Widget Configuration ---
    const scriptTag = document.currentScript;
    const API_BASE = scriptTag ? scriptTag.getAttribute('data-api-url') : 'https://rx-ai-7a8g.onrender.com';
    const CSS_URL = `${API_BASE}/css/bisarx-widget.css`;

    // --- State ---
    let isOpen = false;
    let isRecording = false;
    let recognition = null;
    let selectedImage = null;
    let currentCaseId = null;
    let chatHistory = [];
    let caseWs = null;

    // --- DOM Elements (will be created) ---
    let wrapper, fab, window, messagesContainer, textarea, sendBtn, micBtn, cameraBtn, imagePreview;

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
        window = document.getElementById('bx-window');
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

    function toggleWindow() {
        isOpen = !isOpen;
        window.classList.toggle('open', isOpen);
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
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: chatHistory,
                    image_data: currentSelectedImage
                })
            });
            const data = await response.json();
            
            if (data.reply) {
                addBotMessage(data.reply);
                chatHistory.push({ role: 'assistant', content: data.reply });
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

    function toggleVoice() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Voice input is not supported in this browser.");
            return;
        }

        if (isRecording) {
            recognition.stop();
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

    function connectWebSocket(caseId) {
        const wsProto = API_BASE.startsWith('https') ? 'wss' : 'ws';
        const wsUrl = `${API_BASE.replace(/^http/, wsProto)}/ws/case/${caseId}`;
        
        caseWs = new WebSocket(wsUrl);
        caseWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'case_updated' && data.pharmacist_feedback) {
                    if (data.play_loud_sound) playLoudNotification();
                    const feedback = `📢 **Pharmacist Review Complete**\n\n${data.pharmacist_feedback}\n\n${data.drug_name ? `**Medication:** ${data.drug_name}` : ''}\n${data.referral_advice ? `**Referral:** ${data.referral_advice}` : ''}`;
                    addBotMessage(feedback);
                }
            } catch (e) {}
        };
        caseWs.onclose = () => {
            setTimeout(() => connectWebSocket(caseId), 5000);
        };
    }

    init();
})();
