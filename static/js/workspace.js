/* Theme, workspace navigation, keyboard affordances and shared icon vocabulary. */
(() => {
  'use strict';
  const paths = {
    brand:'<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    moon:'<path d="M20.8 13.2A9 9 0 0 1 10.8 3a9 9 0 1 0 10 10.2z"/>',
    panel:'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
    edit:'<path d="M12 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-7M16 3l5 5M9 15l1-5L18 2l4 4-8 8z"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    arrow:'<path d="M12 19V5m-6 6 6-6 6 6"/>',
    plus:'<path d="M12 5v14M5 12h14"/>',
    shield:'<path d="m12 3 8 4v5c0 5-8 9-8 9s-8-4-8-9V7z"/><path d="m8 12 3 3 5-6"/>',
    heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
    pill:'<path d="m10 4-6 6a6 6 0 0 0 8 8l6-6a6 6 0 0 0-8-8zM7 7l10 10"/>',
    person:'<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    close:'<path d="m6 6 12 12M6 18 18 6"/>',
    file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h6"/>',
    refresh:'<path d="M20 7a8 8 0 1 0 1 7M20 3v5h-5"/>',
    globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a17 17 0 0 1 0 18 17 17 0 0 1 0-18"/>',
  };
  const icon = name => `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.file}</svg>`;
  window.BisaRxIcons = { icon };
  const getTheme = () => { try { return localStorage.getItem('bisarx-theme') === 'dark' ? 'dark' : 'light'; } catch { return 'light'; } };
  document.documentElement.dataset.theme = getTheme();
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#202123':'#ffffff');
    try { localStorage.setItem('bisarx-theme',theme); } catch { /* available for this visit */ }
    document.querySelectorAll('.theme-toggle').forEach(button => {
      button.innerHTML = icon(theme === 'dark' ? 'sun' : 'moon') + `<span>${theme === 'dark' ? 'Light' : 'Dark'} appearance</span>`;
      button.setAttribute('aria-label',`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    });
  }
  window.toggleAppearance = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  window.toggleWorkspaceSidebar = () => {
    if (innerWidth <= 900 && typeof toggleSidebar === 'function') toggleSidebar();
    else document.querySelector('.sidebar')?.classList.toggle('collapsed');
  };
  function initialize() {
    document.querySelectorAll('.sidebar-logo,.mobile-brand-lockup,.login-header,.portal-gate-card').forEach(node => {
      node.insertAdjacentHTML('afterbegin','<span class="brand-symbol" aria-hidden="true"><img src="/logo.png" alt="" width="40" height="40"></span>');
    });
    const footer = document.querySelector('.sidebar-footer');
    const theme = document.createElement('button');
    theme.type='button'; theme.className = `theme-toggle${footer ? '' : ' public-theme'}`;
    theme.addEventListener('click',window.toggleAppearance);
    (footer || document.body).appendChild(theme);
    if(footer && document.body.dataset.portal !== 'patient')footer.insertAdjacentHTML('beforeend','<div class="sidebar-links"><a href="/">Patient</a><a href="/pharmacist">Pharmacist</a><a href="/admin">Admin</a></div>');
    if(document.body.dataset.portal === 'patient') {
      const nav=document.querySelector('.sidebar-nav');
      const primary=document.createElement('div'); primary.className='nav-section';
      ['nav-chat','nav-history','nav-connect','nav-profile'].forEach(id=>{
        const item=document.getElementById(id); if(item)primary.appendChild(item);
      });
      const tools=document.createElement('details'); tools.className='nav-tools';
      tools.innerHTML='<summary>Health tools & resources</summary><div class="nav-section"></div>';
      ['nav-bodymap','nav-conditions','nav-redflag'].forEach(id=>{
        const item=document.getElementById(id); if(item)tools.lastElementChild.appendChild(item);
      });
      nav?.querySelectorAll('.nav-section').forEach(section=>section.remove());
      nav?.append(primary,tools);
      tools.addEventListener('toggle',()=>tools.setAttribute('aria-label',tools.open?'Health tools expanded':'Health tools collapsed'));
      tools.querySelectorAll('a').forEach(item=>item.addEventListener('click',()=>{ tools.open=true; }));
    }
    applyTheme(getTheme());
    document.querySelectorAll('.panel-header').forEach(header => {
      if(document.body.dataset.portal==='patient' && !header.closest('#panel-chat'))return;
      const toolbar = document.createElement('div'); toolbar.className='workspace-toolbar';
      if (header.closest('#panel-chat')) {
        toolbar.innerHTML=`<button type="button" class="desktop-only" aria-label="Collapse sidebar" title="Collapse sidebar">${icon('panel')}</button><button type="button" aria-label="New conversation" title="New conversation">${icon('edit')}</button>`;
        toolbar.children[0].onclick=window.toggleWorkspaceSidebar;
        toolbar.children[1].onclick=() => newChat();
      } else {
        toolbar.innerHTML=`<button type="button" aria-label="Refresh this view" title="Refresh this view">${icon('refresh')}</button>`;
        toolbar.children[0].onclick=() => {
          const role=document.body.dataset.portal;
          if(role==='admin') refreshAdminDashboard();
          else if(role==='pharmacist') refreshPharmacistDashboard();
        };
      }
      (header.querySelector('.panel-badges') || header).appendChild(toolbar);
    });
    const hero=document.querySelector('.hero-header');
    if(hero) hero.insertAdjacentHTML('afterbegin','<div class="welcome-mark" aria-hidden="true"><img src="/logo.png" alt="" width="48" height="48"></div>');
    const composer=document.querySelector('.chat-pill');
    if(composer) composer.insertAdjacentHTML('beforeend','<span class="composer-hint">Photo, voice, or a few words.</span>');
    const sendButton=document.getElementById('send-btn'); if(sendButton) sendButton.innerHTML=icon('arrow');
    document.querySelectorAll('.modal-close,.clear-preview-btn').forEach(button=>button.innerHTML=icon('close'));
    const chat=document.getElementById('panel-chat');
    if(chat && document.body.dataset.portal==='patient') {
      const suggestions=document.createElement('div');suggestions.className='suggestion-row';
      const actions=[['heart','Describe symptoms',"I would like help understanding my symptoms."],['pill','Ask about a medication',"I have a question about a medication."],['person','Find the area that hurts',null]];
      actions.forEach(([symbol,label,prompt])=>{const button=document.createElement('button');button.type='button';button.innerHTML=icon(symbol)+label;button.onclick=()=>{if(prompt){document.getElementById('tinput').value=prompt;document.getElementById('tinput').focus();}else go('bodymap',document.getElementById('nav-bodymap'));};suggestions.appendChild(button);});
      chat.appendChild(suggestions);
    }
    document.querySelectorAll('[data-icon]').forEach(node=>node.innerHTML=icon(node.dataset.icon));
    document.querySelectorAll('.nav-item').forEach(node=>{if(!node.title)node.title=node.textContent.trim();});
    const focusInput=document.getElementById('tinput');
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape' && ![...document.querySelectorAll('.modal-overlay')].some(item=>item.style.display!=='none')) {if(typeof closeSidebar==='function')closeSidebar();}
      if((event.ctrlKey||event.metaKey)&&event.key==='k'&&focusInput){event.preventDefault();go('chat',document.getElementById('nav-chat'));focusInput.focus();}
    });
    document.querySelectorAll('[data-directory-search]').forEach(input=>input.addEventListener('input',()=>{
      document.querySelectorAll(`#${input.dataset.directorySearch} .directory-row`).forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(input.value.toLowerCase()));
    }));
    const sidebar=document.querySelector('.sidebar');
    if(sidebar){const syncSidebar=()=>{sidebar.inert=innerWidth<=900&&!sidebar.classList.contains('open');};new MutationObserver(syncSidebar).observe(sidebar,{attributes:true,attributeFilter:['class']});addEventListener('resize',syncSidebar);syncSidebar();}
    const syncViewport=()=>document.documentElement.style.setProperty('--workspace-height',`${window.visualViewport?.height || innerHeight}px`);
    window.visualViewport?.addEventListener('resize',syncViewport);addEventListener('resize',syncViewport);syncViewport();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize);else initialize();
})();
