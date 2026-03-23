const API_URL = '/api';

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
  sidebar.classList.toggle('open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  const mobileBtn = document.querySelector('.mobile-menu-btn');
  if (sidebar && mobileBtn && sidebar.classList.contains('open')) {
    if (!sidebar.contains(e.target) && !mobileBtn.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  }
});

let currentUser = null;
let lang = 'en', history = [], ttsOn = false, isRecording = false, recognition = null;
const synth = window.speechSynthesis;

const LANGS={
  en:{greeting:"Hello sweetheart! I'm here to help you feel better. How are you feeling today? Don't worry, we'll work through this together, one step at a time. Just tell me what's going on with you.",chips:["I have a headache","My stomach hurts","I feel feverish","I have a cough","My child is sick","I have a skin rash"],placeholder:"Tell me how you're feeling... I care about you",disc:"Based on standard health guidelines. Does not replace a licensed pharmacist or physician.",discLabel:"Disclaimer:"},
  tw:{greeting:"Akwaaba, me panyin! Mewo hɔ na mebɛtumi akyɛ wo. Sɛn na ɛwo hɔ ɛnnɛ? Mɛfrɛ wo sɛ kɔ so, yɛbɛyɛ ne akatua. Ka me nkyɛn sɛdeɛ wo te wo ho.",chips:["Me ti yɛ me yaw","Me yafunu yɛ me yaw","Mewɔ atiridiinini","Mewɔ ekoɔ","Me ba yareɛ","Mewɔ honam yareɛ"],placeholder:"Ka me nkyɛn sɛdeɛ wo te wo ho...",disc:"Wɔ atwerɛ wɔ standard health guidelines so. Ɛnsesa oduruyɛfo anaasɛ ɔdɔkotaa.",discLabel:"Nkɔmmɔdie:"},
  ha:{greeting:"Sannu! Na gode ina nan jira. Mene ne matsalar ku yau? Kada ku damu, za mu taimaka wa tare. Ku gaya mini yadda kuke ji.",chips:["Ina da ciwon kai","Ciki na yi mini ciwo","Ina da zazzabi","Ina da tari","Ɗana ba shi da lafiya","Ina da kuraje"],placeholder:"Gaya mini yadda kake ji... ina kula da kai",disc:"Ya dogara ne akan standard health guidelines. Baya maye gurbin likita ko mai magani.",discLabel:"Gargaɗi:"},
  fr:{greeting:"Bonjour mon ami! Je suis là pour vous aider à vous sentir mieux. Comment vous sentez-vous aujourd'hui? Ne vous inquiétez pas, nous allons résoudre cela ensemble. Dites-moi ce qui se passe.",chips:["J'ai mal a la tete","J'ai mal au ventre","J'ai de la fievre","Je tousse","Mon enfant est malade","J'ai une eruption cutanee"],placeholder:"Dites-moi comment vous vous sentez... je me soucie de vous",disc:"Base sur des directives de sante standards. Ne remplace pas un pharmacien agree.",discLabel:"Avertissement:"}
};

const ZONES={head:{title:'Head & Brain',sub:'Headache, dizziness, fever, vision changes',q:'I have pain in my head. Please assess.'},throat:{title:'Throat & Neck',sub:'Sore throat, difficulty swallowing, neck stiffness',q:'I have throat or neck discomfort. Please assess.'},chest:{title:'Chest & Lungs',sub:'Cough, shortness of breath, chest pain',q:'I have chest pain or breathing difficulty. Please assess.'},abdomen:{title:'Abdomen',sub:'Stomach pain, nausea, vomiting, diarrhea',q:'I have abdominal pain or stomach discomfort. Please assess.'},arm:{title:'Arms & Joints',sub:'Arm pain, joint swelling, muscle aches',q:'I have pain in my arms or joints. Please assess.'},lower:{title:'Lower Abdomen',sub:'Lower cramps, urinary problems, menstrual pain',q:'I have lower abdominal or urinary symptoms. Please assess.'},leg:{title:'Legs',sub:'Leg pain, swelling, muscle weakness',q:'I have pain or swelling in my legs. Please assess.'},foot:{title:'Feet & Ankles',sub:'Foot pain, ankle swelling, wounds',q:'I have pain or wounds in my feet. Please assess.'}};

const CONDITIONS=[{name:'Malaria / Fever',drug:'Artemether + Lumefantrine',tags:[{t:'Coartem®',c:'g'},{t:'6 doses/3 days',c:'b'},{t:'With food',c:'a'}],q:'Tell me about malaria symptoms and Coartem treatment.'},{name:'Headache',drug:'Paracetamol / Ibuprofen',tags:[{t:'Tension',c:'b'},{t:'Migraine',c:'b'},{t:'Refer if severe',c:'r'}],q:'Headache assessment and first-line treatment?'},{name:'Diarrhea',drug:'ORS + Zinc 10–20mg',tags:[{t:'Rehydration',c:'g'},{t:'Zinc',c:'b'},{t:'Metronidazole if amoebic',c:'a'}],q:'Diarrhea management advice.'},{name:'Cough / URTI',drug:'Steam / Guaifenesin',tags:[{t:'Fluids',c:'g'},{t:'Antibiotic if bacterial',c:'a'},{t:'Refer if SOB',c:'r'}],q:'Cough and cold management?'},{name:'Abdominal Pain',drug:'Antacid / Omeprazole',tags:[{t:'Gastritis',c:'b'},{t:'NSAID for cramps',c:'g'},{t:'Refer if severe',c:'r'}],q:'Abdominal pain assessment?'},{name:'Skin Rash',drug:'Hydrocortisone / Clotrimazole',tags:[{t:'Allergic',c:'a'},{t:'Fungal',c:'b'},{t:'Antihistamine',c:'g'}],q:'Skin rash first-line treatment?'},{name:'Urinary Complaints',drug:'Nitrofurantoin / Ciprofloxacin',tags:[{t:'UTI',c:'b'},{t:'Refer if pregnant',c:'r'},{t:'Fluids',c:'g'}],q:'Urinary tract complaint management?'},{name:'Hypertension',drug:'Amlodipine 5mg OD',tags:[{t:'BP monitoring',c:'b'},{t:'Adherence',c:'g'},{t:'Refer if uncontrolled',c:'r'}],q:'Hypertension counseling guidelines?'},{name:'Diabetes',drug:'Metformin (first-line)',tags:[{t:'Type 2 DM',c:'b'},{t:'Monitor glucose',c:'g'},{t:'Refer if uncontrolled',c:'a'}],q:'Diabetes medication counseling?'},{name:'Pain / Inflammation',drug:'Paracetamol / Diclofenac gel',tags:[{t:'NSAID',c:'b'},{t:'Topical option',c:'g'},{t:'Avoid overuse',c:'a'}],q:'Pain and inflammation management?'}];

const REDFLAGS=[{condition:'Malaria / Severe Fever',flags:['Cannot keep oral medication down','Confusion, convulsions, or severe weakness','Yellowing of eyes or dark urine','Fever lasting more than 3 days despite treatment','Pregnant or infant under 6 months']},{condition:'Head / Neurological',flags:['Sudden severe thunderclap headache','Neck stiffness with fever','Vision changes or slurred speech','Headache after head injury']},{condition:'Breathing / Chest',flags:['Difficulty breathing at rest','Coughing blood','Rapid breathing in children','Productive cough with fever over 3 days']},{condition:'Stomach / Abdomen',flags:['Severe dehydration — sunken eyes, no urine','Blood or mucus in stool','Rigid board-like abdomen','Multiple household members ill']},{condition:'General Danger Signs',flags:['Altered consciousness or unconsciousness','Uncontrolled bleeding','Pregnancy with acute serious illness','Patient cannot stand or self-care']}];

// AUTH helper
function getToken() { return localStorage.getItem('token'); }

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
      if(attempt < retries) {
        // Wait before retry (exponential backoff)
        await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 500));
      }
    }
  }
  throw lastError;
}

// UI AUTH
function switchAuthTab(t){
  document.getElementById('tab-login').classList.toggle('on',t==='login');
  document.getElementById('tab-reg').classList.toggle('on',t==='register');
  document.getElementById('form-login').style.display=t==='login'?'block':'none';
  document.getElementById('form-register').style.display=t==='register'?'block':'none';
}
function checkStrength(pw){
  const fill=document.getElementById('strength-fill'),lbl=document.getElementById('strength-label');
  let s=0;if(pw.length>=6)s++;if(pw.length>=10)s++;if(/[A-Z]/.test(pw))s++;if(/[0-9]/.test(pw))s++;if(/[^a-zA-Z0-9]/.test(pw))s++;
  fill.style.width=Math.round((s/5)*100)+'%';
  if(s<=1){fill.style.background='var(--red)';lbl.textContent='Weak';}else if(s<=3){fill.style.background='var(--amber)';lbl.textContent='Fair';}else{fill.style.background='var(--accent)';lbl.textContent='Strong';}
}

async function doLogin(){
  const username=document.getElementById('login-username').value.trim().toLowerCase();
  const pass=document.getElementById('login-pass').value;
  const err=document.getElementById('login-err');
  if(!username||!pass) {err.innerHTML='<div class="err">Please enter username and password.</div>'; return;}

  try{
    const body=new URLSearchParams(); body.append('username',username); body.append('password',pass);
    const data = await callApi('/auth/login', 'POST', body);
    localStorage.setItem('token', data.access_token);
    err.innerHTML=''; currentUser=username; launchApp();
  }catch(e){
    err.innerHTML=`<div class="err">${e.message}</div>`;
  }
}

function doGoogleLogin(){
  window.location.href = '/api/auth/google/login';
}

async function doRegister(){
  const fn=document.getElementById('reg-fname').value.trim(),ln=document.getElementById('reg-lname').value.trim();
  const username=document.getElementById('reg-username').value.trim().toLowerCase();
  const email=document.getElementById('reg-email').value.trim().toLowerCase();
  const pass=document.getElementById('reg-pass').value,pass2=document.getElementById('reg-pass2').value;
  const err=document.getElementById('reg-err');
  if(!fn||!ln||!username||!email||!pass){err.innerHTML='<div class="err">Please fill all fields.</div>';return;}
  if(pass.length<6){err.innerHTML='<div class="err">Password must be at least 6 characters.</div>';return;}
  if(pass!==pass2){err.innerHTML='<div class="err">Passwords do not match.</div>';return;}

  try{
    const data = await callApi('/auth/register', 'POST', {username, email, password:pass, first_name:fn, last_name:ln});
    localStorage.setItem('token', data.access_token);
    err.innerHTML='<div class="ok">Account created! Signing you in...</div>'; currentUser=username; setTimeout(launchApp,600);
  }catch(e){
    err.innerHTML=`<div class="err">${e.message}</div>`;
  }
}

function signOut() {
    localStorage.removeItem("token");
    window.location.reload();
}

function launchApp(prefetchedData=null){
  document.getElementById('login-gate').style.display='none';
  document.getElementById('main-app').style.display='block';
  initApp(prefetchedData);
}

function consumeTokenFromUrl() {
  const url = new URL(window.location.href);
  const token = url.searchParams.get('token');
  if (!token) return null;

  localStorage.setItem('token', token);
  url.searchParams.delete('token');
  window.history.replaceState({}, document.title, url.toString());
  return token;
}

async function initApp(prefetchedData=null){
  buildLang();
  
  // Fetch conditions and red flags from the API (from dataset)
  try {
    const refData = await callApi('/reference');
    buildConditions(refData.conditions);
    buildRedFlags(refData.red_flags);
  } catch(e) {
    console.warn("Failed to load reference data, using defaults", e);
    // Fallback to hardcoded data
    buildConditions(window.FALLBACK_CONDITIONS || []);
    buildRedFlags(window.FALLBACK_REDFLAGS || []);
  }
  
  try{
      const data = prefetchedData || await callApi('/profile');
      loadPersonalForm(data.profile);
      loadMedicalForm(data.medical, data.conditions, data.allergies);
      loadMedsList(data.medications);
      loadEmergencyForm(data.emergency);
      refreshOverview(data);
      renderPrescriptionHistory(data.prescriptions);
  }catch(e){
      console.warn("Failed to load profile", e);
  }
  addMsg('ai',LANGS[lang].greeting,[{t:'AI Assistant',c:'g'},{t:'Voice Ready',c:'b'},{t:'Multilingual',c:'a'}]);
}

async function restoreSessionFromRedirect() {
  const token = consumeTokenFromUrl();
  if (!token) {
    localStorage.removeItem('token');
    return;
  }

  try {
    const data = await callApi('/profile');
    launchApp(data);
  } catch (e) {
    localStorage.removeItem('token');
    console.warn('Failed to restore redirected session', e);
  }
}

window.onload = () => {
  restoreSessionFromRedirect();
}

function buildLang(){
  const L=LANGS[lang];
  document.getElementById('chat-title').textContent=lang==='en'?'AI Pharmacist':lang==='tw'?'AI Oduruyɛfo':lang==='ha'?'AI Likitan Magani':'Pharmacien IA';
  document.getElementById('chat-sub').textContent='AI Powered · Voice · Multilingual';
  document.getElementById('disc-label').textContent=L.discLabel;
  document.getElementById('disc-text').textContent=L.disc;
  document.getElementById('tinput').placeholder=L.placeholder;
  document.getElementById('lang-badge').textContent=lang.toUpperCase();
  const chipsEl=document.getElementById('chips');chipsEl.innerHTML='';
  L.chips.forEach(c=>{const d=document.createElement('div');d.className='chip';d.textContent=c;d.onclick=()=>{document.getElementById('tinput').value=c;chipsEl.style.display='none';send();};chipsEl.appendChild(d);});
}
function setLang(l,el){lang=l;document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('on'));el.classList.add('on');buildLang();}

function go(name,el){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('on'));
  document.getElementById('panel-'+name).classList.add('on');
  if(el)el.classList.add('on');
  // Close mobile sidebar after navigation
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.remove('open');
}

// CHAT
function addMsg(role,text,tags,msgId=null){
  const c=document.getElementById('msgs'),d=document.createElement('div');
  d.className='msg'+(role==='user'?' u':'');
  const messageId = msgId || 'msg_' + Date.now();
  const tagsHtml=tags?`<div class="tr">${tags.map(t=>`<span class="bt ${t.c}">${t.t}</span>`).join('')}</div>`:'';
  const voiceBtnHtml = role==='ai'?`<button class="msg-voice-btn" onclick="speakMsg('${messageId}', this)" title="Listen to this message">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg>
    <span>Listen</span>
  </button>`:'';
  
  // Use marked for AI messages to support formatting
  const formattedText = role === 'ai' && window.marked ? marked.parse(text) : text.replace(/\n/g,'<br>');
  
  d.innerHTML=`<div class="av ${role==='user'?'u':'ai'}">${role==='user'?'You':'Rx'}</div>
  <div class="bub ${role==='user'?'u':'ai'}" id="${messageId}">
    <div class="bub-text">${formattedText}${tagsHtml}</div>
    ${voiceBtnHtml}
  </div>`;
  c.appendChild(d);c.scrollTop=c.scrollHeight;
  return messageId;
}

// Speak a specific message by ID
function speakMsg(msgId, btn) {
  const msgEl = document.getElementById(msgId);
  if (!msgEl) return;
  
  const text = msgEl.querySelector('.bub-text').textContent;
  
  // Toggle between play and stop
  if (btn.classList.contains('speaking')) {
    if (synth) synth.cancel();
    btn.classList.remove('speaking');
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg><span>Listen</span>`;
  } else {
    // Stop any current speech first
    if (synth) synth.cancel();
    
    // Remove speaking class from all buttons
    document.querySelectorAll('.msg-voice-btn.speaking').forEach(b => {
      b.classList.remove('speaking');
      b.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
      </svg><span>Listen</span>`;
    });
    
    btn.classList.add('speaking');
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="6" y="4" width="4" height="16"/>
      <rect x="14" y="4" width="4" height="16"/>
    </svg><span>Stop</span>`;
    
    const utt = new SpeechSynthesisUtterance(text.replace(/<[^>]*>/g, ''));
    utt.rate = 0.88;
    utt.pitch = 1.0;
    utt.lang = lang === 'fr' ? 'fr-FR' : lang === 'ha' ? 'ha-NG' : lang === 'tw' ? 'ak-GH' : 'en-GH';
    utt.onend = () => {
      btn.classList.remove('speaking');
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
      </svg><span>Listen</span>`;
    };
    utt.onerror = () => {
      btn.classList.remove('speaking');
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
      </svg><span>Listen</span>`;
    };
    synth.speak(utt);
  }
}
function showTyping(){const c=document.getElementById('msgs'),d=document.createElement('div');d.className='msg';d.id='typing';d.innerHTML=`<div class="av ai">Rx</div><div class="bub ai" style="padding:7px 13px"><div class="typing"><span></span><span></span><span></span></div></div>`;c.appendChild(d);c.scrollTop=c.scrollHeight;}
function rmTyping(){const e=document.getElementById('typing');if(e)e.remove();}
function autoR(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,100)+'px';}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}

function addDrugCards(drugs) {
  const c = document.getElementById('msgs');
  const wrapper = document.createElement('div');
  wrapper.className = 'drug-cards-wrapper';
  wrapper.innerHTML = `<div class="drug-cards-header"><span class="drug-cards-icon">&#128138;</span> Here are some medications that might help you feel better, sweetheart</div>`;
  drugs.forEach(drug => {
    const card = document.createElement('div');
    card.className = 'drug-card';
    const dosageInstructions = drug.dosage_instructions || 'Take as directed by your pharmacist or doctor';
    card.innerHTML = `
      <div class="drug-card-name">${drug.name}</div>
      <div class="drug-card-row"><span class="drug-card-label">For:</span> ${drug.indication || drug.category}</div>
      <div class="drug-card-row"><span class="drug-card-label">Form:</span> ${drug.dosage_form || 'As available'}</div>
      <div class="drug-card-row"><span class="drug-card-label">Strength:</span> ${drug.strength || 'Standard'}</div>
      <div class="drug-card-dosage"><span class="drug-card-label">How to take:</span> ${dosageInstructions}</div>
      <div class="drug-card-row"><span class="drug-card-label">Type:</span> ${drug.classification || 'Over-the-counter'}</div>
    `;
    wrapper.appendChild(card);
  });
  c.appendChild(wrapper);
  c.scrollTop = c.scrollHeight;
}

async function send(){
  const input=document.getElementById('tinput'),btn=document.getElementById('send-btn');
  const text=input.value.trim();if(!text)return;
  addMsg('user',text);history.push({role:'user',content:text});
  input.value='';input.style.height='auto';btn.disabled=true;showTyping();
  document.getElementById('chips').style.display='none';
  try{
    const res = await callApi('/chat', 'POST', {messages: history});
    const reply=res.reply||'Sorry, please try again.';
    rmTyping();

    if(res.consulting && res.drugs && res.drugs.length > 0) {
      // Show the caring "hold on" transition message
      addMsg('ai', 'Oh sweetie, just give me a moment while I look up the best options for you... I want to make sure we find something that will help you feel better soon', [{t:'Consulting',c:'a'}]);
      if(ttsOn) speak('Oh sweetie, just give me a moment while I look up the best options for you');

      // Brief pause to make it feel real
      await new Promise(r => setTimeout(r, 2000));

      // Now show the pharmacist's summary
      addMsg('ai', reply);
      history.push({role:'assistant',content:reply});

      // Show drug recommendation cards
      addDrugCards(res.drugs);

      addMsg('ai', 'I really hope one of these helps you feel better, darling. Please remember to consult with a licensed pharmacist or doctor before taking any medication, especially if you have any allergies. And please, take good care of yourself. Is there anything else I can help you with? I\'m here for you', [{t:'Drug Match',c:'g'},{t:'Consultation',c:'b'}]);
    } else {
      // Normal conversational exchange (still gathering info)
      addMsg('ai', reply);
      history.push({role:'assistant',content:reply});
      if(ttsOn) speak(reply);
    }

    document.getElementById('ai-summary').textContent=`Patient: "${text.substring(0,100)}..."\n\nAI: ${reply.substring(0,250)}...`;
    showDynamicChips(reply);
    
    // Refresh history dynamically
    const data = await callApi('/profile');
    renderPrescriptionHistory(data.prescriptions);

  }catch(e){
    rmTyping();
    // Friendly error message displayed in chat box with caring tags
    const errorMsg = 'I\'m sorry sweetheart, something went wrong on my end. Please try again in a moment, and I\'ll be right here to help you. Take care!';
    addMsg('ai', errorMsg, [{t:'Error',c:'r'},{t:'Try Again',c:'a'}]);
    // Log error for debugging
    console.error('Chat error:', e.message);
  }
  btn.disabled=false;
}

// TTS & VOICE
function speak(text){
  if(!synth)return;synth.cancel();
  const maxLen = 300; // Speak in chunks to avoid cutoff
  if (text.length > maxLen) {
    const chunks = text.match(new RegExp('.{1,' + maxLen + '}(\\s|$)', 'g')) || [text];
    let i = 0;
    const speakNext = () => {
      if (i < chunks.length) {
        const utt = new SpeechSynthesisUtterance(chunks[i].replace(/<[^>]*>/g, ''));
        utt.rate = 0.88;
        utt.pitch = 1.0;
        utt.lang = lang === 'fr' ? 'fr-FR' : lang === 'ha' ? 'ha-NG' : lang === 'tw' ? 'ak-GH' : 'en-GH';
        const btn = document.getElementById('spk-btn');
        utt.onstart = () => btn.classList.add('speaking');
        utt.onend = () => {
          i++;
          if (i < chunks.length) speakNext();
          else btn.classList.remove('speaking');
        };
        synth.speak(utt);
      }
    };
    speakNext();
  } else {
    const utt = new SpeechSynthesisUtterance(text.replace(/<[^>]*>/g, ''));
    utt.rate = 0.88;
    utt.pitch = 1.0;
    utt.lang = lang === 'fr' ? 'fr-FR' : lang === 'ha' ? 'ha-NG' : lang === 'tw' ? 'ak-GH' : 'en-GH';
    const btn = document.getElementById('spk-btn');
    utt.onstart = () => btn.classList.add('speaking');
    utt.onend = () => btn.classList.remove('speaking');
    synth.speak(utt);
  }
}
function showDynamicChips(reply){
  const chipsEl = document.getElementById('chips');
  chipsEl.innerHTML = '';
  const dynamicChips = [];
  
  const lowerReply = reply.toLowerCase();
  
  // Always show some options
  dynamicChips.push('Ask another question', 'View my profile');
  
  // Add specific ones based on content
  if (lowerReply.includes('medication') || lowerReply.includes('drug') || lowerReply.includes('take') || lowerReply.includes('paracetamol') || lowerReply.includes('ibuprofen') || lowerReply.includes('coartem') ||
      lowerReply.includes('ɔdɔ') || lowerReply.includes('aduro') || lowerReply.includes('faa') || lowerReply.includes('paracetamol') || lowerReply.includes('ibuprofen')) {  // Twi keywords
    dynamicChips.unshift('Order this medication', 'More details on dosage', 'Ask about side effects');
  }
  
  if (lowerReply.includes('symptom') || lowerReply.includes('pain') || lowerReply.includes('fever') ||
      lowerReply.includes('yareɛ') || lowerReply.includes('yaw') || lowerReply.includes('atiri')) {  // Twi
    dynamicChips.push('Tell me more about my symptoms', 'What should I avoid?');
  }
  
  if (lowerReply.includes('hospital') || lowerReply.includes('refer') || lowerReply.includes('emergency') ||
      lowerReply.includes('ɔdɔkota') || lowerReply.includes('ahɔho')) {  // Twi
    dynamicChips.push('Find nearest hospital', 'Call emergency');
  }
  
  dynamicChips.forEach(c => {
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
  
  chipsEl.style.display = 'flex';
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
  document.querySelectorAll('.body-zone').forEach(el=>{el.setAttribute('stroke','#2a3050');el.setAttribute('fill','#1a1e2b');});
  document.querySelectorAll(`[data-zone="${zone}"]`).forEach(el=>{el.setAttribute('stroke','#3dd68c');el.setAttribute('fill','rgba(61,214,140,0.12)');});
  document.getElementById('bodymap-info').innerHTML=`<div class="zone-card"><div class="zone-title">${z.title}</div><div class="zone-sub">${z.sub}</div><div class="zone-btns"><button class="zbtn primary" onclick="askZone('${zone}')">Ask AI about this &#10148;</button></div></div>`;
}
function askZone(zone){go('chat',document.querySelector('.nav'));document.getElementById('tinput').value=ZONES[zone].q;send();}


function buildConditions(conditionsData){
  const g=document.getElementById('cgrid');
  g.innerHTML = ''; // Clear existing content
  
  // Use data from API if available, otherwise use fallback
  const conditions = conditionsData && conditionsData.length > 0 ? conditionsData : CONDITIONS;
  
  conditions.forEach(c=>{
    const d=document.createElement('div');
    d.className='ccard';
    d.innerHTML=`<div class="cname">${c.name}</div><div class="cdrug">${c.drug}</div><div class="ctags">${(c.tags || []).map(t=>`<span class="ctag ${t.c}">${t.t}</span>`).join('')}</div>`;
    d.onclick=()=>{go('chat',document.querySelector('.nav'));document.getElementById('tinput').value=c.q || `Tell me about ${c.name}`;send();};
    g.appendChild(d);
  });
}


function buildRedFlags(redFlagsData){
  const b=document.getElementById('rfbody');
  
  // Use data from API if available, otherwise use fallback
  const redFlags = redFlagsData && redFlagsData.length > 0 ? redFlagsData : REDFLAGS;
  
  b.innerHTML=`<div style="font-size:11px;color:var(--muted2);line-height:1.6;margin-bottom:14px">The following signs require <strong style="color:var(--red)">immediate referral</strong> to a hospital.</div>`;
  
  redFlags.forEach(rf=>{
    const box=document.createElement('div');
    box.className='rfbox';
    box.innerHTML=`<div class="rftitle">&#9888; ${rf.condition}</div>${(rf.flags || []).map(f=>`<div class="rfitem">${f}</div>`).join('')}`;
    b.appendChild(box);
  });
}


// PROFILE
function showPTab(tab,el){['overview','personal','medical','medications','emergency'].forEach(t=>document.getElementById('ptab-'+t).style.display=t===tab?'block':'none');document.querySelectorAll('.ntab').forEach(n=>n.classList.remove('on'));if(el)el.classList.add('on');}
function refreshOverview(u){
  const p=u.profile||{},m=u.medical||{},meds=u.medications||[], conditionsList=u.conditions||[], allergiesList=u.allergies||[];
  document.getElementById('ov-blood').textContent=p.blood_type||'--';
  if(p.dob){const age=Math.floor((new Date()-new Date(p.dob))/(365.25*24*3600*1000));document.getElementById('ov-age').textContent=isNaN(age)?'--':age;}else document.getElementById('ov-age').textContent='--';
  document.getElementById('ov-conds').textContent=(conditionsList).length;
  document.getElementById('ov-allergies').textContent=(allergiesList).length;
  const active=meds.filter(x=>x.status==='Active');
  document.getElementById('ov-meds-list').innerHTML=active.length?active.map(x=>`<div class="med-item" style="margin-bottom:6px"><div><div class="med-name">${x.name}</div><div class="med-dose">${x.dose} · ${x.freq}</div></div><span class="badge g">Active</span></div>`).join(''):'<div style="font-size:12px;color:var(--muted)">None recorded</div>';
  document.getElementById('ov-allergy-list').innerHTML=(allergiesList).length?(allergiesList).map(a=>`<span class="allergy-chip" style="cursor:default">${a}</span>`).join(''):'<div style="font-size:12px;color:var(--muted)">None recorded</div>';
  document.getElementById('ov-conds-list').innerHTML=(conditionsList).length?(conditionsList).map(c=>`<span class="cond-chip" style="cursor:default">${c}</span>`).join(''):'<div style="font-size:12px;color:var(--muted)">None recorded</div>';
}
async function selBlood(btn,type){
    document.querySelectorAll('.blood-btn').forEach(b=>b.classList.remove('sel'));btn.classList.add('sel');
    document.getElementById('ov-blood').textContent=type;
}

let conditions=[],allergies=[];

function loadPersonalForm(p){
    document.getElementById('p-fname').value=p.first_name||'';document.getElementById('p-lname').value=p.last_name||'';
    document.getElementById('p-phone').value=p.phone||'';document.getElementById('p-dob').value=p.dob||'';
    document.getElementById('p-address').value=p.address||'';document.getElementById('p-city').value=p.city||'';
    document.getElementById('p-ghcard').value=p.gh_card||'';document.getElementById('p-gender').value=p.gender||'';
    if(p.blood_type)document.querySelectorAll('.blood-btn').forEach(b=>{if(b.textContent===p.blood_type)b.classList.add('sel');});
}
async function savePersonal(){
    const p = {
        first_name: document.getElementById('p-fname').value.trim(),
        last_name: document.getElementById('p-lname').value.trim(),
        phone: document.getElementById('p-phone').value.trim(),
        dob: document.getElementById('p-dob').value,
        gender: document.getElementById('p-gender').value,
        address: document.getElementById('p-address').value.trim(),
        city: document.getElementById('p-city').value.trim(),
        gh_card: document.getElementById('p-ghcard').value.trim(),
        blood_type: document.getElementById('ov-blood').textContent !== '--' ? document.getElementById('ov-blood').textContent : ''
    };
    try {
        await callApi('/profile/personal', 'PUT', p);
        document.getElementById('personal-msg').innerHTML='<div class="ok">Saved!</div>';setTimeout(()=>document.getElementById('personal-msg').innerHTML='',2000);
    } catch(e){
        document.getElementById('personal-msg').innerHTML=`<div class="err">${e.message}</div>`;
    }
}

function loadMedicalForm(m, condList, allList){
    conditions=[...condList];allergies=[...allList];
    document.getElementById('p-smoking').value=m.smoking||'';document.getElementById('p-alcohol').value=m.alcohol||'';
    document.getElementById('p-notes').value=m.notes||'';renderCondTags();renderAllergyTags();
}
function renderCondTags(){document.getElementById('conds-tags').innerHTML=conditions.map((c,i)=>`<span class="cond-chip" onclick="removeItem('cond',${i})">${c} <span style="font-size:10px;opacity:.7">x</span></span>`).join('');}
function renderAllergyTags(){document.getElementById('allergy-tags').innerHTML=allergies.map((a,i)=>`<span class="allergy-chip" onclick="removeItem('allergy',${i})">${a} <span style="font-size:10px;opacity:.7">x</span></span>`).join('');}
function addCondition(){const v=document.getElementById('cond-input').value.trim();if(!v)return;if(!conditions.includes(v))conditions.push(v);document.getElementById('cond-input').value='';renderCondTags();}
function addAllergy(){const v=document.getElementById('allergy-input').value.trim();if(!v)return;if(!allergies.includes(v))allergies.push(v);document.getElementById('allergy-input').value='';renderAllergyTags();}
function removeItem(type,i){if(type==='cond'){conditions.splice(i,1);renderCondTags();}else{allergies.splice(i,1);renderAllergyTags();}}

async function saveMedical(){
    const m = {
        smoking: document.getElementById('p-smoking').value,
        alcohol: document.getElementById('p-alcohol').value,
        notes: document.getElementById('p-notes').value.trim(),
        conditions, allergies
    };
    try {
        await callApi('/profile/medical', 'PUT', m);
        const data = await callApi('/profile'); refreshOverview(data);
        document.getElementById('medical-msg').innerHTML='<div class="ok">Saved!</div>';setTimeout(()=>document.getElementById('medical-msg').innerHTML='',2000);
    } catch(e){
        document.getElementById('medical-msg').innerHTML=`<div class="err">${e.message}</div>`;
    }
}

function loadMedsList(meds){
    const el=document.getElementById('meds-list');
    if(!meds||!meds.length){el.innerHTML='<div style="font-size:12px;color:var(--muted);margin-bottom:12px">No medications added yet.</div>';return;}
    el.innerHTML=meds.map((m,i)=>`<div class="med-item"><div><div class="med-name">${m.name} ${m.dose}</div><div class="med-dose">${m.freq}${m.doctor?' · Dr. '+m.doctor:''}</div></div><div style="display:flex;gap:7px;align-items:center"><span class="badge ${m.status==='Active'?'g':m.status==='Paused'?'a':'b'}">${m.status}</span><button class="btn danger" style="padding:4px 9px;font-size:11px" onclick="removeMed(${m.id})">Remove</button></div></div>`).join('');
}
async function addMed(){
    const name=document.getElementById('med-name').value.trim(),dose=document.getElementById('med-dose').value.trim(),freq=document.getElementById('med-freq').value,status=document.getElementById('med-status').value,doctor=document.getElementById('med-doctor').value.trim(),msg=document.getElementById('med-msg');
    if(!name||!dose||!freq){msg.innerHTML='<div class="err">Fill in name, dosage, and frequency.</div>';return;}
    try{
        await callApi('/profile/medications', 'POST', {name,dose,freq,status,doctor});
        const data = await callApi('/profile'); loadMedsList(data.medications); refreshOverview(data);
        ['med-name','med-dose','med-doctor'].forEach(id=>document.getElementById(id).value='');document.getElementById('med-freq').value='';
        msg.innerHTML='<div class="ok">Added!</div>';setTimeout(()=>msg.innerHTML='',2000);
    }catch(e){
        msg.innerHTML=`<div class="err">${e.message}</div>`;
    }
}
async function removeMed(id){
    try{
        await callApi(`/profile/medications/${id}`, 'DELETE');
        const data = await callApi('/profile'); loadMedsList(data.medications); refreshOverview(data);
    }catch(e){console.error(e);}
}

function loadEmergencyForm(ec){
    document.getElementById('ec-name').value=ec.name||'';document.getElementById('ec-rel').value=ec.rel||'';
    document.getElementById('ec-phone').value=ec.phone||'';document.getElementById('ec-phone2').value=ec.phone_alt||'';
    document.getElementById('ec-address').value=ec.address||'';document.getElementById('ec-alert').value=ec.alert||'';
}
async function saveEmergency(){
    const ec = {
        name:document.getElementById('ec-name').value.trim(), rel:document.getElementById('ec-rel').value,
        phone:document.getElementById('ec-phone').value.trim(), phone_alt:document.getElementById('ec-phone2').value.trim(),
        address:document.getElementById('ec-address').value.trim(), alert:document.getElementById('ec-alert').value.trim()
    }
    try{
        await callApi('/profile/emergency', 'PUT', ec);
        document.getElementById('ec-msg').innerHTML='<div class="ok">Saved!</div>';setTimeout(()=>document.getElementById('ec-msg').innerHTML='',2000);
    }catch(e){
        document.getElementById('ec-msg').innerHTML=`<div class="err">${e.message}</div>`;
    }
}
function copySummary(){navigator.clipboard.writeText(document.getElementById('ai-summary').textContent).catch(()=>{});event.target.textContent='Copied!';setTimeout(()=>event.target.textContent='Copy summary',2000);}

// Pharmacist Connect Functionality Mock
function connectPharmacist(name) {
   go('chat',document.querySelector('.nav'));
   history = []; // Reset AI context
   document.getElementById('msgs').innerHTML = ''; // Clear chat
   addMsg('ai', `Hello! You are now connected to ${name}. How can I assist you today?`, [{t:'Live Chat',c:'b'}]);
}
function notifyPharmacist(name) {
   alert(`You will be notified when ${name} is available.`);
}

document.querySelectorAll('.pcard').forEach(c => {
    let btn = c.querySelector('.pmeta button');
    let name = c.querySelector('.pname').textContent;
    if(btn) {
        if(btn.textContent === 'Connect') btn.onclick = () => connectPharmacist(name);
        else btn.onclick = () => notifyPharmacist(name);
    }
});

function renderPrescriptionHistory(rxArray) {
   const container = document.querySelector('#panel-history .pbody');
   if(!rxArray || !rxArray.length) {
       container.innerHTML = '<div style="font-size:12px;color:var(--muted);margin-bottom:12px">No prescription history.</div>';
       return;
   }
   // Reverse sort to show newest first
   const sorted = [...rxArray].reverse();
   container.innerHTML = `
      <div class="slabel">All Prescriptions / AI Recommendations</div>
      <div class="rxlist">
        ${sorted.map(rx => `
           <div class="rxitem">
             <div class="rxdot" style="background:${rx.status==='Active'?'var(--accent)':'var(--blue)'}"></div>
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

document.getElementById('cond-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();addCondition();}});
document.getElementById('allergy-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();addAllergy();}});