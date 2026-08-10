chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'capture') {
    captureFullPage(request.tabId)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

async function captureFullPage(tabId) {
  const tab = await chrome.tabs.get(tabId);
  if (!tab) throw new Error('Tab not found');

  const blocked = ['chrome://', 'devtools://', 'chrome-extension://', 'edge://', 'about:'];
  if (blocked.some(p => tab.url.startsWith(p))) {
    throw new Error('Cannot capture internal browser pages');
  }

  const target = { tabId: tab.id };
  let attached = false;
  let metricsOverridden = false;

  try {
    await chrome.debugger.attach(target, '1.3');
    attached = true;

    await chrome.debugger.sendCommand(target, 'Page.enable');
    await chrome.debugger.sendCommand(target, 'Runtime.enable');

    // 1. Read current page state (viewport, scroll position, pixel ratio)
    const pageInfo = await chrome.debugger.sendCommand(target, 'Runtime.evaluate', {
      expression: `({
        width: window.innerWidth,
        height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
        dpr: window.devicePixelRatio || 1,
        scrollX: window.scrollX || window.pageXOffset,
        scrollY: window.scrollY || window.pageYOffset
      })`,
      returnByValue: true
    });

    const { width, height, dpr, scrollX, scrollY } = pageInfo.result.value;

    // 2. CRITICAL: Expand viewport to full document height.
    // This forces the browser to layout and load lazy/off-screen content
    // WITHOUT scrolling the page — preserving dropdowns, modals, etc.
    await chrome.debugger.sendCommand(target, 'Emulation.setDeviceMetricsOverride', {
      width: Math.floor(width),
      height: Math.floor(height),
      deviceScaleFactor: dpr,
      mobile: false
    });
    metricsOverridden = true;

    // 3. Wait for lazy-loaded images and deferred content to render
    await new Promise(r => setTimeout(r, 2500));

    // 4. Capture the FULL rendered surface in ONE native shot
    const result = await chrome.debugger.sendCommand(target, 'Page.captureScreenshot', {
      format: 'png',
      fromSurface: true,
      captureBeyondViewport: true
    });

    // 5. Restore original viewport and scroll position
    await chrome.debugger.sendCommand(target, 'Emulation.clearDeviceMetricsOverride');
    metricsOverridden = false;

    await chrome.debugger.sendCommand(target, 'Runtime.evaluate', {
      expression: `window.scrollTo(${scrollX}, ${scrollY})`
    });

    await chrome.debugger.detach(target);
    attached = false;

    // 6. Download via browser's native download manager
    const dataUrl = 'data:image/png;base64,' + result.data;

    const now = new Date();
    const ts = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
      String(now.getHours()).padStart(2, '0'),
      String(now.getMinutes()).padStart(2, '0'),
      String(now.getSeconds()).padStart(2, '0')
    ].join('-');

    const safeTitle = tab.title
      .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_')
      .substring(0, 50) || 'page';

    const filename = 'Lytrize-Clip_' + safeTitle + '_' + ts + '.png';

    await chrome.downloads.download({
      url: dataUrl,
      filename: filename,
      saveAs: false
    });

    return { success: true, filename };

  } catch (err) {
    if (metricsOverridden) {
      try { await chrome.debugger.sendCommand(target, 'Emulation.clearDeviceMetricsOverride'); } catch (e) {}
    }
    if (attached) {
      try { await chrome.debugger.detach(target); } catch (e) {}
    }
    if (err.message.includes('Another debugger')) {
      throw new Error('Debugger already in use. Close DevTools/other extensions and retry.');
    }
    throw err;
  }
}