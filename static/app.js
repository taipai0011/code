(function () {
  const form = document.getElementById('download-form');
  const urlInput = document.getElementById('url');
  const submitBtn = document.getElementById('submit-btn');
  const platformPreview = document.getElementById('platform-preview');

  if (!form || !urlInput || !submitBtn || !platformPreview) {
    return;
  }

  function detectPlatform(url) {
    const lower = String(url || '').toLowerCase();
    if (lower.includes('youtube.com') || lower.includes('youtu.be')) {
      return 'YouTube';
    }
    if (lower.includes('kling.ai') || lower.includes('klingai')) {
      return 'Kling AI';
    }
    return 'Unknown';
  }

  function updatePlatformHint() {
    const value = urlInput.value.trim();
    if (!value) {
      platformPreview.textContent = 'Detected platform: waiting for URL…';
      platformPreview.className = 'hint';
      return;
    }

    const platform = detectPlatform(value);
    platformPreview.textContent = `Detected platform: ${platform}`;
    platformPreview.className = platform === 'Unknown' ? 'hint error-text' : 'hint success-text';
  }

  urlInput.addEventListener('input', updatePlatformHint);
  updatePlatformHint();

  form.addEventListener('submit', function () {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Preparing download...';
  });
})();
