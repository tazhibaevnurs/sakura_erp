/**
 * Общие UI-хелперы: toast, fetch с CSRF.
 */
(function (global) {
  function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function ensureToastHost() {
    let host = document.getElementById('sakura-toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'sakura-toast-host';
      host.className = 'sakura-toast-host';
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    return host;
  }

  function toast(message, level = 'success', duration = 3200) {
    const host = ensureToastHost();
    const el = document.createElement('div');
    el.className = `sakura-toast sakura-toast--${level}`;
    el.innerHTML = `
      <span class="sakura-toast__icon">${level === 'danger' ? '!' : '✓'}</span>
      <span class="sakura-toast__text">${message}</span>
    `;
    host.appendChild(el);
    requestAnimationFrame(() => el.classList.add('sakura-toast--visible'));
    setTimeout(() => {
      el.classList.remove('sakura-toast--visible');
      setTimeout(() => el.remove(), 280);
    }, duration);
  }

  async function postForm(url, data = {}) {
    const body = new FormData();
    Object.entries(data).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => body.append(key, item ?? ''));
      } else {
        body.append(key, value ?? '');
      }
    });
    const csrf = getCsrfToken();
    if (csrf) body.append('csrfmiddlewaretoken', csrf);

    const resp = await fetch(url, {
      method: 'POST',
      body,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      },
    });
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok || json.ok === false) {
      throw new Error(json.error || json.message || 'Не удалось выполнить запрос');
    }
    return json;
  }

  global.SakuraUI = { getCsrfToken, toast, postForm };
})(window);
