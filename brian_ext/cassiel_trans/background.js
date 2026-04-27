// Cassiel Translate - Background Service Worker
// Handles context menu creation and Google Translate API calls

const GOOGLE_TRANSLATE_URL = 'https://translate.googleapis.com/translate_a/single';

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'translate-to-chinese',
    title: '翻译为中文',
    contexts: ['selection']
  });
});

// Handle context menu click
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'translate-to-chinese') return;
  if (!info.selectionText || !tab?.id) return;

  const text = info.selectionText.trim();
  if (!text) return;

  // Send loading state immediately
  chrome.tabs.sendMessage(tab.id, {
    type: 'cassiel-translate-loading',
    original: text
  }).catch(() => {});

  try {
    const translated = await translateToChinese(text);
    
    // Send result to content script
    chrome.tabs.sendMessage(tab.id, {
      type: 'cassiel-translate-result',
      original: text,
      translated: translated
    }).catch(() => {
      // Content script might not be ready - this is fine
    });
  } catch (err) {
    chrome.tabs.sendMessage(tab.id, {
      type: 'cassiel-translate-error',
      original: text,
      error: err.message
    }).catch(() => {});
  }
});

/**
 * Call Google Translate API (free endpoint)
 * @param {string} text - English text to translate
 * @returns {Promise<string>} - Chinese translation
 */
async function translateToChinese(text) {
  const url = `${GOOGLE_TRANSLATE_URL}?client=gtx&sl=en&tl=zh-CN&dt=t&q=${encodeURIComponent(text)}`;
  
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Translation failed: ${response.status}`);
  }
  
  const data = await response.json();
  
  // Google Translate returns: [[["translated text", "original", null, null, 1]], null, "en"]
  // Join all translation segments
  if (data && data[0]) {
    return data[0]
      .filter(segment => segment && segment[0])
      .map(segment => segment[0])
      .join('');
  }
  
  throw new Error('Empty translation result');
}
