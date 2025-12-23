// utilidades simples
function toast(msg){ alert(msg); }

// Login modal: cargar /ui/login_fragment y mostrarlo en un modal
async function openLoginModal(next) {
	const modal = document.getElementById('login-modal');
	const body = document.getElementById('login-modal-body');
	const closeBtn = document.getElementById('login-modal-close');
	const backdrop = document.getElementById('login-modal-backdrop');

	try {
		const url = '/ui/login_fragment' + (next ? `?next=${encodeURIComponent(next)}` : '');
		const resp = await fetch(url, { credentials: 'same-origin' });
		if (!resp.ok) throw new Error('no fragment');
		const html = await resp.text();
		body.innerHTML = html;

		// mostrar modal
		modal.classList.remove('hidden');
		modal.setAttribute('aria-hidden', 'false');

		// bind close
		closeBtn.onclick = closeLoginModal;
		backdrop.onclick = closeLoginModal;

		// inicializar submit del formulario dentro del modal
		const form = body.querySelector('#login-form');
		const statusEl = body.querySelector('#login-status');
		const nextUrl = new URLSearchParams(window.location.search).get('next') || next || '/ui';
		if (form) {
			form.addEventListener('submit', async (ev) => {
				ev.preventDefault();
				if (statusEl) { statusEl.textContent = 'Ingresando...'; statusEl.className = 'login-status'; }
				const data = Object.fromEntries(new FormData(form).entries());
				try {
					const r = await fetch('/api/auth/login', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify(data),
						credentials: 'same-origin',
					});
					if (!r.ok) {
						let msg = 'Error de login';
						try { const b = await r.json(); msg = b?.detail || msg; } catch(_){}
						if (statusEl) { statusEl.textContent = msg; statusEl.className = 'err'; }
						return;
					}
					if (statusEl) { statusEl.textContent = 'OK'; statusEl.className = 'ok'; }
					// recargar a la URL destino
					window.location.href = nextUrl;
				} catch (err) {
					if (statusEl) { statusEl.textContent = 'No se pudo conectar'; statusEl.className = 'err'; }
				}
			});
		}

		// focus en primer input
		const firstInput = body.querySelector('input');
		if (firstInput) firstInput.focus();
	} catch (err) {
		toast('No se pudo abrir el formulario de login');
	}
}

function closeLoginModal() {
	const modal = document.getElementById('login-modal');
	const body = document.getElementById('login-modal-body');
	if (!modal) return;
	modal.classList.add('hidden');
	modal.setAttribute('aria-hidden', 'true');
	if (body) body.innerHTML = '';
}

document.addEventListener('DOMContentLoaded', () => {
	console.debug('main.js: DOMContentLoaded');
	// interceptor del link de login para abrir modal
	document.querySelectorAll('a[href="/ui/login"]').forEach(a => {
		a.addEventListener('click', (ev) => {
			ev.preventDefault();
			const next = new URLSearchParams(window.location.search).get('next') || window.location.pathname;
			openLoginModal(next);
		});
	});
	// cerrar con Esc
	document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeLoginModal(); });

	// Dropdown de configuración: toggle y cierre al hacer click fuera o Esc
	document.querySelectorAll('.dropdown-toggle').forEach(btn => {
		console.debug('main.js: found dropdown-toggle', btn);
		const wrapper = btn.closest('.import-dropdown');
		if (!wrapper) return;
		const menu = wrapper.querySelector('.dropdown-menu');
		btn.addEventListener('click', (ev) => {
			ev.stopPropagation();
			const opened = !menu.classList.contains('hidden');
			console.debug('main.js: dropdown click, opened=', opened);
			// cerrar todos los dropdowns primero
			document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
			if (!opened) {
				menu.classList.remove('hidden');
				console.debug('main.js: menu opened');
			} else {
				console.debug('main.js: menu closed');
			}
		});
	});

	// Delegated handler: asegura que clicks sobre elementos dinámicos también funcionen
	document.addEventListener('click', (ev) => {
		const btn = ev.target.closest && ev.target.closest('.dropdown-toggle');
		if (!btn) return;
		ev.stopPropagation();
		console.debug('main.js: delegated dropdown click', btn);
		const wrapper = btn.closest('.import-dropdown');
		if (!wrapper) return;
		const menu = wrapper.querySelector('.dropdown-menu');
		const opened = !menu.classList.contains('hidden');
		document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
		if (!opened) {
			menu.classList.remove('hidden');
			console.debug('main.js: menu opened (delegated)');
		}
	});

	// Cerrar dropdowns al click fuera
	document.addEventListener('click', (ev) => {
		if (ev.target.closest && ev.target.closest('.import-dropdown')) return;
		document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
	});

	// also close on Esc (in addition to modal handling)
	document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') {
		document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
	}});
});
