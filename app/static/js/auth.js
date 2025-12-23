// auth.js - manejador del formulario de login (vanilla JS)
// - Envía JSON por fetch a /api/auth/login
// - Maneja estados loading, errores y accesibilidad

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('auth-form');
  const msg = document.getElementById('auth-message');
  const submitBtn = document.getElementById('auth-submit');

  if (!form) return;

  const setMessage = (text, isError=true) => {
    if (!msg) return;
    msg.textContent = text || '';
    msg.style.color = isError ? 'var(--error)' : 'var(--brand-blue)';
  };

  const setInvalid = (el, invalid=true) => {
    if (!el) return;
    // marcar tanto el input como su contenedor .input-group
    try {
      const group = el.closest('.input-group');
      if (group) {
        if (invalid) group.classList.add('is-invalid'); else group.classList.remove('is-invalid');
      }
    } catch (e) {}
    if (invalid) el.classList.add('is-invalid'); else el.classList.remove('is-invalid');
  };

  const setFieldError = (fieldId, text) => {
    const errEl = document.getElementById(fieldId + '-error');
    const input = document.getElementById(fieldId);
    if (errEl) errEl.textContent = text || '';
    setInvalid(input, !!text);
    if (input && text) input.setAttribute('aria-invalid', 'true');
    if (input && !text) input.removeAttribute('aria-invalid');
  };

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    setMessage('');
    // obtener valores
    const username = form.querySelector('#username').value.trim();
    const password = form.querySelector('#password').value;
    const remember = !!form.querySelector('#remember_me')?.checked;

    // validación básica
    let ok = true;
    setFieldError('username', '');
    setFieldError('password', '');
    if (!username) { setFieldError('username', 'El usuario es obligatorio.'); ok = false; }
    if (!password) { setFieldError('password', 'La contraseña es obligatoria.'); ok = false; }
    if (!ok) { setMessage('Complete los campos obligatorios.', true); return; }

    // estado loading
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;

    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, remember_me: remember }),
      });

      if (resp.ok) {
        setMessage('Ingresando...', false);
        // redirigir al root
        window.location.href = '/';
        return;
      }

      // manejar errores
      if (resp.status === 401) {
        setMessage('Usuario o contraseña incorrectos.', true);
        setFieldError('password', 'Credenciales inválidas.');
      } else if (resp.status === 422) {
        const body = await resp.json().catch(() => ({}));
        const detail = body?.detail;
        // intentar mapear errores de validación de FastAPI
        if (Array.isArray(detail)) {
          detail.forEach(d => {
            try {
              const loc = d.loc || [];
              const field = loc[loc.length-1];
              if (field && (field === 'username' || field === 'password')) {
                setFieldError(field, d.msg || 'Valor inválido');
              }
            } catch(e){}
          });
          setMessage('Corrija los campos marcados.', true);
        } else {
          setMessage(detail || 'Datos inválidos.', true);
        }
      } else {
        setMessage('Error en el servidor. Intente más tarde.', true);
      }
    } catch (err) {
      setMessage('No se pudo conectar al servidor.', true);
    } finally {
      submitBtn.classList.remove('loading');
      submitBtn.disabled = false;
    }
  });

  // accesibilidad: focus inicial
  const firstInput = form.querySelector('input');
  if (firstInput) firstInput.focus();
});
