const API_URL = '/api';

// Smooth scroll helper
function smoothScrollTo(elementId) {
  const el = document.getElementById(elementId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// Loading indicator
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

// Toast notifications
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
  const colors = {
    success: 'linear-gradient(135deg,#38a169,#2f855a)',
    error: 'linear-gradient(135deg,#e53e3e,#c53030)',
    info: 'linear-gradient(135deg,var(--primary-light),var(--primary))',
    warning: 'linear-gradient(135deg,#ed8936,#dd6b20)'
  };
  toast.style.cssText = `
    padding:14px 20px;border-radius:14px;color:white;font-weight:600;font-size:.9rem;
    background:${colors[type] || colors.info};box-shadow:0 12px 28px rgba(0,0,0,0.15);
    animation:slideIn .3s ease;max-width:320px;
  `;
  toast.textContent = message;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Fallback data when API is unavailable
window.FALLBACK_CONDITIONS = [
  {name:'Malaria / Fever',drug:'Artemether + Lumefantrine',tags:[{t:'Coartem®',c:'g'},{t:'6 doses/3 days',c:'b'},{t:'With food',c:'a'}],q:'Tell me about malaria symptoms and Coartem treatment.'},
  {name:'Headache',drug:'Paracetamol / Ibuprofen',tags:[{t:'Tension',c:'b'},{t:'Migraine',c:'b'},{t:'Refer if severe',c:'r'}],q:'Headache assessment and first-line treatment?'},
  {name:'Diarrhea',drug:'ORS + Zinc 10–20mg',tags:[{t:'Rehydration',c:'g'},{t:'Zinc',c:'b'},{t:'Metronidazole if amoebic',c:'a'}],q:'Diarrhea management advice.'},
  {name:'Cough / URTI',drug:'Steam / Guaifenesin',tags:[{t:'Fluids',c:'g'},{t:'Antibiotic if bacterial',c:'a'},{t:'Refer if SOB',c:'r'}],q:'Cough and cold management?'},
  {name:'Abdominal Pain',drug:'Antacid / Omeprazole',tags:[{t:'Gastritis',c:'b'},{t:'NSAID for cramps',c:'g'},{t:'Refer if severe',c:'r'}],q:'Abdominal pain assessment?'},
  {name:'Skin Rash',drug:'Hydrocortisone / Clotrimazole',tags:[{t:'Allergic',c:'a'},{t:'Fungal',c:'b'},{t:'Antihistamine',c:'g'}],q:'Skin rash first-line treatment?'},
  {name:'Urinary Complaints',drug:'Nitrofurantoin / Ciprofloxacin',tags:[{t:'UTI',c:'b'},{t:'Refer if pregnant',c:'r'},{t:'Fluids',c:'g'}],q:'Urinary tract complaint management?'},
  {name:'Hypertension',drug:'Amlodipine 5mg OD',tags:[{t:'BP monitoring',c:'b'},{t:'Adherence',c:'g'},{t:'Refer if uncontrolled',c:'r'}],q:'Hypertension counseling guidelines?'},
  {name:'Diabetes',drug:'Metformin (first-line)',tags:[{t:'Type 2 DM',c:'b'},{t:'Monitor glucose',c:'g'},{t:'Refer if uncontrolled',c:'a'}],q:'Diabetes medication counseling?'},
  {name:'Pain / Inflammation',drug:'Paracetamol / Diclofenac gel',tags:[{t:'NSAID',c:'b'},{t:'Topical option',c:'g'},{t:'Avoid overuse',c:'a'}],q:'Pain and inflammation management?'}
];

window.FALLBACK_REDFLAGS = [
  {condition:'Malaria / Severe Fever',flags:['Cannot keep oral medication down','Confusion, convulsions, or severe weakness','Yellowing of eyes or dark urine','Fever lasting more than 3 days despite treatment','Pregnant or infant under 6 months']},
  {condition:'Head / Neurological',flags:['Sudden severe thunderclap headache','Neck stiffness with fever','Vision changes or slurred speech','Headache after head injury']},
  {condition:'Breathing / Chest',flags:['Difficulty breathing at rest','Coughing blood','Rapid breathing in children','Productive cough with fever over 3 days']},
  {condition:'Stomach / Abdomen',flags:['Severe dehydration — sunken eyes, no urine','Blood or mucus in stool','Rigid board-like abdomen','Multiple household members ill']},
  {condition:'General Danger Signs',flags:['Altered consciousness or unconsciousness','Uncontrolled bleeding','Pregnancy with acute serious illness','Patient cannot stand or self-care']}
];

// Mobile Menu Toggle
function toggleMobileMenu() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (!sidebar || !overlay) return;
  const isOpen = sidebar.classList.toggle('open');
  overlay.classList.toggle('open', isOpen);
  document.body.classList.toggle('menu-open', isOpen && window.innerWidth <= 768);
}

function closeMobileMenu() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  document.body.classList.remove('menu-open');
}

document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  const mobileBtn = document.querySelector('.mobile-menu-btn');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar && mobileBtn && sidebar.classList.contains('open')) {
    if (!sidebar.contains(e.target) && !mobileBtn.contains(e.target)) {
      closeMobileMenu();
    }
  }
});

window.addEventListener('resize', () => {
  if (window.innerWidth > 768) closeMobileMenu();
});

let currentUser = null;
let lang = 'en', history = [], ttsOn = false, isRecording = false, recognition = null;
const synth = window.speechSynthesis;

const LANGS = {
  en:{
    greeting:"What are your symptoms? Describe what you're experiencing and how long it has been going on.",
    chips:["I have a headache","Stomach pain","I feel feverish","I have a cough","My child is sick","Skin rash"],
    placeholder:"Describe your symptoms...",
    disc:"For general guidance only. Consult a licensed pharmacist or doctor for medical decisions.",
    discLabel:"Note:"
  },
  tw:{
    greeting:"Wo yareɛ bɛn na ɛwɔ wo? Ka kyerɛ me sɛdeɛ wo te wo ho ne bere a ɛdii so.",
    chips:["Me ti yɛ me yaw","Me yafunu yɛ me yaw","Mewɔ atiridiinini","Mewɔ ekoɔ","Me ba yareɛ","Honam yareɛ"],
    placeholder:"Ka me nkyɛn sɛdeɛ wo te wo ho...",
    disc:"Wɔ atwerɛ wɔ standard health guidelines so. Ɛnsesa oduruyɛfo anaasɛ ɔdɔkotaa.",
    discLabel:"Nkɔmmɔdie:"
  },
  ha:{
    greeting:"Mene ne alamu ku? Bayyana yadda kuke ji da tsawon lokaci.",
    chips:["Ina da ciwon kai","Ciki na yi mini ciwo","Ina da zazzabi","Ina da tari","Ɗana ba shi da lafiya","Ina da kuraje"],
    placeholder:"Bayyana alamun ku...",
    disc:"Jagora ne kawai. Tuntuɓi likitan magani ko likita.",
    discLabel:"Gargaɗi:"
  },
  fr:{
    greeting:"Quels sont vos symptômes? Décrivez ce que vous ressentez et depuis combien de temps.",
    chips:["J'ai mal à la tête","Douleur abdominale","J'ai de la fièvre","Je tousse","Mon enfant est malade","Éruption cutanée"],
    placeholder:"Décrivez vos symptômes...",
    disc:"Conseils généraux seulement. Consultez un pharmacien ou médecin agréé.",
    discLabel:"Note:"
  }
};

function getSpeechLang() {
  if (lang === 'fr') return 'fr-FR';
  if (lang === 'ha') return 'ha-NG';
  if (lang === 'tw') return 'ak-GH';
  return 'en-US';
}

const ZONES={
  head:{title:'Head & Brain',icon:'🤕',sub:'Headache, dizziness, fever, vision changes',simple:'Head pain or dizziness',q:'I have pain in my head. Please assess.'},
  throat:{title:'Throat & Neck',icon:'😣',sub:'Sore throat, difficulty swallowing, neck stiffness',simple:'Throat or neck problem',q:'I have throat or neck discomfort. Please assess.'},
  chest:{title:'Chest & Lungs',icon:'😮‍💨',sub:'Cough, shortness of breath, chest pain',simple:'Chest pain or breathing problem',q:'I have chest pain or breathing difficulty. Please assess.'},
  abdomen:{title:'Stomach',icon:'🤢',sub:'Stomach pain, nausea, vomiting, diarrhea',simple:'Stomach or belly pain',q:'I have abdominal pain or stomach discomfort. Please assess.'},
  arm:{title:'Arms & Joints',icon:'💪',sub:'Arm pain, joint swelling, muscle aches',simple:'Arm or joint pain',q:'I have pain in my arms or joints. Please assess.'},
  lower:{title:'Lower Abdomen',icon:'🚻',sub:'Lower cramps, urinary problems, menstrual pain',simple:'Lower belly or urine problem',q:'I have lower abdominal or urinary symptoms. Please assess.'},
  leg:{title:'Legs',icon:'🦵',sub:'Leg pain, swelling, muscle weakness',simple:'Leg pain or swelling',q:'I have pain or swelling in my legs. Please assess.'},
  foot:{title:'Feet & Ankles',icon:'🦶',sub:'Foot pain, ankle swelling, wounds',simple:'Foot pain or wound',q:'I have pain or wounds in my feet. Please assess.'}
};

// AUTH helper
function getToken() { return localStorage.getItem('token'); }
function isLoggedIn() { return !!getToken(); }

async function callApi(endpoint, method='GET', body=null, retries=2) {
  const headers = {};
  if(body && !(body instanceof URLSearchParams)) headers['Content-Type']='application/json';
  const token = getToken();
  if(token) headers['Authorization'] = `Bearer ${token}`;
  const opts = {method, headers};
  if(body) {
    if(body instanceof URLSearchParams) opts.body = body.toString();
    else opts.body = JSON.stringify(body);
    if(body instanceof URLSearchParams) opts.headers['Content-Type']='application/x-www-form-urlencoded';
  }
  let lastError;
  for(let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(API_URL+endpoint, opts);
      if(!res.ok) {
        const text = await res.text();
        try{ const j=JSON.parse(text); throw new Error(j.detail || text); }catch(e){ throw new Error(text); }
      }
      return await res.json();
    } catch(e) {
      lastError = e;
      if(attempt < retries) await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 500));
    }
  }
  showToast(lastError.message || 'An error occurred', 'error');
  throw lastError;
}

// AUTH UI
function openLoginModal() {
  document.getElementById('login-modal').style.display='flex';
  document.getElementById('login-err').innerHTML='';
  document.getElementById('reg-err').innerHTML='';
  setLoginMode(document.getElementById('login-username')?.dataset.loginMode || 'user');
}
function closeLoginModal() {
  document.getElementById('login-modal').style.display='none';
}
// Close modal clicking outside
document.addEventListener('click', function(e) {
  const modal = document.getElementById('login-modal');
  if(modal && modal.style.display === 'flex' && e.target === modal) closeLoginModal();
});

function switchAuthTab(t){
  document.getElementById('tab-login').classList.toggle('on',t==='login');
  document.getElementById('tab-reg').classList.toggle('on',t==='register');
  document.getElementById('form-login').style.display=t==='login'?'block':'none';
  document.getElementById('form-register').style.display=t==='register'?'block':'none';
  const googleBtn = document.getElementById('btn-google-login');
  if (googleBtn) googleBtn.style.display = t === 'login' ? 'inline-flex' : 'none';
}

function setLoginMode(mode = 'user', trigger = null) {
  document.querySelectorAll('.auth-role-btn').forEach(btn => {
    const isActive = btn.dataset.role === mode;
    btn.classList.toggle('on', isActive);
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
  const label = document.getElementById('login-username-label');
  const input = document.getElementById('login-username');
  const help = document.getElementById('login-mode-help');
  const submit = document.getElementById('btn-do-login');
  if (!label || !input || !help || !submit) return;

  if (mode === 'pharmacist') {
    label.textContent = 'Clinician Username or Email';
    input.placeholder = 'Enter clinician username or email';
    help.textContent = 'Clinicians use the clinician account created and verified by an admin.';
    submit.textContent = 'Sign In as Clinician';
  } else if (mode === 'admin') {
    label.textContent = 'Admin Username or Email';
    input.placeholder = 'Enter admin username or email';
    help.textContent = 'Admins use the seeded admin credentials from environment setup or local bootstrap.';
    submit.textContent = 'Sign In as Admin';
  } else {
    label.textContent = 'Username or Email';
    input.placeholder = 'Enter username or email';
    help.textContent = 'Patients and admins can sign in with username or email.';
    submit.textContent = 'Sign In';
  }

  input.dataset.loginMode = mode;
  if (trigger) trigger.blur();
}

function checkStrength(pw){
  const fill=document.getElementById('strength-fill'),lbl=document.getElementById('strength-label');
  let s=0;if(pw.length>=6)s++;if(pw.length>=10)s++;if(/[A-Z]/.test(pw))s++;if(/[0-9]/.test(pw))s++;if(/[^a-zA-Z0-9]/.test(pw))s++;
  fill.style.width=Math.round((s/5)*100)+'%';
  if(s<=1){fill.style.background='var(--danger)';lbl.textContent='Weak';}
  else if(s<=3){fill.style.background='var(--warning)';lbl.textContent='Fair';}
  else{fill.style.background='var(--primary)';lbl.textContent='Strong';}
}

async function doLogin(){
  const username=document.getElementById('login-username').value.trim().toLowerCase();
  const pass=document.getElementById('login-pass').value;
  const loginMode=document.getElementById('login-username').dataset.loginMode || 'user';
  const err=document.getElementById('login-err');
  const btn=document.getElementById('btn-do-login');
  if(!username||!pass){err.innerHTML='<div class="err">Enter username and password.</div>';return;}
  try{
    btn.disabled=true;
    btn.innerHTML = loginMode === 'admin' ? 'Signing in as Admin...' : loginMode === 'pharmacist' ? 'Signing in as Clinician...' : 'Signing in...';
    const body=new URLSearchParams();body.append('username',username);body.append('password',pass);
    let endpoint = '/auth/login';
    if(loginMode === 'pharmacist') endpoint = '/auth/pharmacist/login';
    
    const data=await callApi(endpoint,'POST',body);
    localStorage.setItem('token',data.access_token);
    currentUser=username;
    closeLoginModal();
    showToast('Welcome back!', 'success');
    initApp();
  }catch(e){err.innerHTML=`<div class="err">${e.message}</div>`;}
  finally{btn.disabled=false;setLoginMode(loginMode);}
}

function doGoogleLogin(){window.location.href='/api/auth/google/login';}

async function doRegister(){
  const username=document.getElementById('reg-username').value.trim().toLowerCase();
  const email=document.getElementById('reg-email').value.trim();
  const fname=document.getElementById('reg-fname').value.trim();
  const lname=document.getElementById('reg-lname').value.trim();
  const pass=document.getElementById('reg-pass').value;
  const err=document.getElementById('reg-err');
  const btn=document.getElementById('btn-do-register');
  
  if(!username||!email||!fname||!lname||!pass){err.innerHTML='<div class="err">Fill all fields.</div>';return;}

  try{
    btn.disabled=true;
    btn.innerHTML='Creating account...';
    const payload={username,email,first_name:fname,last_name:lname,password:pass};
    const data=await callApi('/auth/register','POST',payload);
    localStorage.setItem('token',data.access_token);
    currentUser=username;
    closeLoginModal();
    showToast('Account created successfully!', 'success');
    initApp();
  }catch(e){err.innerHTML=`<div class="err">${e.message}</div>`;}
  finally{btn.disabled=false;btn.innerHTML='Create Account';}
}

function signOut(){localStorage.removeItem('token');currentUser=null;window.location.reload();}

function updateAuthUI(){
  const loggedIn = isLoggedIn();
  const authFooter = document.getElementById('auth-footer');
  const userFooter = document.getElementById('user-footer');
  if(authFooter) authFooter.style.display = loggedIn ? 'none' : 'block';
  if(userFooter) {
    userFooter.style.display = loggedIn ? 'block' : 'none';
    const label = document.getElementById('user-label');
    if(label && currentUser) label.textContent = currentUser;
  }
}

function consumeTokenFromUrl(){
  const url=new URL(window.location.href);
  const token=url.searchParams.get('token');
  if(!token)return null;
  localStorage.setItem('token',token);
  url.searchParams.delete('token');
  window.history.replaceState({},document.title,url.toString());
  return token;
}

async function loadProfileData(){
  if(!isLoggedIn()) return;
  try{
    const data=await callApi('/profile');
    loadPersonalForm(data.profile);
    loadMedicalForm(data.medical,data.conditions,data.allergies);
    loadMedsList(data.medications);
    loadEmergencyForm(data.emergency);
    refreshOverview(data);
    renderPrescriptionHistory(data.prescriptions);
    // Show profile content, hide prompt
    const pc=document.getElementById('profile-content');
    const pp=document.getElementById('profile-auth-prompt');
    if(pc) pc.style.display='block';
    if(pp) pp.style.display='none';
    const hc=document.getElementById('history-content');
    const hp=document.getElementById('history-auth-prompt');
    if(hc) hc.style.display='block';
    if(hp) hp.style.display='none';
  }catch(e){
    console.warn('Failed to load profile',e);
  }
}

async function initApp(){
  updateAuthUI();
  buildLang();
  try{
    const refData=await callApi('/reference');
    buildConditions(refData.conditions);
    buildRedFlags(refData.red_flags);
  }catch(e){
    console.warn('Failed to load reference data, using defaults',e);
    buildConditions(window.FALLBACK_CONDITIONS||[]);
    buildRedFlags(window.FALLBACK_REDFLAGS||[]);
  }
  if(isLoggedIn()){
    await loadProfileData();
  } else {
    // Show prompts for auth-required sections
    const pc=document.getElementById('profile-content');
    const pp=document.getElementById('profile-auth-prompt');
    if(pc) pc.style.display='none';
    if(pp) pp.style.display='block';
    const hc=document.getElementById('history-content');
    const hp=document.getElementById('history-auth-prompt');
    if(hc) hc.style.display='none';
    if(hp) hp.style.display='block';
  }
  updatePharmacistUI();
  refreshPharmacistDashboard();
  addMsg('ai',LANGS[lang].greeting,[{t:'BisaRx',c:'g'},{t:'Clinical AI',c:'b'},{t:'Multilingual',c:'a'}]);
}

window.onload = async () => {
  const token = consumeTokenFromUrl();
  if(token){
    try{
      const data = await callApi('/profile');
      // pre-populate profile data
      currentUser = data.username || '';
    }catch(e){
      localStorage.removeItem('token');
    }
  }
  initApp();
};

function buildLang(){
  const L=LANGS[lang];
  document.getElementById('chat-title').textContent=lang==='en'?'BisaRx AI Pharmacist':lang==='tw'?'BisaRx AI Oduruyɛfo':lang==='ha'?'BisaRx AI Likitan Magani':'BisaRx Pharmacien IA';
  document.getElementById('chat-sub').textContent='Direct clinical guidance · Voice · Multilingual';
  document.getElementById('disc-label').textContent=L.discLabel;
  document.getElementById('disc-text').textContent=L.disc;
  document.getElementById('tinput').placeholder=L.placeholder;
  document.getElementById('lang-badge').textContent=lang.toUpperCase();
  const chipsEl=document.getElementById('chips');chipsEl.innerHTML='';
  L.chips.forEach(c=>{
    const d=document.createElement('div');
    d.className='chip';d.textContent=c;
    d.onclick=()=>{document.getElementById('tinput').value=c;chipsEl.style.display='none';send();};
    chipsEl.appendChild(d);
  });
}
function setLang(l,el){lang=l;document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('on'));el.classList.add('on');buildLang();}

function go(name,el){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('on'));
  document.getElementById('panel-'+name).classList.add('on');
  if(el)el.classList.add('on');
  closeMobileMenu();
}

function goProfile(el){
  go('profile',el);
}

function goHistory(el){
  go('history',el);
}

// VISUAL MODE & ACCESSIBILITY
let visualMode = false;
function toggleVisualMode() {
  visualMode = !visualMode;
  const container = document.getElementById('visual-icons-container');
  const btn = document.getElementById('toggle-visual');
  container.style.display = visualMode ? 'block' : 'none';
  btn.classList.toggle('on', visualMode);
  btn.innerHTML = visualMode ? 'Exit Visual Mode &#x2715;' : 'Visual Assistance &#128065;';
  if (visualMode) speakGuidance("Tap the icon that shows what you are feeling.");
}

function speakGuidance(txt) {
  if (!synth) return;
  synth.cancel();
  const utt = new SpeechSynthesisUtterance(txt);
  utt.rate = 0.9; utt.lang = lang === 'en' ? 'en-GH' : 'ak-GH';
  synth.speak(utt);
}

function selectVisualSymptom(symp) {
  addMsg('user', `I am feeling ${symp} (Selection from Visual Map)`);
  speakGuidance(`Reviewing your ${symp}. Sending this case to a pharmacist for urgent delivery.`);
  // Fast-track: send directly to pharmacit
  history.push({role: 'user', content: `URGENT VISUAL SELECTION: I have ${symp}. Please review and provide treatment for fast delivery.`});
  send();
}

// CHAT
function addMsg(role,text,tags,msgId=null){
  const c=document.getElementById('msgs'),d=document.createElement('div');
  d.className='msg'+(role==='user'?' u':'');
  const messageId=msgId||'msg_'+Date.now();
  const tagsHtml=tags?`<div class="tr">${tags.map(t=>`<span class="bt ${t.c}">${t.t}</span>`).join('')}</div>`:'';
  const voiceBtnHtml=role==='ai'?`<button class="msg-voice-btn" onclick="speakMsg('${messageId}', this)" title="Listen">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
    <span>Listen</span>
  </button>`:'';
  const formattedText=role==='ai'&&window.marked?marked.parse(text):text.replace(/\n/g,'<br>');
  d.innerHTML=`<div class="av ${role==='user'?'u':'ai'}">${role==='user'?'You':'Bx'}</div>
  <div class="bub ${role==='user'?'u':'ai'}" id="${messageId}">
    <div class="bub-text">${formattedText}${tagsHtml}</div>
    ${voiceBtnHtml}
  </div>`;
  c.appendChild(d);
  // Smooth scroll to bottom
  requestAnimationFrame(() => {
    c.scrollTo({
      top: c.scrollHeight,
      behavior: 'smooth'
    });
  });
  return messageId;
}

function speakMsg(msgId,btn){
  const msgEl=document.getElementById(msgId);
  if(!msgEl)return;
  const text=msgEl.querySelector('.bub-text').textContent;
  if(btn.classList.contains('speaking')){
    if(synth)synth.cancel();
    btn.classList.remove('speaking');
    btn.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg><span>Listen</span>`;
  }else{
    if(synth)synth.cancel();
    document.querySelectorAll('.msg-voice-btn.speaking').forEach(b=>{
      b.classList.remove('speaking');
      b.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg><span>Listen</span>`;
    });
    btn.classList.add('speaking');
    btn.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg><span>Stop</span>`;
    const utt=new SpeechSynthesisUtterance(text.replace(/<[^>]*>/g,''));
    utt.rate=0.9;utt.pitch=1.0;
    utt.lang=lang==='fr'?'fr-FR':lang==='ha'?'ha-NG':lang==='tw'?'ak-GH':'en-GH';
    utt.onend=()=>{btn.classList.remove('speaking');btn.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg><span>Listen</span>`;};
    utt.onerror=()=>{btn.classList.remove('speaking');};
    synth.speak(utt);
  }
}

function showTyping(){const c=document.getElementById('msgs'),d=document.createElement('div');d.className='msg';d.id='typing';d.innerHTML=`<div class="av ai">Bx</div><div class="bub ai" style="padding:7px 13px"><div class="typing"><span></span><span></span><span></span></div></div>`;c.appendChild(d);requestAnimationFrame(()=>c.scrollTo({top:c.scrollHeight,behavior:'smooth'}));}
function rmTyping(){const e=document.getElementById('typing');if(e)e.remove();}
function autoR(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,100)+'px';}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}

function addDrugCards(drugs){
  const c=document.getElementById('msgs');
  const wrapper=document.createElement('div');
  wrapper.className='drug-cards-wrapper';
  wrapper.innerHTML=`<div class="drug-cards-header"><span class="drug-cards-icon">&#128138;</span> Potential treatments for pharmacist review</div>`;;
  drugs.forEach(drug=>{
    const card=document.createElement('div');
    card.className='drug-card';
    const dosageInstructions=drug.dosage_instructions||'Take as directed by a pharmacist or doctor';
    card.innerHTML=`
      <div class="drug-card-name">${drug.name}</div>
      <div class="drug-card-row"><span class="drug-card-label">For:</span> ${drug.indication||drug.category}</div>
      <div class="drug-card-row"><span class="drug-card-label">Form:</span> ${drug.dosage_form||'As available'}</div>
      <div class="drug-card-row"><span class="drug-card-label">Strength:</span> ${drug.strength||'Standard'}</div>
      <div class="drug-card-dosage"><span class="drug-card-label">Dosage:</span> ${dosageInstructions}</div>
      <div class="drug-card-row"><span class="drug-card-label">Type:</span> ${drug.classification||'Over-the-counter'}</div>
    `;
    wrapper.appendChild(card);
  });
  c.appendChild(wrapper);
  requestAnimationFrame(() => c.scrollTo({top:c.scrollHeight,behavior:'smooth'}));
}

async function send(){
  const input=document.getElementById('tinput'),btn=document.getElementById('send-btn');
  const text=input.value.trim();if(!text)return;
  addMsg('user',text);history.push({role:'user',content:text});
  input.value='';input.style.height='auto';
  btn.disabled=true;btn.innerHTML='<span class="typing" style="display:inline-flex;gap:4px;"><span></span><span></span><span></span></span>';
  showTyping();
  document.getElementById('chips').style.display='none';
  try{
    const res=await callApi('/chat','POST',{messages:history});
    const reply=res.reply||'Please try again.';
    rmTyping();
    if(res.consulting){
      addMsg('ai','Preparing your intake summary for pharmacist review...',[{t:'Review',c:'a'}]);
      await new Promise(r=>setTimeout(r,1200));
      addMsg('ai',reply);
      history.push({role:'assistant',content:reply});
      addMsg('ai','A licensed pharmacist will use this intake summary to assess the case and decide the right treatment.',[{t:'Under Review',c:'g'},{t:'Pharmacist Only',c:'b'}]);
    }else{
      addMsg('ai',reply);
      history.push({role:'assistant',content:reply});
    }
    if(ttsOn)speak(reply);
    document.getElementById('ai-summary').textContent=`Patient: "${text.substring(0,100)}..."\n\nBisaRx: ${reply.substring(0,250)}...`;
    showDynamicChips(reply);
    // Refresh history if logged in
    if(isLoggedIn()){
      try{
        const data=await callApi('/profile');
        renderPrescriptionHistory(data.prescriptions);
      }catch(e){}
    }
  }catch(e){
    rmTyping();
    addMsg('ai','An error occurred. Please try again.',[{t:'Error',c:'r'},{t:'Try Again',c:'a'}]);
    console.error('Chat error:',e.message);
  }
  btn.disabled=false;btn.innerHTML='<span>Send</span><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';
}

// TTS & VOICE
function speak(text){
  if(!synth)return;synth.cancel();
  const maxLen=300;
  if(text.length>maxLen){
    const chunks=text.match(new RegExp('.{1,'+maxLen+'}(\\s|$)','g'))||[text];
    let i=0;
    const speakNext=()=>{
      if(i<chunks.length){
        const utt=new SpeechSynthesisUtterance(chunks[i].replace(/<[^>]*>/g,''));
        utt.rate=0.9;utt.pitch=1.0;
        utt.lang=lang==='fr'?'fr-FR':lang==='ha'?'ha-NG':lang==='tw'?'ak-GH':'en-GH';
        const btn=document.getElementById('spk-btn');
        utt.onstart=()=>btn.classList.add('speaking');
        utt.onend=()=>{i++;if(i<chunks.length)speakNext();else btn.classList.remove('speaking');};
        synth.speak(utt);
      }
    };
    speakNext();
  }else{
    const utt=new SpeechSynthesisUtterance(text.replace(/<[^>]*>/g,''));
    utt.rate=0.9;utt.pitch=1.0;
    utt.lang=lang==='fr'?'fr-FR':lang==='ha'?'ha-NG':lang==='tw'?'ak-GH':'en-GH';
    const btn=document.getElementById('spk-btn');
    utt.onstart=()=>btn.classList.add('speaking');
    utt.onend=()=>btn.classList.remove('speaking');
    synth.speak(utt);
  }
}

function toggleTTS(){ttsOn=!ttsOn;document.getElementById('spk-btn').classList.toggle('on',ttsOn);}

function showDynamicChips(reply){
  const chipsEl=document.getElementById('chips');
  chipsEl.innerHTML='';
  const dynamicChips=[];
  const lowerReply=reply.toLowerCase();
  dynamicChips.push('Ask another question');
  if(lowerReply.includes('pharmacist')||lowerReply.includes('review')||lowerReply.includes('summary')){
    dynamicChips.unshift('What happens next?','Can I add more symptoms?');
  }
  if(lowerReply.includes('symptom')||lowerReply.includes('pain')||lowerReply.includes('fever')){
    dynamicChips.push('Describe more symptoms','What should I avoid?');
  }
  if(lowerReply.includes('hospital')||lowerReply.includes('refer')||lowerReply.includes('emergency')){
    dynamicChips.push('Find nearest hospital');
  }
  dynamicChips.forEach(c=>{
    const d=document.createElement('div');
    d.className='chip';d.textContent=c;
    d.onclick=()=>{document.getElementById('tinput').value=c;chipsEl.style.display='none';send();};
    chipsEl.appendChild(d);
  });
  chipsEl.style.display=dynamicChips.length?'flex':'none';
}

function toggleVoice(){if(!('webkitSpeechRecognition'in window||'SpeechRecognition'in window)){addMsg('ai','Voice input not supported in this browser. Please type.');return;}isRecording?stopVoice():startVoice();}
function startVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;recognition=new SR();
  recognition.lang=lang==='fr'?'fr-FR':lang==='ha'?'ha-NG':'en-GH';
  recognition.onstart=()=>{isRecording=true;document.getElementById('mic-btn').classList.add('rec');document.getElementById('vstatus-bar').style.display='flex';};
  recognition.onresult=e=>{let t='';for(let i=e.resultIndex;i<e.results.length;i++)t+=e.results[i][0].transcript;document.getElementById('tinput').value=t;};
  recognition.onend=()=>{stopVoice();const t=document.getElementById('tinput').value.trim();if(t)send();};
  recognition.onerror=()=>stopVoice();recognition.start();
}
function stopVoice(){isRecording=false;if(recognition)recognition.stop();document.getElementById('mic-btn').classList.remove('rec');document.getElementById('vstatus-bar').style.display='none';}

function selectZone(zone){
  const z=ZONES[zone];if(!z)return;
  document.querySelectorAll('.body-zone').forEach(el=>{el.setAttribute('stroke','var(--primary-dark)');el.setAttribute('fill','rgba(26,122,74,0.08)');});
  document.querySelectorAll(`[data-zone="${zone}"]`).forEach(el=>{el.setAttribute('stroke','var(--accent)');el.setAttribute('fill','rgba(240,165,0,0.18)');});
  document.getElementById('bodymap-info').innerHTML=`<div class="zone-card"><div class="zone-emoji">${z.icon||'🩺'}</div><div class="zone-title">${z.title}</div><div class="zone-sub">${z.sub}</div><div class="zone-simple">Simple meaning: ${z.simple}</div><div class="zone-btns"><button class="zbtn primary" onclick="askZone('${zone}')">Send This Area</button><button class="zbtn secondary" onclick="speakZone('${zone}')">Speak This Out</button></div></div>`;
  speakZone(zone);
}
function askZone(zone){go('chat',document.querySelector('.nav-item'));document.getElementById('tinput').value=ZONES[zone].q;send();}
function renderBodyMapLanding(){
  const el=document.getElementById('bodymap-info');
  if(!el) return;
  el.innerHTML=`<div class="zone-card"><div class="zone-emoji">🩺</div><div class="zone-title">Choose a body part</div><div class="zone-sub">Tap the picture or use the large buttons above. The system can read the option aloud before sending it to chat.</div><div class="zone-btns"><button class="zbtn secondary" onclick="speakBodyMapHelp()">Hear Instructions</button></div></div>`;
}
function speakZone(zone){
  const z=ZONES[zone];
  if(!z||!synth)return;
  synth.cancel();
  const utt=new SpeechSynthesisUtterance(`${z.title}. ${z.simple}. Tap send if this is where the patient feels pain or discomfort.`);
  utt.rate=0.9;
  utt.lang=getSpeechLang();
  synth.speak(utt);
}
function speakBodyMapHelp(){
  if(!synth)return;
  synth.cancel();
  const utt=new SpeechSynthesisUtterance('Tap the body part that hurts. Then listen to the prompt or press send to continue the clinical intake.');
  utt.rate=0.9;
  utt.lang=getSpeechLang();
  synth.speak(utt);
}

function buildConditions(conditionsData){
  const g=document.getElementById('cgrid');
  g.innerHTML='';
  const conditions=conditionsData&&conditionsData.length>0?conditionsData:window.FALLBACK_CONDITIONS;
  conditions.forEach(c=>{
    const d=document.createElement('div');
    d.className='ccard';
    d.innerHTML=`<div class="cname">${c.name}</div><div class="cdrug">${c.drug}</div><div class="ctags">${(c.tags||[]).map(t=>`<span class="ctag ${t.c}">${t.t}</span>`).join('')}</div>`;
    d.onclick=()=>{go('chat',document.querySelector('.nav-item'));document.getElementById('tinput').value=c.q||`Tell me about ${c.name}`;send();};
    g.appendChild(d);
  });
}

function buildRedFlags(redFlagsData){
  const b=document.getElementById('rfbody');
  const redFlags=redFlagsData&&redFlagsData.length>0?redFlagsData:window.FALLBACK_REDFLAGS;
  b.innerHTML=`<div class="rf-intro">The following signs require <strong>immediate hospital referral</strong>.</div>`;
  redFlags.forEach(rf=>{
    const box=document.createElement('div');
    box.className='rfbox';
    box.innerHTML=`<div class="rftitle">&#9888; ${rf.condition}</div>${(rf.flags||[]).map(f=>`<div class="rfitem">${f}</div>`).join('')}`;
    b.appendChild(box);
  });
}

// PROFILE
function showPTab(tab,el){['overview','personal','medical','medications','emergency'].forEach(t=>document.getElementById('ptab-'+t).style.display=t===tab?'block':'none');document.querySelectorAll('.ntab').forEach(n=>n.classList.remove('on'));if(el)el.classList.add('on');}
function refreshOverview(u){
  const p=u.profile||{},m=u.medical||{},meds=u.medications||[],conditionsList=u.conditions||[],allergiesList=u.allergies||[];
  document.getElementById('ov-blood').textContent=p.blood_type||'--';
  if(p.dob){const age=Math.floor((new Date()-new Date(p.dob))/(365.25*24*3600*1000));document.getElementById('ov-age').textContent=isNaN(age)?'--':age;}else document.getElementById('ov-age').textContent='--';
  document.getElementById('ov-conds').textContent=conditionsList.length;
  document.getElementById('ov-allergies').textContent=allergiesList.length;
  const active=meds.filter(x=>x.status==='Active');
  document.getElementById('ov-meds-list').innerHTML=active.length?active.map(x=>`<div class="med-item"><div><div class="med-name">${x.name}</div><div class="med-dose">${x.dose} · ${x.freq}</div></div><span class="badge g">Active</span></div>`).join(''):'<div class="empty">None recorded</div>';
  document.getElementById('ov-allergy-list').innerHTML=allergiesList.length?allergiesList.map(a=>`<span class="allergy-chip" style="cursor:default">${a}</span>`).join(''):'<div class="empty">None recorded</div>';
  document.getElementById('ov-conds-list').innerHTML=conditionsList.length?conditionsList.map(c=>`<span class="cond-chip" style="cursor:default">${c}</span>`).join(''):'<div class="empty">None recorded</div>';
}
async function selBlood(btn,type){document.querySelectorAll('.blood-btn').forEach(b=>b.classList.remove('sel'));btn.classList.add('sel');document.getElementById('ov-blood').textContent=type;}

let conditions=[],allergies=[];
function loadPersonalForm(p){
  if(!p)return;
  document.getElementById('p-fname').value=p.first_name||'';document.getElementById('p-lname').value=p.last_name||'';
  document.getElementById('p-phone').value=p.phone||'';document.getElementById('p-dob').value=p.dob||'';
  document.getElementById('p-address').value=p.address||'';document.getElementById('p-city').value=p.city||'';
  document.getElementById('p-ghcard').value=p.gh_card||'';document.getElementById('p-gender').value=p.gender||'';
  if(p.blood_type)document.querySelectorAll('.blood-btn').forEach(b=>{if(b.textContent===p.blood_type)b.classList.add('sel');});
}
async function savePersonal(){
  const p={first_name:document.getElementById('p-fname').value.trim(),last_name:document.getElementById('p-lname').value.trim(),phone:document.getElementById('p-phone').value.trim(),dob:document.getElementById('p-dob').value,gender:document.getElementById('p-gender').value,address:document.getElementById('p-address').value.trim(),city:document.getElementById('p-city').value.trim(),gh_card:document.getElementById('p-ghcard').value.trim(),blood_type:document.getElementById('ov-blood').textContent!=='--'?document.getElementById('ov-blood').textContent:''};
  try{await callApi('/profile/personal','PUT',p);document.getElementById('personal-msg').innerHTML='<div class="ok">Saved!</div>';showToast('Personal information saved', 'success');setTimeout(()=>document.getElementById('personal-msg').innerHTML='',2000);}catch(e){document.getElementById('personal-msg').innerHTML=`<div class="err">${e.message}</div>`;}
}
function loadMedicalForm(m,condList,allList){if(!m)return;conditions=[...condList];allergies=[...allList];document.getElementById('p-smoking').value=m.smoking||'';document.getElementById('p-alcohol').value=m.alcohol||'';document.getElementById('p-notes').value=m.notes||'';renderCondTags();renderAllergyTags();}
function renderCondTags(){document.getElementById('conds-tags').innerHTML=conditions.map((c,i)=>`<span class="cond-chip" onclick="removeItem('cond',${i})">${c} <span style="font-size:10px;opacity:.7">x</span></span>`).join('');}
function renderAllergyTags(){document.getElementById('allergy-tags').innerHTML=allergies.map((a,i)=>`<span class="allergy-chip" onclick="removeItem('allergy',${i})">${a} <span style="font-size:10px;opacity:.7">x</span></span>`).join('');}
function addCondition(){const v=document.getElementById('cond-input').value.trim();if(!v)return;if(!conditions.includes(v))conditions.push(v);document.getElementById('cond-input').value='';renderCondTags();}
function addAllergy(){const v=document.getElementById('allergy-input').value.trim();if(!v)return;if(!allergies.includes(v))allergies.push(v);document.getElementById('allergy-input').value='';renderAllergyTags();}
function removeItem(type,i){if(type==='cond'){conditions.splice(i,1);renderCondTags();}else{allergies.splice(i,1);renderAllergyTags();}}
async function saveMedical(){
  const m={smoking:document.getElementById('p-smoking').value,alcohol:document.getElementById('p-alcohol').value,notes:document.getElementById('p-notes').value.trim(),conditions,allergies};
  try{await callApi('/profile/medical','PUT',m);const data=await callApi('/profile');refreshOverview(data);document.getElementById('medical-msg').innerHTML='<div class="ok">Saved!</div>';setTimeout(()=>document.getElementById('medical-msg').innerHTML='',2000);}catch(e){document.getElementById('medical-msg').innerHTML=`<div class="err">${e.message}</div>`;}
}
function loadMedsList(meds){
  const el=document.getElementById('meds-list');
  if(!meds||!meds.length){el.innerHTML='<div class="empty">No medications added yet.</div>';return;}
  el.innerHTML=meds.map((m,i)=>`<div class="med-item"><div><div class="med-name">${m.name} ${m.dose}</div><div class="med-dose">${m.freq}${m.doctor?' · Dr. '+m.doctor:''}</div></div><div style="display:flex;gap:7px;align-items:center"><span class="badge ${m.status==='Active'?'g':m.status==='Paused'?'a':'b'}">${m.status}</span><button class="btn danger" style="padding:4px 9px;font-size:11px" onclick="removeMed(${m.id})">Remove</button></div></div>`).join('');
}
async function addMed(){
  const name=document.getElementById('med-name').value.trim(),dose=document.getElementById('med-dose').value.trim(),freq=document.getElementById('med-freq').value,status=document.getElementById('med-status').value,doctor=document.getElementById('med-doctor').value.trim(),msg=document.getElementById('med-msg');
  if(!name||!dose||!freq){msg.innerHTML='<div class="err">Fill in name, dosage, and frequency.</div>';return;}
  try{await callApi('/profile/medications','POST',{name,dose,freq,status,doctor});const data=await callApi('/profile');loadMedsList(data.medications);refreshOverview(data);['med-name','med-dose','med-doctor'].forEach(id=>document.getElementById(id).value='');document.getElementById('med-freq').value='';msg.innerHTML='<div class="ok">Added!</div>';setTimeout(()=>msg.innerHTML='',2000);}catch(e){msg.innerHTML=`<div class="err">${e.message}</div>`;}
}
async function removeMed(id){try{await callApi(`/profile/medications/${id}`,'DELETE');const data=await callApi('/profile');loadMedsList(data.medications);refreshOverview(data);}catch(e){console.error(e);}}
function loadEmergencyForm(ec){
  if(!ec)return;
  document.getElementById('ec-name').value=ec.name||'';document.getElementById('ec-rel').value=ec.rel||'';
  document.getElementById('ec-phone').value=ec.phone||'';document.getElementById('ec-phone2').value=ec.phone_alt||'';
  document.getElementById('ec-address').value=ec.address||'';document.getElementById('ec-alert').value=ec.alert||'';
}
async function saveEmergency(){
  const ec={name:document.getElementById('ec-name').value.trim(),rel:document.getElementById('ec-rel').value,phone:document.getElementById('ec-phone').value.trim(),phone_alt:document.getElementById('ec-phone2').value.trim(),address:document.getElementById('ec-address').value.trim(),alert:document.getElementById('ec-alert').value.trim()};
  try{await callApi('/profile/emergency','PUT',ec);document.getElementById('ec-msg').innerHTML='<div class="ok">Saved!</div>';setTimeout(()=>document.getElementById('ec-msg').innerHTML='',2000);}catch(e){document.getElementById('ec-msg').innerHTML=`<div class="err">${e.message}</div>`;}
}
function copySummary(){navigator.clipboard.writeText(document.getElementById('ai-summary').textContent).catch(()=>{});event.target.textContent='Copied!';setTimeout(()=>event.target.textContent='Copy Summary',2000);}

function renderPrescriptionHistory(rxArray){
  const container=document.getElementById('history-content');
  if(!container)return;
  if(!rxArray||!rxArray.length){container.innerHTML='<div class="empty">No prescription history.</div>';return;}
  const sorted=[...rxArray].reverse();
  container.innerHTML=`
    <div class="slabel">All Prescriptions / AI Recommendations</div>
    <div class="rxlist">
      ${sorted.map(rx=>`
        <div class="rxitem">
          <div class="rxdot" style="background:${rx.status==='Active'?'var(--primary)':'var(--primary-light)'}"></div>
          <div style="flex:1">
            <div class="rxdrug">${rx.drug_name}</div>
            <div class="rxdet">${rx.details} · ${new Date(rx.created_at).toLocaleDateString()}</div>
          </div>
          <span class="rxst ${rx.status==='Active'?'ac':'pe'}">${rx.status}</span>
        </div>
      `).join('')}
    </div>
  `;
}

LANGS.en = {
  greeting: "What are your symptoms? Describe what you're experiencing and how long it has been going on.",
  chips: ["I have a headache", "Stomach pain", "I feel feverish", "I have a cough", "My child is sick", "Skin rash"],
  placeholder: "Describe your symptoms...",
  disc: "For general guidance only. Consult a licensed clinician for diagnosis, treatment, or medication decisions.",
  discLabel: "Clinical Note:"
};

LANGS.tw = {
  greeting: "Wo yaree ben na ewo wo? Ka kyerE me sEdeE wote wo ho ne bere a edi so.",
  chips: ["Me ti ye me yaw", "Me yafunu ye me yaw", "Mewo atiridiinini", "Mewo ekoo", "Me ba yare", "Honam yare"],
  placeholder: "Ka me nkyEn sEdeE wote wo ho...",
  disc: "Yei yE akwankyerE nkutoo. Bisa oduruyEfo anaa odokota ansa na woasi gyinae biara.",
  discLabel: "NsErEwmu:"
};

LANGS.ha = {
  greeting: "Mene ne alamu ku? Bayyana yadda kuke ji da tsawon lokaci.",
  chips: ["Ina da ciwon kai", "Ciki na yi mini ciwo", "Ina da zazzabi", "Ina da tari", "Yaro na ba shi da lafiya", "Ina da kuraje"],
  placeholder: "Bayyana alamun ku...",
  disc: "Jagora ne kawai. Tuntubi kwararren likita ko likitan magani kafin yanke shawarar magani.",
  discLabel: "Bayani:"
};

LANGS.fr = {
  greeting: "Quels sont vos symptomes? Decrivez ce que vous ressentez et depuis combien de temps.",
  chips: ["J'ai mal a la tete", "Douleur abdominale", "J'ai de la fievre", "Je tousse", "Mon enfant est malade", "Eruption cutanee"],
  placeholder: "Decrivez vos symptomes...",
  disc: "Conseils generaux uniquement. Consultez un professionnel de sante agree pour toute decision clinique.",
  discLabel: "Note:"
};

function buildLang() {
  const L = LANGS[lang];
  document.getElementById('chat-title').textContent = lang === 'fr' ? 'BisaRx Assistant Clinique' : 'BisaRx Clinical Care Assistant';
  document.getElementById('chat-sub').textContent = 'Professional guidance · Voice enabled · Multilingual support';
  document.getElementById('disc-label').textContent = L.discLabel;
  document.getElementById('disc-text').textContent = L.disc;
  document.getElementById('tinput').placeholder = L.placeholder;
  document.getElementById('lang-badge').textContent = lang.toUpperCase();

  const chipsEl = document.getElementById('chips');
  chipsEl.innerHTML = '';
  L.chips.forEach(c => {
    const d = document.createElement('div');
    d.className = 'chip';
    d.textContent = c;
    d.onclick = () => {
      document.getElementById('tinput').value = c;
      chipsEl.style.display = 'none';
      send();
    };
    chipsEl.appendChild(d);
  });
}

function speakGuidance(txt) {
  if (!synth) return;
  synth.cancel();
  const utt = new SpeechSynthesisUtterance(txt);
  utt.rate = 0.9;
  utt.lang = getSpeechLang();
  synth.speak(utt);
}

function speakMsg(msgId, btn) {
  const msgEl = document.getElementById(msgId);
  if (!msgEl) return;
  const text = msgEl.querySelector('.bub-text')?.innerText?.trim();
  if (!text || !synth) return;

  if (btn.classList.contains('speaking')) {
    synth.cancel();
    btn.classList.remove('speaking');
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg><span>Listen</span>`;
    return;
  }

  synth.cancel();
  btn.classList.add('speaking');
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg><span>Stop</span>`;

  const utt = new SpeechSynthesisUtterance(text);
  utt.rate = 0.9;
  utt.pitch = 1;
  utt.lang = getSpeechLang();
  utt.onend = () => {
    btn.classList.remove('speaking');
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg><span>Listen</span>`;
  };
  utt.onerror = () => {
    btn.classList.remove('speaking');
  };
  synth.speak(utt);
}

function speak(text) {
  if (!synth) return;
  synth.cancel();
  const maxLen = 300;
  const chunks = text.length > maxLen ? (text.match(new RegExp('.{1,' + maxLen + '}(\\s|$)', 'g')) || [text]) : [text];
  let i = 0;

  const speakNext = () => {
    if (i >= chunks.length) return;
    const utt = new SpeechSynthesisUtterance(chunks[i].replace(/<[^>]*>/g, ''));
    utt.rate = 0.9;
    utt.pitch = 1;
    utt.lang = getSpeechLang();
    const btn = document.getElementById('spk-btn');
    utt.onstart = () => btn.classList.add('speaking');
    utt.onend = () => {
      i += 1;
      if (i < chunks.length) speakNext();
      else btn.classList.remove('speaking');
    };
    synth.speak(utt);
  };

  speakNext();
}

function startVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = getSpeechLang();
  recognition.onstart = () => {
    isRecording = true;
    document.getElementById('mic-btn').classList.add('rec');
    document.getElementById('vstatus-bar').style.display = 'flex';
  };
  recognition.onresult = e => {
    let t = '';
    for (let i = e.resultIndex; i < e.results.length; i += 1) t += e.results[i][0].transcript;
    document.getElementById('tinput').value = t;
  };
  recognition.onend = () => {
    stopVoice();
    const t = document.getElementById('tinput').value.trim();
    if (t) send();
  };
  recognition.onerror = () => stopVoice();
  recognition.start();
}

function refreshOverview(u) {
  const p = u.profile || {};
  const meds = u.medications || [];
  const conditionsList = u.conditions || [];
  const allergiesList = u.allergies || [];
  document.getElementById('ov-blood').textContent = p.blood_type || '--';
  if (p.dob) {
    const age = Math.floor((new Date() - new Date(p.dob)) / (365.25 * 24 * 3600 * 1000));
    document.getElementById('ov-age').textContent = isNaN(age) ? '--' : age;
  } else {
    document.getElementById('ov-age').textContent = '--';
  }
  document.getElementById('ov-conds').textContent = conditionsList.length;
  document.getElementById('ov-allergies').textContent = allergiesList.length;
  const active = meds.filter(x => x.status === 'Active');
  document.getElementById('ov-meds-list').innerHTML = active.length
    ? active.map(x => `<div class="med-item"><div><div class="med-name">${x.name}</div><div class="med-dose">${x.dose} · ${x.freq}</div></div><span class="badge g">Active</span></div>`).join('')
    : '<div class="empty">None recorded</div>';
  document.getElementById('ov-allergy-list').innerHTML = allergiesList.length
    ? allergiesList.map(a => `<span class="allergy-chip" style="cursor:default">${a}</span>`).join('')
    : '<div class="empty">None recorded</div>';
  document.getElementById('ov-conds-list').innerHTML = conditionsList.length
    ? conditionsList.map(c => `<span class="cond-chip" style="cursor:default">${c}</span>`).join('')
    : '<div class="empty">None recorded</div>';
}

function loadMedsList(meds) {
  const el = document.getElementById('meds-list');
  if (!meds || !meds.length) {
    el.innerHTML = '<div class="empty">No medications added yet.</div>';
    return;
  }
  el.innerHTML = meds.map(m => `<div class="med-item"><div><div class="med-name">${m.name} ${m.dose}</div><div class="med-dose">${m.freq}${m.doctor ? ' · Dr. ' + m.doctor : ''}</div></div><div style="display:flex;gap:7px;align-items:center"><span class="badge ${m.status === 'Active' ? 'g' : m.status === 'Paused' ? 'a' : 'b'}">${m.status}</span><button class="btn danger" style="padding:4px 9px;font-size:11px" onclick="removeMed(${m.id})">Remove</button></div></div>`).join('');
}

function renderPrescriptionHistory(rxArray) {
  const container = document.getElementById('history-content');
  if (!container) return;
  if (!rxArray || !rxArray.length) {
    container.innerHTML = '<div class="empty">No prescription history.</div>';
    return;
  }
  const sorted = [...rxArray].reverse();
  container.innerHTML = `
    <div class="slabel">All Prescriptions / AI Recommendations</div>
    <div class="rxlist">
      ${sorted.map(rx => `
        <div class="rxitem">
          <div class="rxdot" style="background:${rx.status === 'Active' ? 'var(--primary)' : 'var(--primary-light)'}"></div>
          <div style="flex:1">
            <div class="rxdrug">${rx.drug_name}</div>
            <div class="rxdet">${rx.details} · ${new Date(rx.created_at).toLocaleDateString()}</div>
          </div>
          <span class="rxst ${rx.status === 'Active' ? 'ac' : 'pe'}">${rx.status}</span>
        </div>
      `).join('')}
    </div>
  `;
}

document.getElementById('cond-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();addCondition();}});
document.getElementById('allergy-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();addAllergy();}});

let currentSession = { role: 'guest', display_name: '' };
const openReviewForms = new Set();

async function fetchSessionContext() {
  if (!isLoggedIn()) {
    currentSession = { role: 'guest', display_name: '' };
    return currentSession;
  }
  try {
    currentSession = await callApi('/session');
  } catch (e) {
    console.warn('Failed to fetch session context', e);
    currentSession = { role: 'user', display_name: currentUser || '' };
  }
  return currentSession;
}

function updateAuthUI() {
  const loggedIn = isLoggedIn();
  const authFooter = document.getElementById('auth-footer');
  const userFooter = document.getElementById('user-footer');
  const navProfile = document.getElementById('nav-profile');
  const navConnect = document.getElementById('nav-connect');
  const navHistory = document.getElementById('nav-history');
  const navPharmacist = document.getElementById('nav-pharmacist');
  const navAdmin = document.getElementById('nav-admin');
  const isPatientView = currentSession.role === 'guest' || currentSession.role === 'user';

  if (authFooter) authFooter.style.display = loggedIn ? 'none' : 'block';
  if (userFooter) userFooter.style.display = loggedIn ? 'block' : 'none';
  if (loggedIn) {
    const label = document.getElementById('user-label');
    if (label) {
      const roleLabel = currentSession.role === 'admin' ? 'Admin' : currentSession.role === 'pharmacist' ? 'Clinician' : 'Patient';
      label.textContent = `${currentSession.display_name || currentUser || 'User'} · ${roleLabel}`;
    }
  }

  if (navProfile) navProfile.style.display = currentSession.role === 'user' ? 'flex' : 'none';
  if (navHistory) navHistory.style.display = currentSession.role === 'user' ? 'flex' : 'none';
  if (navConnect) navConnect.style.display = isPatientView ? 'flex' : 'none';
  if (navPharmacist) navPharmacist.style.display = currentSession.role === 'pharmacist' ? 'flex' : 'none';
  if (navAdmin) navAdmin.style.display = currentSession.role === 'admin' ? 'flex' : 'none';
}

function updatePharmacistUI() {
  updateAuthUI();
}

async function refreshPharmacistDashboard() {
  if (currentSession.role !== 'pharmacist') return;
  try {
    const data = await callApi('/pharmacist/dashboard');
    document.getElementById('ph-stat-assigned').textContent = data.stats.assigned_cases;
    document.getElementById('ph-stat-inreview').textContent = data.stats.in_review_cases;
    document.getElementById('ph-stat-completed').textContent = data.stats.completed_cases;
    document.getElementById('ph-stat-verified').textContent = data.pharmacist.is_verified ? 'Yes' : 'No';
    renderPharmacistDashboard(data.assigned_cases, data.completed_cases);
  } catch (e) {
    console.error(e);
  }
}

function renderPharmacistDashboard(assignedCases = [], completedCases = []) {
  // Assigned cases (in review)
  const q = document.getElementById('pharmacist-queue');
  if (q) {
    q.innerHTML = assignedCases.length 
      ? assignedCases.map(renderPharmacistCaseCard).join('') 
      : '<div class="empty">No cases assigned to you yet. Admin will assign cases to you.</div>';
  }
  
  // Completed cases
  const c = document.getElementById('pharmacist-completed');
  if (c) {
    c.innerHTML = completedCases.length
      ? completedCases.map(renderPharmacistCaseCard).join('')
      : '<div class="empty">No completed cases yet.</div>';
  }
}

function renderCaseCard(c) {
  const patientName = c.patient?.full_name || c.patient?.username || 'Patient';
  const assignedName = c.pharmacist?.name ? `<div class="case-details">Assigned to: ${c.pharmacist.name}</div>` : '';
  const reviewOpen = openReviewForms.has(c.id);
  const reviewForm = reviewOpen ? `
    <div class="dashboard-form">
      <textarea id="review-advice-${c.id}" placeholder="Write clinical advice, counseling notes, and next steps."></textarea>
      <div class="dashboard-inline">
        <input id="review-drug-${c.id}" type="text" placeholder="Recommended medication (optional)" value="${c.drug_name || ''}">
        <select id="review-status-${c.id}">
          <option value="Reviewed" ${c.status === 'Reviewed' ? 'selected' : ''}>Reviewed</option>
          <option value="Ordered" ${c.status === 'Ordered' ? 'selected' : ''}>Ordered</option>
          <option value="Delivered" ${c.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
        </select>
      </div>
      <div class="dashboard-form-actions">
        <button class="btn btn-primary btn-sm" onclick="submitCaseReview(${c.id})">Save Review</button>
        <button class="btn btn-secondary btn-sm" onclick="toggleReviewForm(${c.id})">Cancel</button>
      </div>
    </div>
  ` : '';
  return `
    <div class="case-card">
      <div class="case-header">
        <span class="case-user">${patientName}</span>
        <span class="case-time">${new Date(c.created_at).toLocaleString()}</span>
      </div>
      <div class="case-details"><strong>Status:</strong> ${c.status}</div>
      <div class="case-details"><strong>Medication:</strong> ${c.drug_name || 'To be confirmed'}</div>
      <div class="dashboard-meta">
        <div class="case-details"><strong>Patient Email:</strong> ${c.patient?.email || 'Not available'}</div>
        <div class="case-details"><strong>Phone:</strong> ${c.patient?.phone || 'Not provided'}</div>
        <div class="case-details"><strong>Location:</strong> ${c.patient?.city || 'Not provided'}</div>
      </div>
      <div class="case-details">${c.details}</div>
      ${assignedName}
      <div class="case-actions">
        <button class="btn-review" onclick="toggleReviewForm(${c.id})">${reviewOpen ? 'Hide Review Form' : 'Open Review Form'}</button>
      </div>
      ${reviewForm}
    </div>
  `;
}

// Removed claimCase - admin now assigns cases to pharmacists

// Admin tabs
function showAdminTab(tab, el) {
  ['overview', 'users', 'clinicians', 'cases'].forEach(t => {
    const el = document.getElementById('admin-tab-' + t);
    if (el) el.style.display = t === tab ? 'block' : 'none';
  });
  document.querySelectorAll('#panel-admin .ntab').forEach(n => n.classList.remove('on'));
  if (el) el.classList.add('on');
}

// Pharmacist tabs
function showPharmaTab(tab, el) {
  ['assigned', 'completed'].forEach(t => {
    const el = document.getElementById('pharma-tab-' + t);
    if (el) el.style.display = t === tab ? 'block' : 'none';
  });
  document.querySelectorAll('#panel-pharmacist .ntab').forEach(n => n.classList.remove('on'));
  if (el) el.classList.add('on');
}

// Render case card for pharmacist (no claim button)
function renderPharmacistCaseCard(c) {
  const patientName = c.patient?.full_name || c.patient?.username || 'Patient';
  const assignedName = c.pharmacist?.name ? `<div class="case-details">Assigned to: ${c.pharmacist.name}</div>` : '';
  const reviewOpen = openReviewForms.has(c.id);
  const reviewForm = reviewOpen ? `
    <div class="dashboard-form">
      <textarea id="review-advice-${c.id}" placeholder="Write clinical advice, counseling notes, and next steps."></textarea>
      <div class="dashboard-inline">
        <input id="review-drug-${c.id}" type="text" placeholder="Recommended medication (optional)" value="${c.drug_name || ''}">
        <select id="review-status-${c.id}">
          <option value="Reviewed" ${c.status === 'Reviewed' ? 'selected' : ''}>Reviewed</option>
          <option value="Ordered" ${c.status === 'Ordered' ? 'selected' : ''}>Ordered</option>
          <option value="Delivered" ${c.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
        </select>
      </div>
      <div class="dashboard-form-actions">
        <button class="btn btn-primary btn-sm" onclick="submitCaseReview(${c.id})">Save Review</button>
        <button class="btn btn-secondary btn-sm" onclick="toggleReviewForm(${c.id})">Cancel</button>
      </div>
    </div>
  ` : '';
  return `
    <div class="case-card">
      <div class="case-header">
        <span class="case-user">${patientName}</span>
        <span class="case-time">${new Date(c.created_at).toLocaleString()}</span>
      </div>
      <div class="case-details"><strong>Status:</strong> ${c.status}</div>
      <div class="case-details"><strong>Medication:</strong> ${c.drug_name || 'To be confirmed'}</div>
      <div class="dashboard-meta">
        <div class="case-details"><strong>Patient Email:</strong> ${c.patient?.email || 'Not available'}</div>
        <div class="case-details"><strong>Phone:</strong> ${c.patient?.phone || 'Not provided'}</div>
        <div class="case-details"><strong>Location:</strong> ${c.patient?.city || 'Not provided'}</div>
      </div>
      <div class="case-details">${c.details}</div>
      ${assignedName}
      <div class="case-actions">
        <button class="btn-review" onclick="toggleReviewForm(${c.id})">${reviewOpen ? 'Hide Review Form' : 'Open Review Form'}</button>
      </div>
      ${reviewForm}
    </div>
  `;
}

function toggleReviewForm(id) {
  if (openReviewForms.has(id)) openReviewForms.delete(id);
  else openReviewForms.add(id);
  refreshPharmacistDashboard();
}

async function submitCaseReview(id) {
  const advice = document.getElementById(`review-advice-${id}`)?.value.trim();
  const drug = document.getElementById(`review-drug-${id}`)?.value.trim();
  const statusValue = document.getElementById(`review-status-${id}`)?.value || 'Reviewed';
  if (!advice) {
    alert('Clinical advice is required.');
    return;
  }
  try {
    await callApi(`/pharmacist/review/${id}`, 'POST', { advice, drug, status: statusValue });
    openReviewForms.delete(id);
    refreshPharmacistDashboard();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

async function refreshAdminDashboard() {
  if (currentSession.role !== 'admin') return;
  try {
    const data = await callApi('/admin/dashboard');
    document.getElementById('admin-total-users').textContent = data.stats.total_users;
    document.getElementById('admin-total-pharmacists').textContent = data.stats.total_pharmacists;
    document.getElementById('admin-pending-cases').textContent = data.stats.pending_cases;
    document.getElementById('admin-inreview-cases').textContent = data.stats.in_review_cases;
    document.getElementById('admin-completed-cases').textContent = data.stats.reviewed_cases;
    document.getElementById('admin-verified-pharmacists').textContent = data.stats.verified_pharmacists;
    
    // Render lists
    renderAdminPharmacists(data.pharmacists);
    renderAdminCases(data.cases, data.pharmacists);
    renderAdminUsers(data.recent_users);
  } catch (e) {
    console.error(e);
  }
}

function renderAdminUsers(users = []) {
  const el = document.getElementById('admin-users-list');
  if (!el) return;
  if (!users || users.length === 0) {
    el.innerHTML = '<div class="empty">No users found.</div>';
    return;
  }
  el.innerHTML = users.map(u => `
    <div class="med-item">
      <div>
        <div class="med-name">${u.first_name || ''} ${u.last_name || ''} <small style="color:var(--mist-500)">(@${u.username})</small></div>
        <div class="med-dose">${u.email} ${u.is_admin ? '<span class="badge badge-danger" style="margin-left:8px">Admin</span>' : ''}</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <span class="badge ${u.city ? 'badge-success' : 'badge-primary'}">${u.city || 'No location'}</span>
      </div>
    </div>
  `).join('');
}

function renderAdminPharmacists(pharmacists = []) {
  const el = document.getElementById('admin-pharmacists-list');
  if (!el) return;
  el.innerHTML = pharmacists.length ? pharmacists.map(p => `
    <div class="pharmacist-card">
      <div class="pharmacist-avatar" style="background:#edf2f7;color:#1e3a30;">${(p.full_name || p.username || 'CL').split(' ').map(x => x[0]).join('').slice(0, 2).toUpperCase()}</div>
      <div class="pharmacist-info">
        <h5>${p.full_name || p.username}</h5>
        <span>${p.email}</span>
        <p>License: ${p.license_number || 'Not provided'}</p>
      </div>
      <div class="pharmacist-actions">
        <span class="online"><span class="dot"></span>${p.is_verified ? 'Verified' : 'Pending verification'}</span>
        ${p.is_verified ? '' : `<button class="btn btn-primary btn-sm" onclick="verifyPharmacist(${p.id})">Verify</button>`}
        <button class="btn danger btn-sm" onclick="deletePharmacist(${p.id})">Delete</button>
      </div>
    </div>
  `).join('') : '<div class="empty">No clinicians found.</div>';
}

async function createPharmacist() {
  const payload = {
    full_name: document.getElementById('admin-ph-name').value.trim(),
    username: document.getElementById('admin-ph-username').value.trim().toLowerCase(),
    email: document.getElementById('admin-ph-email').value.trim(),
    license_number: document.getElementById('admin-ph-license').value.trim(),
    location: document.getElementById('admin-ph-location').value.trim(),
    password: document.getElementById('admin-ph-password').value
  };
  const msg = document.getElementById('admin-ph-msg');
  if (!payload.full_name || !payload.username || !payload.email || !payload.license_number || !payload.password) {
    msg.innerHTML = '<div class="err">Fill all clinician fields first.</div>';
    return;
  }
  try {
    await callApi('/admin/pharmacists', 'POST', payload);
    ['admin-ph-name', 'admin-ph-username', 'admin-ph-email', 'admin-ph-license', 'admin-ph-location', 'admin-ph-password']
      .forEach(id => { document.getElementById(id).value = ''; });
    msg.innerHTML = '<div class="ok">Clinician account created.</div>';
    refreshAdminDashboard();
  } catch (e) {
    msg.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

function renderAdminCases(cases = [], pharmacists = []) {
  const el = document.getElementById('admin-cases-list');
  if (!el) return;
  el.innerHTML = cases.length ? `<div class="case-list-view">${cases.map(c => {
    const options = pharmacists.map(p => `<option value="${p.id}" ${c.pharmacist?.id === p.id ? 'selected' : ''}>${p.full_name || p.username}</option>`).join('');
    const patientName = c.patient?.full_name || c.patient?.username || 'Patient';
    return `
      <div class="case-list-item">
        <div class="case-list-info">
          <div class="case-list-name">${patientName}</div>
          <div class="case-list-meta">
            <span>Status: ${c.status}</span> · 
            <span>${new Date(c.created_at).toLocaleString()}</span> · 
            <span>Assigned: ${c.pharmacist?.name || 'Unassigned'}</span>
          </div>
        </div>
        <div class="case-list-actions">
          <select id="assign-case-${c.id}" style="min-width:120px;padding:8px;">
            <option value="">Assign</option>
            ${options}
          </select>
          <button class="btn btn-primary btn-sm" onclick="assignCase(${c.id})">Assign</button>
        </div>
      </div>
    `;
  }).join('')}</div>` : '<div class="empty">No cases available.</div>';
}

async function verifyPharmacist(id) {
  try {
    await callApi(`/admin/pharmacists/${id}/verify`, 'POST', {});
    refreshAdminDashboard();
  } catch (e) {
    alert(`Unable to verify clinician: ${e.message}`);
  }
}

async function assignCase(id) {
  const select = document.getElementById(`assign-case-${id}`);
  const pharmacistId = Number(select?.value || 0);
  if (!pharmacistId) {
    alert('Select a clinician first.');
    return;
  }
  try {
    await callApi(`/admin/cases/${id}/assign`, 'POST', { pharmacist_id: pharmacistId });
    refreshAdminDashboard();
    refreshPharmacistDashboard();
  } catch (e) {
    alert(`Unable to assign case: ${e.message}`);
  }
}

async function deletePharmacist(id) {
  if (!confirm('Delete this clinician account?')) return;
  try {
    await callApi(`/admin/pharmacists/${id}`, 'DELETE');
    refreshAdminDashboard();
  } catch (e) {
    alert(`Unable to delete clinician: ${e.message}`);
  }
}

function formatPrescriptionDetails(details = '') {
  const clean = String(details || '').replace(/\s*\|\|\s*/g, ' | ');
  const adviceMarker = 'Clinician advice:';
  if (!clean.includes(adviceMarker)) return clean;
  const [summary, advice] = clean.split(adviceMarker);
  return `${summary.trim()} | Feedback from clinician: ${advice.trim()}`;
}

function renderPrescriptionHistory(rxArray) {
  const container = document.getElementById('history-content');
  if (!container) return;
  if (!rxArray || !rxArray.length) {
    container.innerHTML = '<div class="empty">No prescription history.</div>';
    return;
  }
  const sorted = [...rxArray].reverse();
  container.innerHTML = `
    <div class="slabel">Patient Cases And Clinician Feedback</div>
    <div class="rxlist">
      ${sorted.map(rx => `
        <div class="rxitem">
          <div class="rxdot" style="background:${rx.status === 'Active' ? 'var(--primary)' : 'var(--primary-light)'}"></div>
          <div style="flex:1">
            <div class="rxdrug">${rx.drug_name}</div>
            <div class="rxdet">${formatPrescriptionDetails(rx.details)} | ${new Date(rx.created_at).toLocaleDateString()}</div>
          </div>
          <span class="rxst ${rx.status === 'Active' ? 'ac' : 'pe'}">${rx.status}</span>
        </div>
      `).join('')}
    </div>
  `;
}

async function initApp() {
  await fetchSessionContext();
  updateAuthUI();
  buildLang();
  renderBodyMapLanding();

  try {
    const refData = await callApi('/reference');
    buildConditions(refData.conditions);
    buildRedFlags(refData.red_flags);
  } catch (e) {
    console.warn('Failed to load reference data, using defaults', e);
    buildConditions(window.FALLBACK_CONDITIONS || []);
    buildRedFlags(window.FALLBACK_REDFLAGS || []);
  }

  if (currentSession.role === 'user') {
    await loadProfileData();
  } else if (!isLoggedIn()) {
    const pc = document.getElementById('profile-content');
    const pp = document.getElementById('profile-auth-prompt');
    if (pc) pc.style.display = 'none';
    if (pp) pp.style.display = 'block';
    const hc = document.getElementById('history-content');
    const hp = document.getElementById('history-auth-prompt');
    if (hc) hc.style.display = 'none';
    if (hp) hp.style.display = 'block';
  }

  if (currentSession.role === 'pharmacist') {
    const nav = document.getElementById('nav-pharmacist');
    if (nav) go('pharmacist', nav);
    refreshPharmacistDashboard();
  }
  if (currentSession.role === 'admin') {
    const nav = document.getElementById('nav-admin');
    if (nav) go('admin', nav);
    refreshAdminDashboard();
  }

  if (currentSession.role !== 'pharmacist' && currentSession.role !== 'admin') {
    addMsg('ai', LANGS[lang].greeting, [{ t: 'BisaRx', c: 'g' }, { t: 'Clinical AI', c: 'b' }, { t: 'Multilingual', c: 'a' }]);
  }
}

let pharmacistDashboardState = { pending: [], assigned: [] };
let adminDashboardState = { cases: [], pharmacists: [] };

function getZoneOptions(zone) {
  const defaults = ['pain', 'swelling', 'rash', 'wound'];
  const map = {
    head: ['pain', 'dizziness', 'fever', 'injury'],
    throat: ['pain', 'swallowing problem', 'swelling', 'stiffness'],
    shoulder: ['pain', 'swelling', 'stiffness', 'injury'],
    chest: ['pain', 'cough', 'breathing problem', 'tightness'],
    abdomen: ['pain', 'vomiting', 'diarrhea', 'swelling'],
    pelvis: ['pain', 'urine problem', 'cramps', 'bleeding'],
    neck_back: ['pain', 'stiffness', 'swelling', 'injury'],
    back: ['pain', 'burning', 'stiffness', 'injury'],
    lower_back: ['pain', 'stiffness', 'weakness', 'injury'],
    arm: ['pain', 'swelling', 'numbness', 'injury'],
    hand: ['pain', 'swelling', 'numbness', 'wound'],
    leg: ['pain', 'swelling', 'weakness', 'wound'],
    foot: ['pain', 'swelling', 'wound', 'burning']
  };
  return map[zone] || defaults;
}

function renderBodyMapLanding() {
  const el = document.getElementById('bodymap-info');
  if (!el) return;
  el.innerHTML = `<div class="zone-card"><div class="zone-emoji">🩺</div><div class="zone-title">Choose a body part</div><div class="zone-sub">Tap the body area, then choose what kind of problem it is and how bad it feels.</div><div class="zone-btns"><button class="zbtn secondary" onclick="speakBodyMapHelp()">Hear Instructions</button></div></div>`;
}

function selectZone(zone) {
  const z = ZONES[zone];
  if (!z) return;
  document.querySelectorAll('.body-zone').forEach(el => {
    el.setAttribute('stroke', 'var(--primary-dark)');
    el.setAttribute('fill', 'rgba(26,122,74,0.08)');
  });
  document.querySelectorAll(`[data-zone="${zone}"]`).forEach(el => {
    el.setAttribute('stroke', 'var(--accent)');
    el.setAttribute('fill', 'rgba(240,165,0,0.18)');
  });
  const symptomButtons = getZoneOptions(zone).map(option => `<button class="chip" onclick="askZone('${zone}','${option}','moderate')">${option}</button>`).join('');
  document.getElementById('bodymap-info').innerHTML = `
    <div class="zone-card">
      <div class="zone-emoji">${z.icon || '🩺'}</div>
      <div class="zone-title">${z.title}</div>
      <div class="zone-sub">${z.sub}</div>
      <div class="zone-simple">Choose the problem type first:</div>
      <div class="ctags">${symptomButtons}</div>
      <div class="zone-simple">Then choose severity:</div>
      <div class="zone-btns">
        <button class="zbtn secondary" onclick="askZone('${zone}','pain','mild')">Mild</button>
        <button class="zbtn secondary" onclick="askZone('${zone}','pain','moderate')">Moderate</button>
        <button class="zbtn primary" onclick="askZone('${zone}','pain','severe')">Severe</button>
      </div>
      <div class="zone-btns">
        <button class="zbtn secondary" onclick="speakZone('${zone}')">Speak This Out</button>
      </div>
    </div>
  `;
  speakZone(zone);
}

function askZone(zone, symptomType = 'pain', severity = 'moderate') {
  const prompt = `My ${zone} has ${symptomType}. The severity feels ${severity}. Please assess this symptom.`;
  go('chat', document.getElementById('nav-chat'));
  document.getElementById('tinput').value = prompt;
  send();
}

function speakZone(zone) {
  const z = ZONES[zone];
  if (!z || !synth) return;
  synth.cancel();
  const utt = new SpeechSynthesisUtterance(`${z.title}. ${z.simple}. Choose the symptom type, then choose how serious it feels.`);
  utt.rate = 0.9;
  utt.lang = getSpeechLang();
  synth.speak(utt);
}

function speakBodyMapHelp() {
  if (!synth) return;
  synth.cancel();
  const utt = new SpeechSynthesisUtterance('Tap the body part. Choose the kind of problem. Then send it to the clinical chat for review.');
  utt.rate = 0.9;
  utt.lang = getSpeechLang();
  synth.speak(utt);
}

function renderCareTeam(clinicians = []) {
  const section = document.querySelector('.pharmacists-section');
  if (!section) return;
  const body = clinicians.length ? clinicians.map(c => `
    <div class="pharmacist-card">
      <div class="pharmacist-avatar" style="background:#edf2f7;color:#1e3a30;">${(c.full_name || c.username || 'CL').split(' ').map(x => x[0]).join('').slice(0, 2).toUpperCase()}</div>
      <div class="pharmacist-info">
        <h5>${c.full_name || c.username}</h5>
        <span>${c.location || 'Licensed clinician'}</span>
        <p>License: ${c.license_number || 'Verified clinician'}.</p>
      </div>
      <div class="pharmacist-actions">
        <span class="online"><span class="dot"></span>${c.is_verified ? 'Available' : 'Pending'}</span>
        <button class="btn btn-primary btn-sm" onclick="focusChatForClinician('${(c.full_name || c.username).replace(/'/g, "\\'")}')">Send Summary</button>
      </div>
    </div>
  `).join('') : '<div class="empty">No clinicians are available right now.</div>';
  section.innerHTML = `<h4>Available Clinicians</h4>${body}`;
}

function focusChatForClinician(name) {
  go('chat', document.getElementById('nav-chat'));
  document.getElementById('tinput').value = `I want my case reviewed by clinician ${name}.`;
}

async function loadCareTeam() {
  try {
    const data = await callApi('/clinicians/available');
    renderCareTeam(data.clinicians || []);
  } catch (e) {
    console.warn('Failed to load clinicians', e);
  }
}

function formatPrescriptionDetails(details = '') {
  return String(details || '').replace(/\s*\|\|\s*/g, ' | ').replace(/\n+/g, ' | ');
}

function renderPrescriptionHistory(rxArray) {
  const container = document.getElementById('history-content');
  if (!container) return;
  if (!rxArray || !rxArray.length) {
    container.innerHTML = '<div class="empty">No prescription history.</div>';
    return;
  }
  const sorted = [...rxArray].reverse();
  const feedbackCount = sorted.filter(rx => rx.pharmacist_feedback).length;
  container.innerHTML = `
    ${feedbackCount ? `<div class="disclaimer-banner"><strong>Update:</strong> You have ${feedbackCount} case update(s) with clinician feedback.</div>` : ''}
    <div class="slabel">Patient Cases And Clinician Feedback</div>
    <div class="rxlist">
      ${sorted.map(rx => `
        <div class="rxitem" style="display:block;">
          <div style="display:flex;gap:12px;align-items:flex-start;">
            <div class="rxdot" style="background:${rx.status === 'Reviewed' || rx.status === 'Delivered' ? 'var(--success)' : 'var(--primary-light)'}"></div>
            <div style="flex:1">
              <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;">
                <div class="rxdrug">${rx.drug_name}</div>
                <span class="rxst ${rx.status === 'Reviewed' || rx.status === 'Delivered' ? 'ac' : 'pe'}">${rx.status}</span>
              </div>
              <div class="rxdet">Summary: ${rx.case_summary || formatPrescriptionDetails(rx.details)}</div>
              ${rx.pharmacist_feedback ? `<div class="rxdet"><strong>Clinician Feedback:</strong> ${rx.pharmacist_feedback}</div>` : ''}
              ${rx.referral_advice ? `<div class="rxdet"><strong>Referral:</strong> ${rx.referral_advice}</div>` : ''}
              ${rx.follow_up_instructions ? `<div class="rxdet"><strong>Follow-up:</strong> ${rx.follow_up_instructions}</div>` : ''}
              <div class="rxdet">Urgency: ${rx.urgency_level || 'routine'} | Follow-up: ${rx.follow_up_status || 'awaiting_review'} | ${new Date(rx.created_at).toLocaleDateString()}</div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function ensureDashboardToolbar(containerId, type) {
  const container = document.getElementById(containerId);
  if (!container || container.querySelector('.dashboard-toolbar')) return;
  const placeholder = type === 'admin' ? 'Search patient, clinician, area...' : 'Search patient, symptom, area...';
  container.insertAdjacentHTML('afterbegin', `
    <div class="dashboard-toolbar">
      <input id="${type}-search" type="text" placeholder="${placeholder}">
      <select id="${type}-status">
        <option value="">All statuses</option>
        <option value="Pending">Pending</option>
        <option value="In Review">In Review</option>
        <option value="Reviewed">Reviewed</option>
        <option value="Ordered">Ordered</option>
        <option value="Delivered">Delivered</option>
      </select>
      <select id="${type}-urgency">
        <option value="">All urgency</option>
        <option value="routine">Routine</option>
        <option value="priority">Priority</option>
        <option value="urgent">Urgent</option>
      </select>
    </div>
  `);
  container.querySelectorAll('input,select').forEach(el => el.addEventListener('input', () => {
    if (type === 'admin') renderAdminCases(adminDashboardState.cases, adminDashboardState.pharmacists);
    else renderPharmacistDashboard(pharmacistDashboardState.pending, pharmacistDashboardState.assigned);
  }));
}

function filterCases(cases = [], type) {
  const search = (document.getElementById(`${type}-search`)?.value || '').toLowerCase();
  const status = document.getElementById(`${type}-status`)?.value || '';
  const urgency = document.getElementById(`${type}-urgency`)?.value || '';
  return cases.filter(c => {
    const haystack = `${c.patient?.full_name || ''} ${c.patient?.username || ''} ${c.symptom_area || ''} ${c.symptom_type || ''} ${c.case_summary || ''} ${c.pharmacist?.name || ''}`.toLowerCase();
    if (search && !haystack.includes(search)) return false;
    if (status && c.status !== status) return false;
    if (urgency && c.urgency_level !== urgency) return false;
    return true;
  });
}

function renderCaseCard(c) {
  const patientName = c.patient?.full_name || c.patient?.username || 'Patient';
  const assignedName = c.pharmacist?.name ? `<div class="case-details">Assigned to: ${c.pharmacist.name}</div>` : '';
  const reviewOpen = openReviewForms.has(c.id);
  const reviewForm = reviewOpen ? `
    <div class="dashboard-form">
      <input id="review-diagnosis-${c.id}" type="text" placeholder="Diagnosis note or impression">
      <textarea id="review-advice-${c.id}" placeholder="Write feedback for the patient."></textarea>
      <textarea id="review-referral-${c.id}" placeholder="Referral advice if needed"></textarea>
      <textarea id="review-followup-${c.id}" placeholder="Follow-up instructions"></textarea>
      <div class="dashboard-inline">
        <input id="review-drug-${c.id}" type="text" placeholder="Medication decision (optional)" value="${c.drug_name || ''}">
        <select id="review-status-${c.id}">
          <option value="Reviewed" ${c.status === 'Reviewed' ? 'selected' : ''}>Reviewed</option>
          <option value="Ordered" ${c.status === 'Ordered' ? 'selected' : ''}>Ordered</option>
          <option value="Delivered" ${c.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
        </select>
      </div>
      <div class="dashboard-form-actions">
        <button class="btn btn-primary btn-sm" onclick="submitCaseReview(${c.id})">Send Feedback</button>
        <button class="btn btn-secondary btn-sm" onclick="toggleReviewForm(${c.id})">Cancel</button>
      </div>
    </div>
  ` : '';
  const eventList = (c.events || []).slice(-3).map(event => `<div class="help-copy">${event.actor_role}: ${event.action} | ${event.note || 'No note'}</div>`).join('');
  return `
    <div class="case-card">
      <div class="case-header">
        <span class="case-user">${patientName}</span>
        <span class="case-time">${new Date(c.created_at).toLocaleString()}</span>
      </div>
      <div class="dashboard-meta">
        <div class="case-details"><strong>Status:</strong> ${c.status}</div>
        <div class="case-details"><strong>Urgency:</strong> ${c.urgency_level || 'routine'}</div>
        <div class="case-details"><strong>Area:</strong> ${c.symptom_area || 'General'}</div>
        <div class="case-details"><strong>Type:</strong> ${c.symptom_type || 'General'}</div>
      </div>
      <div class="case-details"><strong>Patient Summary:</strong> ${c.case_summary || c.patient_message || 'No summary provided'}</div>
      <div class="case-details"><strong>AI Intake:</strong> ${c.ai_summary || 'No AI summary recorded'}</div>
      ${c.pharmacist_feedback ? `<div class="case-details"><strong>Latest Feedback:</strong> ${c.pharmacist_feedback}</div>` : ''}
      ${assignedName}
      ${eventList}
      <div class="case-actions">
        <button class="btn-review" onclick="toggleReviewForm(${c.id})">${reviewOpen ? 'Hide Feedback Form' : 'Open Feedback Form'}</button>
      </div>
      ${reviewForm}
    </div>
  `;
}

function renderPharmacistDashboard(pendingCases = [], assignedCases = []) {
  pharmacistDashboardState = { pending: pendingCases, assigned: assignedCases };
  const q = document.getElementById('pharmacist-queue');
  if (!q) return;
  ensureDashboardToolbar('pharmacist-queue', 'pharmacist');
  const pendingFiltered = filterCases(pendingCases, 'pharmacist');
  const assignedFiltered = filterCases(assignedCases, 'pharmacist');
  const sections = [];
  if (pendingFiltered.length) sections.push(`<div class="info-card"><h4>Waiting Patients</h4>${pendingFiltered.map(renderCaseCard).join('')}</div>`);
  if (assignedFiltered.length) sections.push(`<div class="info-card"><h4>My Reviews</h4>${assignedFiltered.map(renderCaseCard).join('')}</div>`);
  const toolbar = q.querySelector('.dashboard-toolbar')?.outerHTML || '';
  q.innerHTML = toolbar + (sections.length ? sections.join('') : '<div class="empty">No cases match this filter.</div>');
}

async function submitCaseReview(id) {
  const diagnosis = document.getElementById(`review-diagnosis-${id}`)?.value.trim();
  const advice = document.getElementById(`review-advice-${id}`)?.value.trim();
  const referral_advice = document.getElementById(`review-referral-${id}`)?.value.trim();
  const follow_up_instructions = document.getElementById(`review-followup-${id}`)?.value.trim();
  const drug = document.getElementById(`review-drug-${id}`)?.value.trim();
  const statusValue = document.getElementById(`review-status-${id}`)?.value || 'Reviewed';
  if (!advice) {
    alert('Patient feedback is required.');
    return;
  }
  try {
    await callApi(`/pharmacist/review/${id}`, 'POST', { diagnosis, advice, referral_advice, follow_up_instructions, drug, status: statusValue });
    openReviewForms.delete(id);
    refreshPharmacistDashboard();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

function renderAdminCases(cases = [], pharmacists = []) {
  adminDashboardState = { cases, pharmacists };
  const el = document.getElementById('admin-cases-list');
  if (!el) return;
  ensureDashboardToolbar('admin-cases-list', 'admin');
  const filteredCases = filterCases(cases, 'admin');
  const toolbar = el.querySelector('.dashboard-toolbar')?.outerHTML || '';
  el.innerHTML = toolbar + (filteredCases.length ? filteredCases.map(c => {
    const options = pharmacists.map(p => `<option value="${p.id}" ${c.pharmacist?.id === p.id ? 'selected' : ''}>${p.full_name || p.username}</option>`).join('');
    const patientName = c.patient?.full_name || c.patient?.username || 'Patient';
    return `
      <div class="case-card">
        <div class="case-header">
          <span class="case-user">${patientName}</span>
          <span class="case-time">${new Date(c.created_at).toLocaleString()}</span>
        </div>
        <div class="dashboard-meta">
          <div class="case-details"><strong>Status:</strong> ${c.status}</div>
          <div class="case-details"><strong>Urgency:</strong> ${c.urgency_level || 'routine'}</div>
          <div class="case-details"><strong>Area:</strong> ${c.symptom_area || 'General'}</div>
          <div class="case-details"><strong>Assigned Clinician:</strong> ${c.pharmacist?.name || 'Unassigned'}</div>
        </div>
        <div class="case-details"><strong>Case Summary:</strong> ${c.case_summary || c.patient_message || 'No summary provided'}</div>
        <div class="case-actions" style="align-items:stretch;">
          <div class="dashboard-inline">
            <select id="assign-case-${c.id}">
              <option value="">Assign clinician</option>
              ${options}
            </select>
            <button class="btn btn-secondary btn-sm" onclick="assignCase(${c.id})">Assign</button>
          </div>
          <div class="help-copy">Assigning moves the case into active clinical review.</div>
        </div>
      </div>
    `;
  }).join('') : '<div class="empty">No cases match this filter.</div>');
}

async function refreshPharmacistDashboard() {
  if (currentSession.role !== 'pharmacist') return;
  try {
    const data = await callApi('/pharmacist/dashboard');
    document.getElementById('pending-count').textContent = `${data.stats.pending_cases} Pending`;
    document.getElementById('ph-stat-pending').textContent = data.stats.pending_cases;
    document.getElementById('ph-stat-assigned').textContent = data.stats.assigned_cases;
    document.getElementById('ph-stat-reviewed').textContent = data.stats.reviewed_cases;
    document.getElementById('ph-stat-verified').textContent = data.pharmacist.is_verified ? 'Yes' : 'No';
    renderPharmacistDashboard(data.pending_cases, data.assigned_cases);
  } catch (e) {
    console.error(e);
  }
}

async function refreshAdminDashboard() {
  if (currentSession.role !== 'admin') return;
  try {
    const data = await callApi('/admin/dashboard');
    document.getElementById('admin-total-users').textContent = data.stats.total_users;
    document.getElementById('admin-total-pharmacists').textContent = data.stats.total_pharmacists;
    document.getElementById('admin-pending-cases').textContent = data.stats.pending_cases;
    document.getElementById('admin-verified-pharmacists').textContent = data.stats.verified_pharmacists;
    renderAdminPharmacists(data.pharmacists);
    renderAdminCases(data.cases, data.pharmacists);
  } catch (e) {
    console.error(e);
  }
}

function updateAuthUI() {
  const loggedIn = isLoggedIn();
  const authFooter = document.getElementById('auth-footer');
  const userFooter = document.getElementById('user-footer');
  const navChat = document.getElementById('nav-chat');
  const navBodymap = document.getElementById('nav-bodymap');
  const navConditions = document.getElementById('nav-conditions');
  const navRedflag = document.getElementById('nav-redflag');
  const navProfile = document.getElementById('nav-profile');
  const navConnect = document.getElementById('nav-connect');
  const navHistory = document.getElementById('nav-history');
  const navPharmacist = document.getElementById('nav-pharmacist');
  const navAdmin = document.getElementById('nav-admin');
  const isPatientView = currentSession.role === 'guest' || currentSession.role === 'user';
  const isAdminView = currentSession.role === 'admin';
  const isClinicianView = currentSession.role === 'pharmacist';
  if (authFooter) authFooter.style.display = loggedIn ? 'none' : 'block';
  if (userFooter) userFooter.style.display = loggedIn ? 'block' : 'none';
  if (loggedIn) {
    const label = document.getElementById('user-label');
    if (label) {
      const roleLabel = currentSession.role === 'admin' ? 'Admin' : currentSession.role === 'pharmacist' ? 'Clinician' : 'Patient';
      label.textContent = `${currentSession.display_name || currentUser || 'User'} · ${roleLabel}`;
    }
  }
  if (navChat) navChat.style.display = isAdminView || isClinicianView ? 'none' : 'flex';
  if (navBodymap) navBodymap.style.display = isAdminView || isClinicianView ? 'none' : 'flex';
  if (navConditions) navConditions.style.display = isAdminView || isClinicianView ? 'none' : 'flex';
  if (navRedflag) navRedflag.style.display = isAdminView || isClinicianView ? 'none' : 'flex';
  if (navProfile) navProfile.style.display = currentSession.role === 'user' ? 'flex' : 'none';
  if (navHistory) navHistory.style.display = currentSession.role === 'user' ? 'flex' : 'none';
  if (navConnect) navConnect.style.display = isPatientView ? 'flex' : 'none';
  if (navPharmacist) navPharmacist.style.display = currentSession.role === 'pharmacist' ? 'flex' : 'none';
  if (navAdmin) navAdmin.style.display = currentSession.role === 'admin' ? 'flex' : 'none';
}

function newChat() {
  history = [];
  const msgs = document.getElementById('msgs');
  if (msgs) msgs.innerHTML = '';
  addMsg('ai', LANGS[lang].greeting, [{ t: 'BisaRx', c: 'g' }, { t: 'Clinical AI', c: 'b' }, { t: 'Multilingual', c: 'a' }]);
  closeMobileMenu();
  const nav = document.getElementById('nav-chat');
  if (nav) go('chat', nav);
}

async function initApp() {
  await fetchSessionContext();
  updateAuthUI();
  buildLang();
  renderBodyMapLanding();
  await loadCareTeam();

  try {
    const refData = await callApi('/reference');
    buildConditions(refData.conditions);
    buildRedFlags(refData.red_flags);
  } catch (e) {
    console.warn('Failed to load reference data, using defaults', e);
    buildConditions(window.FALLBACK_CONDITIONS || []);
    buildRedFlags(window.FALLBACK_REDFLAGS || []);
  }

  if (currentSession.role === 'user') {
    await loadProfileData();
  } else {
    const pc = document.getElementById('profile-content');
    const pp = document.getElementById('profile-auth-prompt');
    const hc = document.getElementById('history-content');
    const hp = document.getElementById('history-auth-prompt');
    if (pc) pc.style.display = 'none';
    if (pp) pp.style.display = 'block';
    if (hc) hc.style.display = 'none';
    if (hp) hp.style.display = 'block';
  }

  if (currentSession.role === 'pharmacist') {
    const nav = document.getElementById('nav-pharmacist');
    if (nav) go('pharmacist', nav);
    refreshPharmacistDashboard();
    return;
  }
  if (currentSession.role === 'admin') {
    const nav = document.getElementById('nav-admin');
    if (nav) go('admin', nav);
    refreshAdminDashboard();
    return;
  }

  addMsg('ai', LANGS[lang].greeting, [{ t: 'BisaRx', c: 'g' }, { t: 'Clinical AI', c: 'b' }, { t: 'Multilingual', c: 'a' }]);
}
