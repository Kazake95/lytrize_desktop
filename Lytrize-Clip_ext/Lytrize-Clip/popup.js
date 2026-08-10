const btn = document.getElementById('captureBtn');
const statusEl = document.getElementById('status');

function showStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = 'status show ' + type;
}

btn.addEventListener('click', async () => {
  btn.disabled = true;
  btn.classList.add('loading');
  showStatus('Expanding viewport to capture full page...', 'info');

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const response = await chrome.runtime.sendMessage({ action: 'capture', tabId: tab.id });
    if (response.success) {
      showStatus('Saved: ' + response.filename, 'success');
    } else {
      showStatus(response.error || 'Unknown error', 'error');
    }
  } catch (err) {
    showStatus(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
});