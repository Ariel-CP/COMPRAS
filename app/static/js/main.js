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

	// Toggle del menú lateral
	const sidebarToggle = document.getElementById('sidebar-toggle');
	const sidebarBackdrop = document.getElementById('sidebar-backdrop');
	const isMobile = () => window.matchMedia('(max-width: 880px)').matches;
	const closeMobileSidebar = () => {
		document.body.classList.remove('sidebar-open');
		if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
	};
	if (sidebarToggle) {
		sidebarToggle.addEventListener('click', () => {
			if (isMobile()) {
				const opening = !document.body.classList.contains('sidebar-open');
				document.body.classList.toggle('sidebar-open', opening);
				if (sidebarBackdrop) sidebarBackdrop.classList.toggle('hidden', !opening);
				sidebarToggle.setAttribute('aria-expanded', String(opening));
			} else {
				const collapsed = document.body.classList.toggle('sidebar-collapsed');
				sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
			}
		});
	}
	if (sidebarBackdrop) {
		sidebarBackdrop.addEventListener('click', closeMobileSidebar);
	}
	document.addEventListener('keydown', (ev) => {
		if (ev.key === 'Escape') closeMobileSidebar();
	});
	// Al navegar desde el sidebar en móvil, cerrarlo
	document.querySelectorAll('.sidebar a').forEach(a => {
		a.addEventListener('click', () => { if (isMobile()) closeMobileSidebar(); });
	});

	// Grupos del menú lateral: se abren/cierran solo de forma manual y quedan fijos.
	const navGroups = document.querySelectorAll('.sidebar-nav .nav-group');

	navGroups.forEach(group => {
		const button = group.querySelector('.nav-group-toggle');
		const menu = group.querySelector('.dropdown-menu');
		const menuItems = () => Array.from(menu.querySelectorAll('[role="menuitem"]'));

		button.addEventListener('click', () => {
			const opening = menu.classList.contains('hidden');
			menu.classList.toggle('hidden', !opening);
			button.setAttribute('aria-expanded', String(opening));
		});

		button.addEventListener('keydown', event => {
			if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
			event.preventDefault();
			if (menu.classList.contains('hidden')) button.click();
			const items = menuItems();
			items[event.key === 'ArrowDown' ? 0 : items.length - 1]?.focus();
		});

		menu.addEventListener('keydown', event => {
			const items = menuItems();
			const currentIndex = items.indexOf(document.activeElement);
			let nextIndex;
			if (event.key === 'Escape') {
				event.preventDefault();
				menu.classList.add('hidden');
				button.setAttribute('aria-expanded', 'false');
				button.focus();
				return;
			}
			if (event.key === 'Home') nextIndex = 0;
			else if (event.key === 'End') nextIndex = items.length - 1;
			else if (event.key === 'ArrowDown') nextIndex = (currentIndex + 1) % items.length;
			else if (event.key === 'ArrowUp') nextIndex = (currentIndex - 1 + items.length) % items.length;
			else return;
			event.preventDefault();
			items[nextIndex]?.focus();
		});
	});
});
