const API_URL = '/api';
const PORTAL_MODE = window.BISARX_PORTAL || document.body?.dataset?.portal || 'patient';
let _chatGreetingShown = false;
let _patientWs = null;
let _caseWs = null;
let _pharmacistWs = null;
let currentSession = { role: 'guest' };
let currentUser = null;
let lang = 'en', history = [], ttsOn = false, isRecording = false, recognition = null;
const synth = window.speechSynthesis;
let pendingConditionSelection = null;
let patientReportSignatures = new Map();
let patientReportStatePrimed = false;
let patientReportSyncTimer = null;
let conditions = [], allergies = [];
let currentImageData = null;


function isPortalMode(mode) { return PORTAL_MODE === mode; }
function isDedicatedPortal() { return isPortalMode('admin') || isPortalMode('pharmacist'); }

function getDedicatedPortalConfig() {
  if (isPortalMode('admin')) return { role: 'admin', navId: 'nav-admin', panelId: 'panel-admin', brandTag: 'Admin Portal' };
  if (isPortalMode('pharmacist')) return { role: 'pharmacist', navId: 'nav-pharmacist', panelId: 'panel-pharmacist', brandTag: 'Pharmacist Portal' };
  return null;
}

function setDedicatedPortalVisibility(isUnlocked) {
  if (!isDedicatedPortal()) return;
  document.body.classList.toggle('portal-locked', !isUnlocked);
  const gate = document.getElementById('portal-gate');
  if (gate) gate.setAttribute('aria-hidden', isUnlocked ? 'true' : 'false');
}

function cleanupDedicatedPortalLayout() {
  const config = getDedicatedPortalConfig();
  if (!config) return;
  const sharedIdsToRemove = [
    'btn-new-chat', 'nav-chat', 'nav-bodymap', 'nav-conditions', 'nav-redflag', 'nav-profile', 'nav-connect', 'nav-history',
    'panel-chat', 'panel-bodymap', 'panel-conditions', 'panel-redflag', 'panel-profile', 'panel-connect', 'panel-history'
  ];
  const roleSpecificIds = config.role === 'admin' ? ['nav-pharmacist', 'panel-pharmacist'] : ['nav-admin', 'panel-admin'];
  [...sharedIdsToRemove, ...roleSpecificIds].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
  const brandTag = document.querySelector('.brand-tag');
  if (brandTag) brandTag.textContent = config.brandTag;
  const nav = document.getElementById(config.navId);
  if (nav) { nav.style.display = 'flex'; nav.classList.add('on'); }
  const panel = document.getElementById(config.panelId);
  if (panel) panel.classList.add('on');
}

function getPortalHome() {
  if (isPortalMode('pharmacist')) return '/pharmacist';
  if (isPortalMode('admin')) return '/admin';
  return '/';
}

function showLoading(message = 'Loading...') {
  const existing = document.getElementById('global-loading');
  if (existing) return existing;
  const loader = document.createElement('div');
  loader.id = 'global-loading';
  loader.innerHTML = `
    <div class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>${message}</p>
    </div>
  `;
  loader.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:9999;background:rgba(255,255,255,0.9);backdrop-filter:blur(4px);';
  document.body.appendChild(loader);
  return loader;
}

function hideLoading() {
  const loader = document.getElementById('global-loading');
  if (loader) {
    loader.style.opacity = '0';
    loader.style.transition = 'opacity 0.3s ease';
    setTimeout(() => loader.remove(), 300);
  }
}

function showToast(message, type = 'info', duration = 3000) {
  const existing = document.querySelector('.toast-container');
  const container = existing || (() => {
    const c = document.createElement('div');
    c.className = 'toast-container';
    c.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:12px;';
    document.body.appendChild(c);
    return c;
  })();
  const toast = document.createElement('div');
  const colors = { success: 'linear-gradient(135deg,#38a169,#2f855a)', error: 'linear-gradient(135deg,#e53e3e,#c53030)', info: 'linear-gradient(135deg,var(--primary-light),var(--primary))', warning: 'linear-gradient(135deg,#ed8936,#dd6b20)' };
  toast.style.cssText = `padding:14px 20px;border-radius:14px;color:white;font-weight:600;font-size:.9rem;background:${colors[type] || colors.info};box-shadow:0 12px 28px rgba(0,0,0,0.15);animation:slideIn .3s ease;max-width:320px;`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0'; toast.style.transform = 'translateX(20px)'; toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Fallback Data
window.FALLBACK_CONDITIONS = [
  { name: 'Malaria / Fever', drug: 'Artemether + Lumefantrine', tags: [{ t: 'CoartemAr', c: 'g' }, { t: '6 doses/3 days', c: 'b' }, { t: 'With food', c: 'a' }], q: 'Tell me about malaria symptoms and Coartem treatment.' },
  { name: 'Headache', drug: 'Paracetamol / Ibuprofen', tags: [{ t: 'Tension', c: 'b' }, { t: 'Migraine', c: 'b' }, { t: 'Refer if severe', c: 'r' }], q: 'Headache assessment and first-line treatment?' },
  { name: 'Diarrhea', drug: 'ORS + Zinc 10-20mg', tags: [{ t: 'Rehydration', c: 'g' }, { t: 'Zinc', c: 'b' }, { t: 'Metronidazole if amoebic', c: 'a' }], q: 'Diarrhea management advice.' },
  { name: 'Cough / URTI', drug: 'Steam / Guaifenesin', tags: [{ t: 'Fluids', c: 'g' }, { t: 'Antibiotic if bacterial', c: 'a' }, { t: 'Refer if SOB', c: 'r' }], q: 'Cough and cold management?' },
  { name: 'Abdominal Pain', drug: 'Antacid / Omeprazole', tags: [{ t: 'Gastritis', c: 'b' }, { t: 'NSAID for cramps', c: 'g' }, { t: 'Refer if severe', c: 'r' }], q: 'Abdominal pain assessment?' },
  { name: 'Skin Rash', drug: 'Hydrocortisone / Clotrimazole', tags: [{ t: 'Allergic', c: 'a' }, { t: 'Fungal', c: 'b' }, { t: 'Antihistamine', c: 'g' }], q: 'Skin rash first-line treatment?' },
  { name: 'Urinary Complaints', drug: 'Nitrofurantoin / Ciprofloxacin', tags: [{ t: 'UTI', c: 'b' }, { t: 'Refer if pregnant', c: 'r' }, { t: 'Fluids', c: 'g' }], q: 'Urinary tract complaint management?' },
  { name: 'Hypertension', drug: 'Amlodipine 5mg OD', tags: [{ t: 'BP monitoring', c: 'b' }, { t: 'Adherence', c: 'g' }, { t: 'Refer if uncontrolled', c: 'r' }], q: 'Hypertension counseling guidelines?' },
  { name: 'Diabetes', drug: 'Metformin (first-line)', tags: [{ t: 'Type 2 DM', c: 'b' }, { t: 'Monitor glucose', c: 'g' }, { t: 'Refer if uncontrolled', c: 'a' }], q: 'Diabetes medication counseling?' },
  { name: 'Pain / Inflammation', drug: 'Paracetamol / Diclofenac gel', tags: [{ t: 'NSAID', c: 'b' }, { t: 'Topical option', c: 'g' }, { t: 'Avoid overuse', c: 'a' }], q: 'Pain and inflammation management?' }
];

window.FALLBACK_REDFLAGS = [
  { condition: 'Malaria / Severe Fever', flags: ['Cannot keep oral medication down', 'Confusion, convulsions, or severe weakness', 'Yellowing of eyes or dark urine', 'Fever lasting more than 3 days despite treatment', 'Pregnant or infant under 6 months'] },
  { condition: 'Head / Neurological', flags: ['Sudden severe thunderclap headache', 'Neck stiffness with fever', 'Vision changes or slurred speech', 'Headache after head injury'] },
  { condition: 'Breathing / Chest', flags: ['Difficulty breathing at rest', 'Coughing blood', 'Rapid breathing in children', 'Productive cough with fever over 3 days'] },
  { condition: 'Stomach / Abdomen', flags: ['Severe dehydration - sunken eyes, no urine', 'Blood or mucus in stool', 'Rigid board-like abdomen', 'Multiple household members ill'] },
  { condition: 'General Danger Signs', flags: ['Altered consciousness or unconsciousness', 'Uncontrolled bleeding', 'Pregnancy with acute serious illness', 'Patient cannot stand or self-care'] }
];

const LANGS = {
  en: { greeting: "What are your symptoms? Describe what you're experiencing and how long it has been going on.", chips: ["I have a headache", "Stomach pain", "I feel feverish", "I have a cough", "My child is sick", "Skin rash"], placeholder: "Describe your symptoms...", disc: "For general guidance only. Consult a licensed pharmacist for diagnosis, treatment, or medication decisions.", discLabel: "Clinical Note:" },
  tw: { greeting: "Wo yaree ben na ewo wo? Ka kyerE me sEdeE wote wo ho ne bere a edi so.", chips: ["Me ti ye me yaw", "Me yafunu ye me yaw", "Mewo atiridiinini", "Mewo ekoo", "Me ba yare", "Honam yare"], placeholder: "Ka me nkyEn sEdeE wote wo ho...", disc: "Yei yE akwankyerE nkutoo. Bisa oduruyEfo anaa odokota ansa na woasi gyinae biara.", discLabel: "NsErEwmu:" },
  ha: { greeting: "Mene ne alamu ku? Bayyana yadda kuke ji da tsawon lokaci.", chips: ["Ina da ciwon kai", "Ciki na yi mini ciwo", "Ina da zazzabi", "Ina da tari", "Yaro na ba shi da lafiya", "Ina da kuraje"], placeholder: "Bayyana alamun ku...", disc: "Jagora ne kawai. Tuntubi kwararren likita ko likitan magani kafin yanke shawarar magani.", discLabel: "Bayani:" },
  fr: { greeting: "Quels sont vos symptomes? Decrivez ce que vous ressentez et depuis combien de temps.", chips: ["J'ai mal a la tete", "Douleur abdominale", "J'ai de la fievre", "Je tousse", "Mon enfant est malade", "Eruption cutanee"], placeholder: "Decrivez vos symptomes...", disc: "Conseils generaux uniquement. Consultez un professionnel de sante agree pour toute decision clinique.", discLabel: "Note:" }
};

const ZONES = {
  head: { title: 'Head & Brain', icon: '🧠', sub: 'Headache, dizziness, fever, vision changes', simple: 'Head pain or dizziness', q: 'I have pain in my head. Please assess.' },
  throat: { title: 'Throat & Neck', icon: '🦒', sub: 'Sore throat, difficulty swallowing, neck stiffness', simple: 'Throat or neck problem', q: 'I have throat or neck discomfort. Please assess.' },
  chest: { title: 'Chest & Lungs', icon: '🫁', sub: 'Cough, shortness of breath, chest pain', simple: 'Chest pain or breathing problem', q: 'I have chest pain or breathing difficulty. Please assess.' },
  abdomen: { title: 'Stomach', icon: '🍕', sub: 'Stomach pain, nausea, vomiting, diarrhea', simple: 'Stomach or belly pain', q: 'I have abdominal pain or stomach discomfort. Please assess.' },
  arm: { title: 'Arms & Joints', icon: '💪', sub: 'Arm pain, joint swelling, muscle aches', simple: 'Arm or joint pain', q: 'I have pain in my arms or joints. Please assess.' },
  lower: { title: 'Lower Abdomen', icon: '🧬', sub: 'Lower cramps, urinary problems, menstrual pain', simple: 'Lower belly or urine problem', q: 'I have lower abdominal or urinary symptoms. Please assess.' },
  leg: { title: 'Legs', icon: '🦵', sub: 'Leg pain, swelling, muscle weakness', simple: 'Leg pain or swelling', q: 'I have pain or swelling in my legs. Please assess.' },
  foot: { title: 'Feet & Ankles', icon: '🦶', sub: 'Foot pain, ankle swelling, wounds', simple: 'Foot pain or wound', q: 'I have pain or wounds in my feet. Please assess.' }
};

function playLoudNotification(force = false) {
  const audio = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
  audio.volume = 1.0;
  audio.play().catch(e => {
    console.warn('Audio play blocked. Interactions needed.', e);
    if (force) {
        // Fallback: try to play on next document click
        const playOnce = () => { audio.play(); document.removeEventListener('click', playOnce); };
        document.addEventListener('click', playOnce);
    }
  });
}

// Auth & Api
function getToken() { return localStorage.getItem('token'); }
function isLoggedIn() { return !!getToken(); }

async function callApi(endpoint, method = 'GET', body = null, retries = 2) {
  const headers = {};
  if (body && !(body instanceof URLSearchParams)) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const opts = { method, headers };
  if (body) opts.body = (body instanceof URLSearchParams) ? body.toString() : JSON.stringify(body);
  if (body instanceof URLSearchParams) opts.headers['Content-Type'] = 'application/x-www-form-urlencoded';
  
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(API_URL + endpoint, opts);
      if (!res.ok) {
        const text = await res.text();
        try { const j = JSON.parse(text); throw new Error(j.detail || text); } catch (e) { throw new Error(text); }
      }
      return await res.json();
    } catch (e) {
      lastError = e;
      if (attempt < retries) await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 500));
    }
  }
  showToast(lastError.message || 'An error occurred', 'error');
  throw lastError;
}

function openLoginModal() {
  const modal = document.getElementById('login-modal');
  if (modal) modal.style.display = 'flex';
  document.getElementById('login-err').innerHTML = '';
  document.getElementById('reg-err').innerHTML = '';
  const roleSwitch = document.querySelector('.auth-role-switch');
  const registerTab = document.getElementById('tab-reg');
  const googleBtn = document.getElementById('btn-google-login');
  if (roleSwitch) roleSwitch.style.display = 'none';
  if (registerTab) registerTab.style.display = isPortalMode('patient') ? 'inline-flex' : 'none';
  if (googleBtn) googleBtn.style.display = isPortalMode('patient') ? 'inline-flex' : 'none';
  const preferredMode = isPortalMode('pharmacist') ? 'pharmacist' : isPortalMode('admin') ? 'admin' : (document.getElementById('login-username')?.dataset.loginMode || 'user');
  setLoginMode(preferredMode);
  if (!isPortalMode('patient')) switchAuthTab('login');
  else if (!pendingConditionSelection) setPatientAuthPrompt('');
}

function closeLoginModal() {
  const modal = document.getElementById('login-modal');
  if (modal) modal.style.display = 'none';
}

document.addEventListener('click', e => {
  const modal = document.getElementById('login-modal');
  if (modal && modal.style.display === 'flex' && e.target === modal) closeLoginModal();
});

function switchAuthTab(t) {
  const loginTab = document.getElementById('tab-login');
  const registerTab = document.getElementById('tab-reg');
  const loginForm = document.getElementById('form-login');
  const registerForm = document.getElementById('form-register');
  if (loginTab) loginTab.classList.toggle('on', t === 'login');
  if (registerTab) registerTab.classList.toggle('on', t === 'register');
  if (loginForm) loginForm.style.display = t === 'login' ? 'block' : 'none';
  if (registerForm) registerForm.style.display = t === 'register' && !!registerTab ? 'block' : 'none';
  const googleBtn = document.getElementById('btn-google-login');
  if (googleBtn) googleBtn.style.display = t === 'login' ? 'inline-flex' : 'none';
}

function setLoginMode(mode = 'user', trigger = null) {
  document.querySelectorAll('.auth-role-btn').forEach(btn => {
    const isActive = btn.dataset.role === mode;
    btn.classList.toggle('on', isActive);
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
  const label = document.getElementById('login-username-label'), input = document.getElementById('login-username'), help = document.getElementById('login-mode-help'), submit = document.getElementById('btn-do-login');
  // Always set the login mode on the input, even if some UI elements are missing
  if (input) input.dataset.loginMode = mode;
  if (!label || !input || !help || !submit) return;
  if (mode === 'pharmacist') { label.textContent = 'Pharmacist ID'; input.placeholder = 'Enter pharmacist ID'; help.textContent = 'Use your allocated pharmacist credentials.'; submit.textContent = 'Sign In as Pharmacist'; }
  else if (mode === 'admin') { label.textContent = 'Admin ID'; input.placeholder = 'Enter admin identifier'; help.textContent = 'Access restricted to system administrators.'; submit.textContent = 'Sign In as Admin'; }
  else { label.textContent = 'Username or Email'; input.placeholder = 'Enter credentials'; help.textContent = 'Use your patient account.'; submit.textContent = 'Sign In'; }
  if (trigger) trigger.blur();
}

async function doLogin() {
  const username = document.getElementById('login-username').value.trim().toLowerCase();
  const pass = document.getElementById('login-pass').value;
  // Use dataset.loginMode first, then fall back to portal mode
  const loginMode = document.getElementById('login-username').dataset.loginMode || (isPortalMode('pharmacist') ? 'pharmacist' : isPortalMode('admin') ? 'admin' : 'user');
  const err = document.getElementById('login-err'), btn = document.getElementById('btn-do-login');
  if (!username || !pass) { err.innerHTML = '<div class="err">Required: Username & password.</div>'; return; }
  try {
    btn.disabled = true; btn.innerHTML = 'Signing in...';
    const body = new URLSearchParams(); body.append('username', username); body.append('password', pass);
    const endpoint = loginMode === 'pharmacist' ? '/auth/pharmacist/login' : '/auth/login';
    const data = await callApi(endpoint, 'POST', body);
    localStorage.setItem('token', data.access_token);
    currentUser = username;
    closeLoginModal();
    showToast('Welcome back!', 'success');
    const sess = await callApi('/session'); currentSession = sess;
    initApp();
    if (currentSession.role === 'user') _connectPatientWebSocket();
  } catch (e) { err.innerHTML = `<div class="err">${e.message}</div>`; }
  finally { btn.disabled = false; setLoginMode(loginMode); }
}

async function doRegister() {
  const username=document.getElementById('reg-username').value.trim().toLowerCase(), email=document.getElementById('reg-email').value.trim(), fname=document.getElementById('reg-fname').value.trim(), lname=document.getElementById('reg-lname').value.trim(), pass=document.getElementById('reg-pass').value;
  const err=document.getElementById('reg-err'), btn=document.getElementById('btn-do-register');
  if(!username||!email||!fname||!lname||!pass){ err.innerHTML='<div class="err">All fields required.</div>'; return; }
  try {
    btn.disabled=true; btn.innerHTML='Creating account...';
    const data=await callApi('/auth/register','POST',{username,email,first_name:fname,last_name:lname,password:pass});
    localStorage.setItem('token',data.access_token);
    currentUser=username; closeLoginModal(); showToast('Account created!', 'success'); initApp();
  } catch(e){ err.innerHTML=`<div class="err">${e.message}</div>`; }
  finally{ btn.disabled=false; btn.innerHTML='Create Account'; }
}

function signOut() {
  stopPatientReportSync();
  localStorage.removeItem('token'); currentUser=null; currentSession={role:'guest'};
  window.location.href=getPortalHome();
}

function handleImageUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (!file.type.startsWith('image/')) {
    showToast('Please select an image file', 'error');
    return;
  }

  // Show loading toast for large images
  if (file.size > 2 * 1024 * 1024) {
    showToast('Processing image...', 'info', 1000);
  }

  const reader = new FileReader();
  reader.onload = function(e) {
    currentImageData = e.target.result;
    const previewContainer = document.getElementById('image-preview-container');
    const previewImg = document.getElementById('image-preview');
    
    if (previewImg) previewImg.src = currentImageData;
    if (previewContainer) {
      previewContainer.style.display = 'flex';
      // Smooth scroll to preview if on mobile
      if (window.innerWidth < 768) {
        previewContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    }
  };
  reader.readAsDataURL(file);
}

function clearImagePreview() {
  currentImageData = null;
  const previewContainer = document.getElementById('image-preview-container');
  if (previewContainer) previewContainer.style.display = 'none';
  const fileInput = document.getElementById('camera-input');
  if (fileInput) fileInput.value = '';
}

// Navigation & Global UI
function go(name, el) {
  const isGuest = currentSession.role === 'guest';
  const restrictedTabs = ['bodymap', 'conditions', 'redflag', 'profile', 'connect', 'history'];

  // Handle restricted access for guests
  if (restrictedTabs.includes(name) && isGuest) {
    openLoginModal();
    // Also show the restriction overlay in case they close the modal
    showGuestRestriction(name);
  } else if (restrictedTabs.includes(name)) {
    hideGuestRestriction(name);
  }

  document.querySelectorAll('.panel').forEach(p => p.classList.remove('on'));
  const target = document.getElementById('panel-' + name);
  if (target) target.classList.add('on');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('on'));
  if (el) el.classList.add('on');
  
  if (name === 'pharmacist') refreshPharmacistDashboard();
  if (name === 'admin') refreshAdminDashboard();

  // Reset scroll
  const mainContent = document.getElementById('main-content');
  if (mainContent) mainContent.scrollTop = 0;
  if (target) target.scrollTop = 0;
  window.scrollTo({ top: 0, behavior: 'auto' });
  
  closeSidebar();
}

function showGuestRestriction(name) {
  const panel = document.getElementById('panel-' + name);
  if (!panel) return;
  const prompt = panel.querySelector('.auth-prompt-overlay');
  const content = panel.querySelector('.panel-content-wrapper') || panel.querySelector(':scope > div:not(.panel-header):not(.auth-prompt-overlay)');
  
  if (prompt) prompt.style.display = 'flex';
  if (content) content.style.display = 'none';
}

function hideGuestRestriction(name) {
  const panel = document.getElementById('panel-' + name);
  if (!panel) return;
  const prompt = panel.querySelector('.auth-prompt-overlay');
  const content = panel.querySelector('.panel-content-wrapper');
  
  if (prompt) prompt.style.display = 'none';
  if (content) {
    content.style.display = 'block';
  } else {
    // If no wrapper, make sure children aren't accidentally hidden
    panel.querySelectorAll(':scope > div:not(.auth-prompt-overlay)').forEach(child => {
      if (child.style.display === 'none') child.style.display = 'block';
    });
  }
}

function goProfile(el) { go('profile', el); }
function goHistory(el) { go('history', el); }

function toggleSidebar() {
  const sb = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sb) sb.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open');
  document.body.classList.toggle('sidebar-open');
}

function closeSidebar() {
  const sb = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sb) sb.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  document.body.classList.remove('sidebar-open');
}

function toggleMobileMenu() {
  toggleSidebar();
}

window.addEventListener('resize', () => {
  if (window.innerWidth > 900) {
    closeSidebar();
  }
});

function newChat() {
  history = [];
  _chatGreetingShown = false;
  const msgs = document.getElementById('msgs');
  if (msgs) msgs.innerHTML = '';
  const input = document.getElementById('tinput');
  if (input) {
    input.value = '';
    input.style.height = 'auto'; // Reset height
  }
  _showGreeting();
  go('chat', document.getElementById('nav-chat'));
}

function _showGreeting() {
    if (_chatGreetingShown) return;
    addMsg('ai', LANGS[lang].greeting, [{ t: 'BisaRx', c: 'g' }, { t: 'BisaRx Assistant', c: 'b' }, { t: 'Multilingual', c: 'a' }]);
    _chatGreetingShown = true;
}

function updateChatWelcomeState() {
  const panel = document.getElementById('panel-chat');
  const messages = document.getElementById('msgs');
  if (!panel || !messages) return;

  const items = Array.from(messages.querySelectorAll('.msg'));
  // We show the hero when there are NO messages.
  // The first AI greeting will trigger the transition to the chat state.
  const isWelcome = items.length === 0;
  panel.classList.toggle('chat-welcome-state', isWelcome);
  
  const hero = document.getElementById('chat-welcome-hero');
  if (hero) hero.style.display = isWelcome ? 'flex' : 'none';
}

// PWA Install Logic
function triggerPwaInstall() {
  if (window.deferredPrompt) {
    window.deferredPrompt.prompt();
    window.deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        showToast('Thank you for installing BisaRx!', 'success');
      }
      window.deferredPrompt = null;
    });
  } else {
    showToast('To install: Open browser menu and select "Add to Home Screen"', 'info');
  }
}

function updateAuthUI() {
  const loggedIn = isLoggedIn();
  const authFooter = document.getElementById('auth-footer'), userFooter = document.getElementById('user-footer');
  if (authFooter) authFooter.style.display = loggedIn ? 'none' : 'block';
  if (userFooter) {
    userFooter.style.display = loggedIn ? 'block' : 'none';
    const label = document.getElementById('user-label');
    if (label) label.textContent = (currentSession.display_name || currentUser || 'User') + ' | ' + (currentSession.role || 'Guest');
  }
  const navItems = ['chat', 'bodymap', 'conditions', 'redflag', 'profile', 'connect', 'history'];
  const isDedicated = isDedicatedPortal();
  navItems.forEach(id => { const el = document.getElementById('nav-' + id); if (el) el.style.display = isDedicated ? 'none' : 'flex'; });
  const np = document.getElementById('nav-pharmacist'), na = document.getElementById('nav-admin');
  if (np) np.style.display = (currentSession.role === 'pharmacist' || isPortalMode('pharmacist')) ? 'flex' : 'none';
  if (na) na.style.display = (currentSession.role === 'admin' || isPortalMode('admin')) ? 'flex' : 'none';
}

// Patient Portal UI
function buildLang() {
  const g = document.getElementById('msgs'), c = document.getElementById('chips'), p = document.getElementById('tinput'), d = document.getElementById('disc');
  if (g) g.innerHTML = '';
  updateChatWelcomeState();
  if (c) c.innerHTML = LANGS[lang].chips.map(txt => `<div class="chip" onclick="document.getElementById('tinput').value='${txt}';send();">${txt}</div>`).join('');
  if (p) p.placeholder = LANGS[lang].placeholder;
  if (d) d.innerHTML = `<strong>${LANGS[lang].discLabel}</strong> ${LANGS[lang].disc}`;
}

function renderPrescriptionHistory(rxArray = []) {
  const h = document.getElementById('history-content'); if (!h) return;
  if (!rxArray.length) { h.innerHTML = '<div class="empty">No clinical reports yet.</div>'; return; }
  h.innerHTML = rxArray.map(rx => `
    <div class="rx-card ${rx.status.toLowerCase()}">
      <div class="rx-head"><div class="rx-title">${rx.drug_name || 'Pharmacist Review'}</div><div class="rx-date">${new Date(rx.created_at).toLocaleDateString()}</div></div>
      <div class="rx-body">
        <div class="rx-meta"><span><strong>Status:</strong> ${rx.status}</span>${rx.pharmacist_feedback ? `<p>${rx.pharmacist_feedback}</p>` : '<p class="pending">Awaiting pharmacist assessment...</p>'}</div>
      </div>
    </div>
  `).join('');
}

async function send() {
  const input = document.getElementById('tinput');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  addMsg('user', text);

  const messages = [...history, { role: 'user', content: text }];

  try {
    const payload = { messages };
    if (currentImageData) {
      payload.image_data = currentImageData;
    }
    
    const res = await callApi('/chat', 'POST', payload);
    const reply = res.reply || res.response || '';
    
    // Clear image immediately after sending
    clearImagePreview();
    
    history.push({ role: 'user', content: text }, { role: 'assistant', content: reply });
    
    const drugTags = (res.drugs || []).map(d => ({ t: d.name, c: 'g' }));
    addMsg('ai', reply, [
      { t: 'BisaRx AI', c: 'b' },
      ...drugTags
    ]);
    if (res.case_id && !isLoggedIn()) {
      _connectCaseWebSocket(res.case_id);
    }
  } catch (e) {
    addMsg('ai', 'Error connecting to brain. Please try again.');
  }
}

function addMsg(role, text, tags = []) {
  const g = document.getElementById('msgs'); if (!g) return;
  const isAi = role === 'ai';
  const m = document.createElement('div'); 
  m.className = 'msg ' + (isAi ? 'ai' : 'u');
  
  const avatar = `<div class="av ${isAi ? 'ai' : 'u'}">${isAi ? 'Rx' : 'Me'}</div>`;
  const bubble = `
    <div class="bub ${isAi ? 'ai' : 'u'}">
      <div class="bub-text">${text}</div>
      ${tags.length ? `<div class="tags" style="margin-top:10px;">${tags.map(t => `<span class="tag ${t.c}">${t.t}</span>`).join('')}</div>` : ''}
    </div>
  `;
  
  m.innerHTML = avatar + bubble;
  g.appendChild(m); g.scrollTop = g.scrollHeight;
  updateChatWelcomeState();
}

// Pharmacist Portal UI
function renderPharmacistDashboard(pending = [], assigned = [], completed = []) {
  // This function is now deprecated in favor of renderPharmaQueue
}

function renderCaseCard(c, mode) {
  return `
    <div class="ccard">
      <div class="cname">Case #${c.id} - ${c.patient_name || 'Guest'}</div>
      <div class="ctags"><span class="ctag b">${c.status}</span></div>
      ${mode === 'pending' ? `<button class="btn btn-sm" onclick="acceptCase(${c.id})">Accept Case</button>` : ''}
      ${mode === 'assigned' ? `<button class="btn btn-sm" onclick="toggleReviewForm(${c.id})">Review</button>` : ''}
    </div>
  `;
}

async function acceptCase(id) { 
  await callApi(`/pharmacist/cases/${id}/accept`, 'POST'); 
  showToast('Case accepted'); 
  const tabBtn = document.querySelector('[onclick*="assigned"]');
  if (tabBtn) showPharmaTab('assigned', tabBtn); 
  refreshPharmacistDashboard(); 
}

function showPharmaTab(tab, el) {
  ['pending', 'assigned', 'completed'].forEach(t => { const p = document.getElementById(`pharma-tab-${t}`); if (p) p.style.display = t === tab ? 'block' : 'none'; });
  const tabs = el.parentElement.querySelectorAll('.profile-tab');
  tabs.forEach(t => t.classList.remove('on'));
  el.classList.add('on');
}

async function refreshPharmacistDashboard() {
  try {
    const activeElement = document.activeElement;
    const scrollPositions = {};
    document.querySelectorAll('.pharmacist-queue').forEach(q => scrollPositions[q.id] = q.scrollTop);

    const data = await callApi('/pharmacist/dashboard');
    const s = data.stats || {};
    const p = document.getElementById('ph-stat-pending'), a = document.getElementById('ph-stat-assigned'), c = document.getElementById('ph-stat-completed');
    if (p) p.textContent = s.pending_cases || 0;
    if (a) a.textContent = s.assigned_cases || 0;
    if (c) c.textContent = s.completed_cases || 0;

    renderPharmaQueue('pharmacist-pending-queue', data.pending_cases, 'pending');
    renderPharmaQueue('pharmacist-queue', data.assigned_cases || data.in_review_cases, 'assigned');
    renderPharmaQueue('pharmacist-completed', data.completed_cases, 'completed');

    // Restore scroll positions
    Object.entries(scrollPositions).forEach(([id, pos]) => {
      const q = document.getElementById(id);
      if (q) q.scrollTop = pos;
    });

    // Try to restore focus if it was in an input that still exists
    if (activeElement && activeElement.id) {
        const newEl = document.getElementById(activeElement.id);
        if (newEl) newEl.focus();
    }
  } catch (e) { console.warn('Refresh failed', e); }
}

function renderPharmaQueue(id, cases = [], mode = 'pending') {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = cases.length ? cases.map(cs => `
    <div class="case-card pharmacist-case-card" id="case-evaluation-${cs.id}">
      <div class="dashboard-field"><label>Patient</label><div class="case-field-text">${cs.patient_name || 'Guest'}</div></div>
      <div class="dashboard-field"><label>Summary</label><div class="case-field-text case-summary-text">${cs.case_summary || 'No details'}</div></div>
      <div class="dashboard-field"><label>Status</label><div><span class="badge badge-${cs.status === 'Pending' ? 'warning' : 'success'}">${cs.status}</span></div></div>
      ${mode === 'pending' ? `<button class="btn btn-primary btn-sm" onclick="acceptCase(${cs.id})">Accept Case</button>` : ''}
      ${mode === 'assigned' ? `
        <div class="pharma-review-divider"></div>
        <div class="pharma-review-block">
          <div class="pharma-review-title">Medication Plan</div>
          <div id="drug-rows-${cs.id}" class="drug-rows">
            <div class="drug-row">
              <div class="dashboard-field drug-name-field">
                <label>Drug Name</label>
                <input type="text" class="rev-drug-name" placeholder="Enter medication name" value="${cs.drug_name && cs.drug_name !== 'Pharmacist review required' ? cs.drug_name : ''}">
              </div>
              <div class="dashboard-field drug-point-field">
                <label>Dosage and Counselling</label>
                <textarea class="rev-drug-point" placeholder="Dose, duration, counselling points, and follow-up advice" rows="4">${cs.pharmacist_feedback || ''}</textarea>
              </div>
              <button class="btn btn-danger btn-sm drug-row-remove" onclick="this.parentElement.remove()" aria-label="Remove medication row">&times;</button>
            </div>
          </div>
          <div class="pharma-review-actions">
            <button class="btn btn-sm btn-secondary" onclick="addDrugRow(${cs.id})">+ Add Drug</button>
            <button class="btn btn-sm btn-magic" onclick="fillAiSuggestion(${cs.id}, this)">AI Suggest</button>
          </div>
          <button class="btn btn-primary btn-sm pharma-submit-btn" onclick="submitReview(${cs.id})">Submit to Patient</button>
        </div>
      ` : ''}
      ${mode === 'completed' ? `
        <div class="pharma-review-divider"></div>
        <div class="dashboard-field"><label>Medication</label><div class="case-field-text">${cs.drug_name || 'N/A'}</div></div>
        <div class="dashboard-field"><label>Counselling Points</label><div class="case-field-text case-feedback-text">${cs.pharmacist_feedback || 'N/A'}</div></div>
      ` : ''}
    </div>
  `).join('') : '<div class="empty">No cases here.</div>';
}

function addDrugRow(caseId) {
  const container = document.getElementById(`drug-rows-${caseId}`);
  if (!container) return;
  const row = document.createElement('div');
  row.className = 'drug-row';
  row.innerHTML = `
    <div class="dashboard-field drug-name-field">
      <label>Drug Name</label>
      <input type="text" class="rev-drug-name" placeholder="Enter medication name">
    </div>
    <div class="dashboard-field drug-point-field">
      <label>Dosage and Counselling</label>
      <textarea class="rev-drug-point" placeholder="Dose, duration, counselling points, and follow-up advice" rows="4"></textarea>
    </div>
    <button class="btn btn-danger btn-sm drug-row-remove" onclick="this.parentElement.remove()" aria-label="Remove medication row">&times;</button>
  `;
  container.appendChild(row);
}

async function fillAiSuggestion(caseId, btn) {
  try {
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'Thinking...';
    
    const res = await callApi(`/cases/${caseId}/ai-suggest`, 'POST');
    const suggestion = res.suggestion;
    
    if (suggestion) {
      const container = document.getElementById(`drug-rows-${caseId}`);
      if (!container) return;
      
      // Clear empty rows or take the first one
      const rows = container.querySelectorAll('.drug-row');
      let targetRow = rows[0];
      
      // If the first row is already filled, add a new one
      const nameInput = targetRow.querySelector('.rev-drug-name');
      const pointInput = targetRow.querySelector('.rev-drug-point');
      
      if (nameInput.value.trim() || pointInput.value.trim()) {
        addDrugRow(caseId);
        const newRows = container.querySelectorAll('.drug-row');
        targetRow = newRows[newRows.length - 1];
      }
      
      targetRow.querySelector('.rev-drug-name').value = suggestion.drug_name || '';
      targetRow.querySelector('.rev-drug-point').value = suggestion.pharmacist_feedback || '';
      showToast('AI suggestion applied!', 'success');
    }
  } catch (e) {
    showToast('Failed to get AI suggestion', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'AI Suggest';
  }
}

async function submitReview(id) {
  const container = document.getElementById(`drug-rows-${id}`);
  if (!container) return;
  const rows = container.querySelectorAll('.drug-row');
  const drugs_list = Array.from(rows).map(row => ({
    name: row.querySelector('.rev-drug-name').value.trim(),
    point: row.querySelector('.rev-drug-point').value.trim()
  })).filter(d => d.name);

  if (drugs_list.length === 0) return showToast('Please add at least one drug', 'error');

  try {
    await callApi(`/pharmacist/review/${id}`, 'POST', {
      advice: 'Clinical review completed', // placeholder since we use drugs_list now
      drugs_list: drugs_list,
      status: 'Reviewed'
    });
    showToast('Review sent to patient!', 'success');
    refreshPharmacistDashboard();
  } catch (e) { showToast(e.message, 'error'); }
}

// Admin Portal UI
function showAdminTab(tab, el) {
  ['overview', 'pharmacists', 'users', 'cases'].forEach(t => { const p = document.getElementById(`admin-tab-${t}`); if (p) p.style.display = t === tab ? 'block' : 'none'; });
  const tabs = el.parentElement.querySelectorAll('.profile-tab');
  tabs.forEach(t => t.classList.remove('on'));
  el.classList.add('on');
}

async function refreshAdminDashboard() {
  try {
    const data = await callApi('/admin/dashboard');
    const s = data.stats || {};
    const u = document.getElementById('admin-total-users'), ph = document.getElementById('admin-total-pharmacists'), pc = document.getElementById('admin-pending-cases'), cc = document.getElementById('admin-completed-cases');
    if (u) u.textContent = s.total_users || 0;
    if (ph) ph.textContent = s.total_pharmacists || 0;
    if (pc) pc.textContent = s.pending_cases || 0;
    if (cc) cc.textContent = s.reviewed_cases || 0;

    renderAdminPharmacists(data.pharmacists);
    renderAdminUsers(data.all_users || data.recent_users);
    renderAdminCases(data.cases);
  } catch (e) { console.warn('Admin refresh failed', e); }
}

function renderAdminPharmacists(list = []) {
  const el = document.getElementById('admin-pharmacists-list');
  if (!el) return;
  el.innerHTML = list.length ? list.map(p => `
    <div class="case-card" style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
      <div><strong>${p.full_name}</strong> (${p.username})<br><small>${p.email} | ${p.license_number || 'No License'}</small></div>
      <div style="display:flex; gap:8px;">
        ${!p.is_verified ? `<button class="btn btn-sm" onclick="verifyPharmacist(${p.id})">Verify</button>` : '<span class="badge badge-success">Verified</span>'}
        <button class="btn btn-danger btn-sm" onclick="deletePharmacist(${p.id})">Delete</button>
      </div>
    </div>
  `).join('') : '<div class="empty">No pharmacists found.</div>';
}

function renderAdminUsers(list = []) {
  const el = document.getElementById('admin-users-list');
  if (!el) return;
  el.innerHTML = list.length ? list.map(u => `<div class="ccard"><div><strong>${u.username}</strong><br><small>${u.email}</small></div></div>`).join('') : '<div class="empty">No users found.</div>';
}

function renderAdminCases(cases = []) {
  const c = document.getElementById('admin-cases-list');
  if (c) c.innerHTML = cases.length ? cases.map(cs => `<div class="ccard"><div class="cname">#${cs.id} | ${cs.patient_name}</div><div class="cdrug">Status: ${cs.status}</div></div>`).join('') : '<div class="empty">No cases found.</div>';
}

async function createPharmacist() {
  const name = document.getElementById('admin-ph-name').value, 
        user = document.getElementById('admin-ph-username').value, 
        email = document.getElementById('admin-ph-email').value, 
        pass = document.getElementById('admin-ph-password').value,
        license = document.getElementById('admin-ph-license').value;
  if (!name || !user || !email || !pass || !license) return showToast('Fill all fields including license', 'error');
  try {
    await callApi('/admin/pharmacists', 'POST', { 
      full_name: name, 
      username: user, 
      email, 
      password: pass,
      license_number: license,
      location: 'Main Pharmacy'
    });
    showToast('Pharmacist created', 'success');
    refreshAdminDashboard();
  } catch (e) { showToast(e.message, 'error'); }
}

async function verifyPharmacist(id) { await callApi(`/admin/pharmacists/${id}/verify`, 'POST'); showToast('Pharmacist verified'); refreshAdminDashboard(); }
async function deletePharmacist(id) { if (confirm('Delete this account?')) { await callApi(`/admin/pharmacists/${id}`, 'DELETE'); refreshAdminDashboard(); } }

// Initialization
async function fetchSessionContext() { try { currentSession = await callApi('/session'); currentUser = currentSession.username; } catch (e) { currentSession = { role: 'guest' }; } }

function cleanupPatientPortalDuplicates() {
  if (!isPortalMode('patient')) return;
  ['nav-pharmacist', 'nav-admin', 'panel-pharmacist', 'panel-admin'].forEach(id => { const el = document.getElementById(id); if (el) el.remove(); });
}

async function initApp() {
  showLoading('Initializing...');
  try {
    await fetchSessionContext();
    cleanupPatientPortalDuplicates();
    cleanupDedicatedPortalLayout();
    
    if (isDedicatedPortal() && currentSession.role === 'guest') { 
      setDedicatedPortalVisibility(false); 
      updateAuthUI(); 
      switchAuthTab('login'); 
      openLoginModal(); 
      return; 
    }
    
    setDedicatedPortalVisibility(true);
    updateAuthUI();
    
    if (!isDedicatedPortal()) {
      buildLang();
      try {
        const ref = await callApi('/reference');
        window.FALLBACK_CONDITIONS = ref.conditions;
        window.FALLBACK_REDFLAGS = ref.red_flags;
      } catch (e) { console.warn('Using fallback data'); }
      // Build initial grids
      const g = document.getElementById('conditions-grid');
      if (g) g.innerHTML = window.FALLBACK_CONDITIONS.map(c => `<div class="ccard" onclick="handleConditionSelection(${JSON.stringify(c).replace(/"/g, '&quot;')})"><div class="cname">${c.name}</div><div class="cdrug">${c.drug}</div></div>`).join('');
      const b = document.getElementById('rfbody');
      if (b) b.innerHTML = window.FALLBACK_REDFLAGS.map(rf => `<div class="rfbox"><div class="rftitle">⚠️ ${rf.condition}</div>${rf.flags.map(f => `<div class="rfitem">${f}</div>`).join('')}</div>`).join('');
    }
    
    if (currentSession.role === 'user') loadProfileData();
    if (currentSession.role === 'pharmacist') { 
      go('pharmacist', document.getElementById('nav-pharmacist')); 
      refreshPharmacistDashboard(); 
      _connectPharmacistWebSocket(); 
    }
    if (currentSession.role === 'admin') { go('admin', document.getElementById('nav-admin')); refreshAdminDashboard(); }

    if (!isDedicatedPortal() && !_chatGreetingShown) {
      _showGreeting();
    }

    // Auto-expanding chat input
    const tinput = document.getElementById('tinput');
    if (tinput) {
        tinput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }

    // Check for PWA after a short delay
    setTimeout(() => {
        if (!window.matchMedia('(display-mode: standalone)').matches && /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
            showToast('Install BisonRx for a better experience', 'info', 8000);
        }
    }, 5000);

  } finally {
    hideLoading();
  }
}

function handleConditionSelection(condition) {
  if (currentSession.role === 'user') {
    const nav = document.getElementById('nav-chat');
    if (nav) go('chat', nav);
    document.getElementById('tinput').value = condition.q || `Tell me about ${condition.name}`;
    send();
    return;
  }
  pendingConditionSelection = condition;
  openLoginModal();
  switchAuthTab('register');
  setPatientAuthPrompt('Create an account or sign in to save your clinical information for future diagnosis. This helps the pharmacist review your case faster.');
}

function setPatientAuthPrompt(message = '') {
  if (!isPortalMode('patient')) return;
  const loginHelp = document.getElementById('login-mode-help');
  const loginErr = document.getElementById('login-err');
  const regErr = document.getElementById('reg-err');
  if (loginHelp) loginHelp.textContent = message || 'Use your patient account to continue.';
  if (loginErr) loginErr.innerHTML = message ? `<div class="ok">${message}</div>` : '';
  if (regErr) regErr.innerHTML = message ? `<div class="ok">${message}</div>` : '';
}

async function loadProfileData(){
  if(!isLoggedIn()) return;
  try{
    const data=await callApi('/profile');
    renderPrescriptionHistory(data.prescriptions || []);
    const pc=document.getElementById('profile-content'), pp=document.getElementById('profile-auth-prompt');
    if(pc) pc.style.display='block'; if(pp) pp.style.display='none';
    const hc=document.getElementById('history-content'), hp=document.getElementById('history-auth-prompt');
    if(hc) hc.style.display='block'; if(hp) hp.style.display='none';
  }catch(e){ console.warn('Failed to load profile',e); }
}

function stopPatientReportSync() { if (patientReportSyncTimer) { clearInterval(patientReportSyncTimer); patientReportSyncTimer = null; } }

function _connectPatientWebSocket() {
  if (!isLoggedIn() || isPortalMode('pharmacist') || isPortalMode('admin')) return;
  if (_patientWs && _patientWs.readyState < 2) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws', userId = currentSession.user_id || '';
  if (!userId) return;
  try {
    _patientWs = new WebSocket(`${proto}://${location.host}/ws/patient/${userId}`);
    _patientWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'case_updated' && data.pharmacist_feedback) {
          if (data.play_loud_sound) playLoudNotification(true);
          showToast('Pharmacist result received!', 'success', 8000);
          const resultMsg = [
            data.pharmacist_feedback,
            data.drug_name ? `**Medication:** ${data.drug_name}` : '',
            data.referral_advice ? `**Referral:** ${data.referral_advice}` : '',
            data.follow_up_instructions ? `**Follow-up:** ${data.follow_up_instructions}` : '',
          ].filter(Boolean).join('\n\n');
          addMsg('ai', '📢 **Pharmacist Review Complete:**\n\n' + resultMsg, [{ t: 'Results', c: 'g' }, { t: 'Pharmacist', c: 'b' }]);
          if (isLoggedIn()) callApi('/profile').then(d => renderPrescriptionHistory(d.prescriptions)).catch(() => {});
        } else if (data.type === 'case_updated') {
           showToast('Case updated.', 'info');
        }
      } catch (_) { }
    };
    _patientWs.onclose = () => { 
       _patientWs = null; 
       setTimeout(_connectPatientWebSocket, 5000); 
    };
  } catch (_) { }
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
        <div class="cec-header-title">Clinical Evaluation Report</div>
      </div>
      
      ${drugName ? `
      <div class="cec-section">
        <div class="cec-label">Prescription / Medication</div>
        <div class="cec-drug-box">
          <div class="cec-drug-name">${drugName}</div>
        </div>
      </div>
      ` : ''}

      <div class="cec-section">
        <div class="cec-label">Pharmacist Guidance</div>
        <div class="cec-content">${feedback || 'No specific instructions provided.'}</div>
      </div>

      ${referral ? `
      <div class="cec-section">
        <div class="cec-label">Referral / Critical Action</div>
        <div class="cec-referral">${referral}</div>
      </div>
      ` : ''}

      ${followUp ? `
      <div class="cec-section">
        <div class="cec-label">Follow-up Instructions</div>
        <div class="cec-content">${followUp}</div>
      </div>
      ` : ''}
    </div>
  `;
}

function _connectCaseWebSocket(caseId) {
  if (isPortalMode('pharmacist') || isPortalMode('admin')) return;
  if (_caseWs && _caseWs.readyState < 2) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  try {
    _caseWs = new WebSocket(`${proto}://${location.host}/ws/case/${caseId}`);
    _caseWs.onopen = () => showToast('Connected to real-time pharmacist updates.', 'info', 2000);
    _caseWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'case_updated' && data.pharmacist_feedback) {
          if (data.play_loud_sound) playLoudNotification(true);
          showToast('Pharmacist evaluation received!', 'success', 8000);
          
          const evaluationHTML = generateEvaluationHTML(data);
          addMsg('ai', evaluationHTML, [{ t: 'Clinical Report', c: 'g' }, { t: 'Pharmacist Verified', c: 'b' }]);
          
          _caseWs.onclose = null; // Don't reconnect after success
          _caseWs.close();
        } else if (data.type === 'case_updated') {
           showToast('Case status updated.', 'info');
        }
      } catch (_) { }
    };
    _caseWs.onclose = () => { 
      _caseWs = null; 
      // Reconnect if we're still waiting for pharmacist_feedback
      setTimeout(() => _connectCaseWebSocket(caseId), 3000); 
    };
  } catch (_) { }
}

function _connectPharmacistWebSocket() {
  if (currentSession.role !== 'pharmacist') return;
  if (_pharmacistWs && _pharmacistWs.readyState < 2) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  try {
    _pharmacistWs = new WebSocket(`${proto}://${location.host}/ws/pharmacist`);
    _pharmacistWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'case_created') {
          showToast('New patient case ready for review!', 'info');
          playLoudNotification(true);
          refreshPharmacistDashboard();
        }
      } catch (_) { }
    };
    _pharmacistWs.onclose = () => { 
      _pharmacistWs = null; 
      setTimeout(_connectPharmacistWebSocket, 5000); 
    };
  } catch (_) { }
}

function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = (el.scrollHeight) + 'px';
}

// Start
window.addEventListener('DOMContentLoaded', initApp);
