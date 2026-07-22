(function initializeBisaRxCore(global) {
  'use strict';

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
  }

  function sanitizeHtml(html) {
    const template = document.createElement('template');
    template.innerHTML = String(html ?? '');
    const allowedTags = new Set(['A', 'BR', 'CODE', 'EM', 'LI', 'OL', 'P', 'PRE', 'STRONG', 'UL']);
    const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_ELEMENT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach(node => {
      if (!allowedTags.has(node.tagName)) {
        node.replaceWith(...node.childNodes);
        return;
      }
      const href = node.tagName === 'A' ? node.getAttribute('href') || '' : '';
      [...node.attributes].forEach(attribute => node.removeAttribute(attribute.name));
      if (node.tagName === 'A' && /^https?:\/\//i.test(href)) {
        node.setAttribute('href', href);
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
    });
    return template.innerHTML;
  }

  function renderMarkdown(text) {
    if (!text) return '';
    if (!global.marked) return escapeHtml(text).replace(/\n/g, '<br>');
    return sanitizeHtml(global.marked.parse(text, { async: false }));
  }

  global.BisaRxUI = Object.freeze({ escapeHtml, sanitizeHtml, renderMarkdown });
})(window);
