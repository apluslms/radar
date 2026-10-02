/**
 * Submission re-fetch progress widget: polls the course's refresh status so
 * the panel survives page refreshes (the task id lives server-side).
 * Included by review/_refresh_menu.html on the Dolos hub pages.
 */
(function () {
	var scriptEl = document.currentScript;
	if (!scriptEl) {
		return;
	}
	var statusUrl = scriptEl.getAttribute('data-status-url');
	if (!statusUrl) {
		return;
	}

	var POLL_INTERVAL_MS = 2000;
	var pollHandle = null;

	function el(id) {
		return document.getElementById(id);
	}

	function stopPolling() {
		if (pollHandle) {
			window.clearInterval(pollHandle);
			pollHandle = null;
		}
	}

	function showPanel(text, error) {
		var panel = el('hubRefreshProgress');
		var label = el('hubRefreshProgressText');
		if (!panel || !label) {
			return;
		}
		panel.classList.add('active');
		label.classList.toggle('status-error', !!error);
		label.textContent = text;
	}

	function hidePanel() {
		var panel = el('hubRefreshProgress');
		if (panel) {
			panel.classList.remove('active');
		}
	}

	function setBar(done, total) {
		var bar = el('hubRefreshProgressBar');
		if (!bar) {
			return;
		}
		if (total) {
			bar.max = total;
			bar.value = done || 0;
		} else {
			bar.removeAttribute('value');
			bar.removeAttribute('max');
		}
	}

	function messageFor(data) {
		if (data.phase === 'reloading' && data.current_exercise) {
			var base = 'Re-fetching ' + data.current_exercise + ' (' +
				(data.exercises_done || 0) + '/' + (data.exercises_total || '?') + ' exercises)';
			if (data.submissions_total) {
				base += ' \u2014 ' + (data.submissions_done || 0) + '/' + data.submissions_total + ' submissions';
			}
			return base + '\u2026';
		}
		if (data.phase === 'complete') {
			var failed = data.exercises_failed && data.exercises_failed.length;
			return failed
				? 'Re-fetch finished, but ' + failed + ' exercise(s) failed.'
				: 'Re-fetch finished.';
		}
		return 'Queuing submission re-fetch\u2026';
	}

	function applyStatus(data) {
		if (data.status === 'idle') {
			stopPolling();
			return;
		}
		if (data.status === 'pending') {
			showPanel(messageFor(data), false);
			setBar(data.exercises_done, data.exercises_total);
			return;
		}
		stopPolling();
		if (data.status === 'ready') {
			setBar(1, 1);
			showPanel('Re-fetch finished. Reloading\u2026', false);
			window.setTimeout(function () {
				window.location.reload();
			}, 800);
		} else {
			showPanel('Re-fetch failed: ' + (data.message || 'Unknown error'), true);
		}
	}

	function poll() {
		fetch(statusUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
			.then(function (response) { return response.json(); })
			.then(applyStatus)
			.catch(function () {
				// Transient error: keep polling.
			});
	}

	function startPolling() {
		stopPolling();
		pollHandle = window.setInterval(poll, POLL_INTERVAL_MS);
	}

	// Restore an in-flight refresh after a page reload.
	poll();

	var form = el('hubRefreshForm');
	if (form) {
		form.addEventListener('submit', function () {
			// The submit itself starts the task; begin polling shortly after.
			window.setTimeout(poll, 500);
			window.setTimeout(startPolling, 2500);
		});
	}
})();
