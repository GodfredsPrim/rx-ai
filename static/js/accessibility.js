/* Shared keyboard and dialog behavior; existing click and close handlers remain authoritative. */
(() => {
  'use strict';
  const focusable = 'button, a[href], input:not([type="hidden"]), select, textarea, [tabindex="0"]';
  let activeDialog = null;
  let returnFocus = null;

  function visible(node) {
    return !node.disabled && node.getClientRects().length > 0 &&
      getComputedStyle(node).visibility !== 'hidden';
  }

  function enhance(root) {
    root.querySelectorAll('div[onclick]:not(.sidebar-overlay)').forEach(node => {
      if (!node.hasAttribute('role')) node.setAttribute('role', 'button');
      if (!node.hasAttribute('tabindex')) node.tabIndex = 0;
    });
  }

  function syncDialog() {
    const dialogs = [...document.querySelectorAll('.modal-overlay')];
    const next = dialogs.filter(visible).at(-1) || null;
    if (next === activeDialog) return;
    if (next) {
      if (!activeDialog && !next.contains(document.activeElement)) returnFocus = document.activeElement;
      activeDialog = next;
      document.getElementById('main-app')?.toggleAttribute('inert',true);
      if (!next.contains(document.activeElement)) {
        (Array.from(next.querySelectorAll(focusable)).find(visible) || next).focus();
      }
    } else {
      activeDialog = null;
      document.getElementById('main-app')?.toggleAttribute('inert',false);
      if (returnFocus?.isConnected && visible(returnFocus)) returnFocus.focus();
      returnFocus = null;
    }
  }

  // Capture the opener before an existing inline handler moves focus into a dialog.
  document.addEventListener('click', event => {
    if (!activeDialog) returnFocus = event.target.closest('button, a[href], [role="button"]') || document.activeElement;
  }, true);

  function init() {
    enhance(document);
    document.querySelectorAll('.modal-overlay').forEach(dialog => {
      dialog.setAttribute('role', 'dialog');
      dialog.setAttribute('aria-modal', 'true');
      dialog.tabIndex = -1;
      if (!dialog.hasAttribute('aria-label') && !dialog.hasAttribute('aria-labelledby')) {
        dialog.setAttribute('aria-label', dialog.querySelector('h2, h3')?.textContent.trim() || 'BisaRx dialog');
      }
    });
    new MutationObserver(records => {
      records.forEach(record => record.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) enhance(node.parentElement || node);
      }));
      if (records.some(record => record.type === 'childList' || record.target.matches('.modal-overlay'))) syncDialog();
    }).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class'] });
    syncDialog();
  }

  document.addEventListener('keydown', event => {
    const custom = event.target.closest('div[role="button"][onclick]');
    if (custom && event.target === custom && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      custom.click();
    }
    if (!activeDialog) return;
    if (event.key === 'Escape') {
      const close = activeDialog.querySelector('.modal-close');
      if (close) { event.preventDefault(); close.click(); }
    }
    if (event.key === 'Tab') {
      const items = [...activeDialog.querySelectorAll(focusable)].filter(visible);
      const first = items[0] || activeDialog;
      const last = items.at(-1) || activeDialog;
      if (!activeDialog.contains(document.activeElement) ||
          (event.shiftKey && document.activeElement === first) ||
          (!event.shiftKey && document.activeElement === last) || items.length === 0) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
    }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
