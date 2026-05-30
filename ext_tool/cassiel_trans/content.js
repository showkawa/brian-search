// Cassiel Translate - Content Script
// Tracks mouse position and renders floating translation popup

(function() {
  'use strict';

  // ── State ──────────────────────────────────────────────
  let mouseX = 0;
  let mouseY = 0;
  let currentPopup = null;

  // ── Mouse tracking ─────────────────────────────────────
  document.addEventListener('contextmenu', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
  }, true);

  // ── Message listener ───────────────────────────────────
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'cassiel-translate-loading') {
      // Show loading spinner
      showPopup('loading', msg.original, '正在翻译...');
    } else if (msg.type === 'cassiel-translate-result') {
      dismissPopup();
      showPopup('result', msg.original, msg.translated);
    } else if (msg.type === 'cassiel-translate-error') {
      dismissPopup();
      showPopup('error', msg.original, msg.error || '翻译失败');
    }
  });

  // ── Popup management ───────────────────────────────────
  function showPopup(mode, original, content) {
    const popup = createPopupElement(mode, original, content);
    document.body.appendChild(popup);
    currentPopup = popup;

    // Position near mouse click
    requestAnimationFrame(() => {
      positionPopup(popup);
      popup.classList.add('cassiel-visible');
    });

    // Auto-dismiss handlers
    setTimeout(() => bindDismissal(popup), 0);
  }

  function dismissPopup() {
    if (currentPopup) {
      const popup = currentPopup;
      popup.classList.remove('cassiel-visible');
      setTimeout(() => {
        if (popup.parentNode) {
          popup.parentNode.removeChild(popup);
        }
        if (currentPopup === popup) {
          currentPopup = null;
        }
      }, 150);
    }
  }

  /**
   * Position popup near mouse coordinates, keeping it within viewport
   */
  function positionPopup(popup) {
    const rect = popup.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const gap = 12;

    let left = mouseX;
    let top = mouseY + gap;

    // Keep within right edge
    if (left + rect.width > vw - gap) {
      left = vw - rect.width - gap;
    }
    // Keep within left edge
    if (left < gap) {
      left = gap;
    }
    // Flip above if not enough space below
    if (top + rect.height > vh - gap) {
      top = mouseY - rect.height - gap;
    }
    // Keep within top edge
    if (top < gap) {
      top = gap;
    }

    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
  }

  /**
   * Bind dismissal events
   */
  function bindDismissal(popup) {
    const dismiss = () => {
      dismissPopup();
      cleanup();
    };

    const onScroll = () => dismiss();
    const onKey = (e) => { if (e.key === 'Escape') dismiss(); };
    const onClick = (e) => {
      if (!popup.contains(e.target)) {
        dismiss();
      }
    };

    // Delay click listener so the right-click that triggered
    // the context menu doesn't immediately close the popup
    setTimeout(() => {
      document.addEventListener('click', onClick, true);
    }, 100);

    document.addEventListener('scroll', onScroll, true);
    document.addEventListener('keydown', onKey, true);

    function cleanup() {
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('scroll', onScroll, true);
      document.removeEventListener('keydown', onKey, true);
    }
  }

  // ── DOM creation ───────────────────────────────────────
  function createPopupElement(mode, original, content) {
    const wrapper = document.createElement('div');
    wrapper.className = 'cassiel-popup-wrapper';
    wrapper.setAttribute('data-cassiel', 'true');

    const header = document.createElement('div');
    header.className = 'cassiel-header';

    const label = document.createElement('span');
    label.className = 'cassiel-header-label';
    label.textContent = mode === 'loading' ? '翻译中' : mode === 'error' ? '翻译失败' : '翻译结果';

    const closeBtn = document.createElement('button');
    closeBtn.className = 'cassiel-close-btn';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      dismissPopup();
    });

    header.appendChild(label);
    header.appendChild(closeBtn);

    const originalEl = document.createElement('div');
    originalEl.className = 'cassiel-original';
    originalEl.textContent = truncate(original, 100);

    const body = document.createElement('div');
    body.className = mode === 'error' ? 'cassiel-body cassiel-error' : mode === 'loading' ? 'cassiel-body cassiel-loading' : 'cassiel-body';
    
    // Loading mode: show spinner
    if (mode === 'loading') {
      const spinner = document.createElement('div');
      spinner.className = 'cassiel-spinner';
      body.appendChild(spinner);
      const loadingText = document.createElement('span');
      loadingText.className = 'cassiel-loading-text';
      loadingText.textContent = content;
      body.appendChild(loadingText);
    } else {
      body.textContent = content;
    }

    // Copy button (hidden in loading mode)
    const footer = document.createElement('div');
    footer.className = 'cassiel-footer';
    footer.style.display = mode === 'loading' ? 'none' : 'flex';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'cassiel-copy-btn';
    copyBtn.textContent = '复制';
    copyBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      copyToClipboard(content);
      copyBtn.textContent = '已复制';
      setTimeout(() => { copyBtn.textContent = '复制'; }, 1500);
    });

    footer.appendChild(copyBtn);

    wrapper.appendChild(header);
    wrapper.appendChild(originalEl);
    wrapper.appendChild(body);
    wrapper.appendChild(footer);

    return wrapper;
  }

  // ── Utilities ──────────────────────────────────────────
  function truncate(text, maxLen) {
    if (!text) return '';
    return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    });
  }

})();
