(function () {
  'use strict';

  // 1. Identify script tag and extract parameters
  const scriptTag = document.currentScript || (function () {
    const scripts = document.getElementsByTagName('script');
    for (let i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i].src && scripts[i].src.indexOf('widget.v1.js') !== -1) {
        return scripts[i];
      }
    }
    return null;
  })();

  if (!scriptTag) {
    console.error('[WidgetPlatform] Could not find script tag.');
    return;
  }

  const scriptUrl = new URL(scriptTag.src, window.location.href);
  const widgetId = scriptUrl.searchParams.get('id') || scriptTag.getAttribute('data-widget-id');
  const apiBase = scriptUrl.origin;

  if (!widgetId) {
    console.error('[WidgetPlatform] Missing required widget "id" in script src or data-widget-id attribute.');
    return;
  }

  // 2. Fetch public configuration
  const configUrl = `${apiBase}/api/v1/public/widgets/${encodeURIComponent(widgetId)}/config`;

  fetch(configUrl, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
    cache: 'default'
  })
    .then(function (res) {
      if (!res.ok) {
        throw new Error('Failed to load widget configuration (Status: ' + res.status + ')');
      }
      return res.json();
    })
    .then(function (config) {
      initWidget(config, apiBase);
    })
    .catch(function (err) {
      console.warn('[WidgetPlatform] Initialization error:', err.message);
    });

  // 3. Render widget into host page
  function initWidget(config, baseUrl) {
    const display = config.display_options || {};
    const themeColor = display.theme_color || '#2563eb';
    const position = display.position || 'bottom-right';
    const delay = (display.delay_seconds || 0) * 1000;

    const container = document.createElement('div');
    container.id = 'wp-embed-' + config.id;
    
    // Position styling
    let posStyles = 'position: fixed; z-index: 999999; max-width: 380px; width: calc(100% - 32px);';
    if (position === 'bottom-right') {
      posStyles += ' bottom: 20px; right: 20px;';
    } else if (position === 'bottom-left') {
      posStyles += ' bottom: 20px; left: 20px;';
    } else if (position === 'top-right') {
      posStyles += ' top: 20px; right: 20px;';
    } else {
      posStyles += ' bottom: 20px; right: 20px;';
    }

    container.style.cssText = posStyles;

    // Build form fields HTML
    let fieldsHtml = '';
    (config.fields || []).forEach(function (field) {
      const requiredAttr = field.required ? 'required' : '';
      const reqStar = field.required ? '<span style="color:#ef4444;">*</span>' : '';

      fieldsHtml += `
        <div style="margin-bottom: 12px; text-align: left;">
          <label style="display:block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;">
            ${escapeHtml(field.label)} ${reqStar}
          </label>
          <input type="${escapeHtml(field.type || 'text')}" 
                 name="${escapeHtml(field.name)}" 
                 ${requiredAttr} 
                 style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; border: 1px solid #d1d5db; border-radius: 6px; outline: none; transition: border-color 0.2s;" />
        </div>
      `;
    });

    // Honeypot field (invisible to users, catches bots)
    const honeypotHtml = `
      <div style="display:none !important; position:absolute !important; left:-9999px !important;">
        <label>Website</label>
        <input type="text" name="_hp_trap" tabindex="-1" autocomplete="off" />
      </div>
    `;

    container.innerHTML = `
      <div style="background: #ffffff; border-radius: 12px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1); border: 1px solid #e5e7eb; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <div style="background: ${themeColor}; padding: 14px 18px; color: #ffffff; display: flex; justify-content: space-between; align-items: center;">
          <h3 style="margin: 0; font-size: 16px; font-weight: 600;">${escapeHtml(config.title)}</h3>
          <button type="button" id="wp-close-${config.id}" style="background:none; border:none; color:#ffffff; font-size: 18px; cursor: pointer; opacity: 0.8; line-height: 1;">&times;</button>
        </div>
        <div style="padding: 16px 18px;">
          ${config.description ? `<p style="margin: 0 0 14px 0; font-size: 13px; color: #4b5563; line-height: 1.4;">${escapeHtml(config.description)}</p>` : ''}
          <div id="wp-status-${config.id}" style="display:none; padding: 10px; border-radius: 6px; margin-bottom: 12px; font-size: 13px;"></div>
          <form id="wp-form-${config.id}" novalidate>
            ${fieldsHtml}
            ${honeypotHtml}
            <button type="submit" id="wp-btn-${config.id}" style="width: 100%; padding: 10px 14px; background: ${themeColor}; color: #ffffff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; transition: opacity 0.2s;">
              ${escapeHtml(config.button_text || 'Submit')}
            </button>
          </form>
        </div>
      </div>
    `;

    setTimeout(function () {
      document.body.appendChild(container);
      setupEvents(config, container, baseUrl);
    }, delay);
  }

  function setupEvents(config, container, baseUrl) {
    const form = container.querySelector('#wp-form-' + config.id);
    const closeBtn = container.querySelector('#wp-close-' + config.id);
    const submitBtn = container.querySelector('#wp-btn-' + config.id);
    const statusBox = container.querySelector('#wp-status-' + config.id);

    closeBtn.addEventListener('click', function () {
      container.style.display = 'none';
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      const formData = new FormData(form);
      const dataObj = {};
      let honeypotValue = '';

      for (let [key, val] of formData.entries()) {
        if (key === '_hp_trap') {
          honeypotValue = val;
        } else {
          dataObj[key] = val;
        }
      }

      // Basic client-side check
      for (let i = 0; i < (config.fields || []).length; i++) {
        const field = config.fields[i];
        if (field.required && (!dataObj[field.name] || !dataObj[field.name].trim())) {
          showStatus(statusBox, 'Please fill in ' + field.label, 'error');
          return;
        }
      }

      submitBtn.disabled = true;
      submitBtn.innerText = 'Submitting...';
      statusBox.style.display = 'none';

      const payload = {
        widget_id: config.id,
        data: dataObj,
        _hp_trap: honeypotValue
      };

      fetch(`${baseUrl}/api/v1/public/submissions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
      })
        .then(function (res) {
          return res.json().then(function (body) {
            return { ok: res.ok, status: res.status, body: body };
          });
        })
        .then(function (result) {
          submitBtn.disabled = false;
          submitBtn.innerText = config.button_text || 'Submit';

          if (result.ok) {
            form.reset();
            form.style.display = 'none';
            showStatus(statusBox, 'Thank you! Your submission has been received.', 'success');
          } else {
            const errMsg = (result.body && result.body.detail && (result.body.detail.error || result.body.detail)) || 'Submission failed.';
            showStatus(statusBox, errMsg, 'error');
          }
        })
        .catch(function (err) {
          submitBtn.disabled = false;
          submitBtn.innerText = config.button_text || 'Submit';
          showStatus(statusBox, 'Network error. Please try again.', 'error');
        });
    });
  }

  function showStatus(el, msg, type) {
    el.style.display = 'block';
    el.innerText = msg;
    if (type === 'success') {
      el.style.background = '#dcfce7';
      el.style.color = '#15803d';
      el.style.border = '1px solid #bbf7d0';
    } else {
      el.style.background = '#fee2e2';
      el.style.color = '#b91c1c';
      el.style.border = '1px solid #fecaca';
    }
  }

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
})();
