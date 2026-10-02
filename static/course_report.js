/**
 * Whole-course Dolos report generation widget: "Generate Course Report"
 * button + progress panel, shared by dolos_hub.html and students_hub.html
 * (both include review/_course_report_panel.html, which loads this file).
 *
 * Previously this logic was duplicated inline in both templates and had
 * drifted out of sync: students_hub.html called a helper that assumed a
 * #hubCourseMeta element which only existed in dolos_hub.html, so its
 * "report ready" handler threw and silently got stuck. Every DOM lookup
 * here is therefore defensive (missing elements are simply skipped) so a
 * future template that omits a piece of the panel degrades instead of
 * breaking the whole handler.
 *
 * On success this stays on the current page and shows a clear success
 * message. Users explicitly asked to avoid redirect/reload jumps.
 */
(function () {
	var scriptEl = document.currentScript;
	if (!scriptEl) {
		return;
	}

	var generateUrl = scriptEl.getAttribute('data-generate-url');
	var checkUrlTemplate = scriptEl.getAttribute('data-check-url-template');
	var checkCurrentUrl = scriptEl.getAttribute('data-check-current-url');
	if (!generateUrl || !checkUrlTemplate || !checkCurrentUrl) {
		return;
	}

	var POLL_INTERVAL_MS = 3000;
	// Client-side safety net only; the server itself gives up on a stalled
	// task after 15 minutes (see COURSE_REPORT_STALE_SECONDS in views.py) and
	// reports "failed", so this just guards against an unexpected client-side
	// infinite loop rather than being the primary timeout.
	var MAX_POLL_ATTEMPTS = 500;

	var taskId = null;
	var pollHandle = null;
	var pollAttempts = 0;
	var gameHandle = null;

	function el(id) {
		return document.getElementById(id);
	}

	function formatTimestamp(isoText) {
		if (!isoText) {
			return 'Generated recently';
		}
		var d = new Date(isoText);
		if (isNaN(d.getTime())) {
			return 'Generated recently';
		}
		return d.toLocaleString();
	}

	function setCourseMeta(completedAt) {
		var meta = el('hubCourseMeta');
		var stamp = el('hubCourseMetaTimestamp');
		if (!meta || !stamp) {
			return;
		}
		stamp.textContent = 'Last course-wide report: ' + formatTimestamp(completedAt);
		meta.classList.add('visible');
	}

	function setHint(message) {
		var hint = el('hubCourseProgressHint');
		if (!hint) {
			return;
		}
		if (message) {
			hint.textContent = message;
			hint.style.display = '';
		} else {
			hint.textContent = '';
			hint.style.display = 'none';
		}
	}

	function setProgressBar(data) {
		var bar = el('hubCourseProgressBar');
		if (!bar) {
			return;
		}
		if (data && data.exercises_total) {
			bar.max = data.exercises_total;
			bar.value = data.exercises_done || 0;
		} else {
			bar.removeAttribute('value');
			bar.removeAttribute('max');
		}
	}

	function phaseMessage(data) {
		if (data.current_exercise) {
			if (data.phase === 'processing') {
				var remaining = (data.exercises_remaining != null) ? ' ' + data.exercises_remaining + ' exercise(s) left.' : '';
				return 'Generating report for ' + data.current_exercise + '\u2026' + remaining;
			}
			if (data.phase === 'collecting') {
				return 'Collecting submissions for ' + data.current_exercise + '\u2026';
			}
			if (data.phase === 'fetching') {
				return 'Fetching submissions for ' + data.current_exercise + '\u2026';
			}
			if (data.phase === 'packaging') {
				return 'Packaging ' + data.current_exercise + ' submissions\u2026';
			}
			if (data.phase === 'uploading') {
				return 'Uploading ' + data.current_exercise + ' to Dolos\u2026';
			}
			if (data.phase === 'analyzing') {
				return 'Dolos is analyzing ' + data.current_exercise + '\u2026';
			}
		}
		if (data.phase === 'packaging') {
			return 'Packaging submissions for upload\u2026';
		}
		if (data.phase === 'uploading') {
			return 'Uploading dataset to Dolos\u2026';
		}
		if (data.phase === 'analyzing') {
			var seconds = data.analyzing_seconds ? ' (' + data.analyzing_seconds + 's)' : '';
			return 'Dolos is analyzing the dataset\u2026' + seconds + ' This can take a while for large courses.';
		}
		if (data.phase === 'collecting') {
			return 'Collecting submissions\u2026';
		}
		if (data.phase === 'complete') {
			return 'All exercises processed successfully!';
		}
		return 'Generating course-wide report\u2026 this can take a few minutes.';
	}

	function updateProgressText(data) {
		var text = el('hubCourseProgressText');
		if (text) {
			text.classList.remove('status-error');
			text.textContent = phaseMessage(data);
		}
		setProgressBar(data);
		setHint(data.hint || null);
	}

	function setBusy(busy) {
		var btn = el('generateCourseBtn');
		if (btn) {
			btn.disabled = busy;
		}
	}

	function idleButtonText(btn) {
		return btn && btn.getAttribute('data-force') === '1'
			? 'Regenerate Course Report'
			: 'Generate Course Report';
	}

	function isGameHidden() {
		try {
			return window.localStorage.getItem('radar_pong_hidden') === '1';
		} catch (error) {
			return false;
		}
	}

	function syncGameToggle() {
		var toggle = el('hubCourseGameToggle');
		if (toggle) {
			toggle.textContent = isGameHidden() ? 'Show game' : 'Hide game';
		}
	}

	function toggleGame() {
		var hide = !isGameHidden();
		try {
			window.localStorage.setItem('radar_pong_hidden', hide ? '1' : '0');
		} catch (error) {
			// Storage unavailable: the toggle still works for this page view.
		}
		if (hide) {
			stopGame();
		} else {
			startGame();
		}
		syncGameToggle();
	}

	function startGame() {
		var canvas = el('canvas');
		if (!canvas || gameHandle || isGameHidden()) {
			return;
		}
		canvas.classList.add('active');
		var ctx = canvas.getContext('2d');
		var paddles = [0, 0];
		var ball = [0, 0, -0.016, 0];
		var score = [0, 0];
		var cursor = 0;
		var reactionSpeed = 6;
		var reactionDistance = -0.5;

		canvas.addEventListener('pointermove', function (event) {
			var bounds = canvas.getBoundingClientRect();
			cursor = (event.clientY - bounds.top) / bounds.height * 2 - 1;
		});
		ctx.textAlign = 'center';
		ctx.font = '50px "Press Start 2P", Arial, sans-serif';
		ctx.fillStyle = 'white';

		gameHandle = window.setInterval(function () {
			if (Math.abs(ball[0]) >= 1) {
				score[ball[0] < 0 ? 1 : 0] += 1;
				ball = [0, 0, ball[0] < 0 ? -0.016 : 0.016, 0];
				reactionDistance = -0.5;
				reactionSpeed = 6;
				return;
			}
			ctx.clearRect(0, 0, 500, 500);
			if (Math.abs(ball[1]) >= 1) { ball[3] = -ball[3]; }
			ball[0] += ball[2];
			ball[1] += ball[3];
			paddles[0] = cursor;
			if (ball[0] > reactionDistance && ball[2] > 0) {
				paddles[1] += ball[1] > paddles[1] + 10 / 250 ? reactionSpeed / 250 : ball[1] < paddles[1] - 10 / 250 ? -reactionSpeed / 250 : 0;
			}
			if (Math.abs(paddles[0]) > 210 / 250) { paddles[0] = paddles[0] / Math.abs(paddles[0]) * 210 / 250; }
			if (Math.abs(paddles[1]) > 210 / 250) { paddles[1] = paddles[1] / Math.abs(paddles[1]) * 210 / 250; }
			ctx.fillRect(20, paddles[0] * 250 + 225, 10, 50);
			ctx.fillRect(470, paddles[1] * 250 + 225, 10, 50);
			ctx.fillRect(ball[0] * 250 + 245, ball[1] * 250 + 245, 10, 10);
			ctx.fillText(score[0] + ' : ' + score[1], 250, 100);
			if ((ball[0] > -220 / 250 && ball[0] + ball[2] <= -220 / 250 && Math.abs(paddles[0] - ball[1] - ball[3] * (-220 / 250 - ball[0]) / ball[2]) <= 30 / 250) ||
				(ball[0] < 220 / 250 && ball[0] + ball[2] >= 220 / 250 && Math.abs(paddles[1] - ball[1] - ball[3] * (220 / 250 - ball[0]) / ball[2]) <= 30 / 250)) {
				var alpha = (ball[0] < 0 ? 1 : -1) * (7 / 16 * (Math.atan(ball[3] / -ball[2]) + Math.PI / 2) + 0.004375 * Math.PI * (ball[1] - paddles[ball[0] < 0 ? 0 : 1]) * 500 + 27 / 64 * Math.PI - Math.atan(ball[3] / -ball[2]) + Math.PI * 3 / 8);
				var nextX = ball[2] * Math.cos(alpha) - ball[3] * Math.sin(alpha);
				var nextY = ball[2] * Math.sin(alpha) + ball[3] * Math.cos(alpha);
				ball[2] = nextX * 1.02;
				ball[3] = nextY * 1.02;
				reactionSpeed = Math.random() * 4.5 + 1.7;
				reactionDistance = Math.random() * 0.7 - 1;
			}
		}, 1000 / 60);
	}

	function stopGame() {
		if (gameHandle) {
			window.clearInterval(gameHandle);
			gameHandle = null;
		}
		var canvas = el('canvas');
		if (canvas) {
			canvas.classList.remove('active');
		}
	}

	function stopPolling() {
		if (pollHandle) {
			window.clearInterval(pollHandle);
			pollHandle = null;
		}
	}

	function startPolling() {
		stopPolling();
		pollAttempts = 0;
		pollHandle = window.setInterval(checkCourseReportStatus, POLL_INTERVAL_MS);
	}

	function showFailure(message) {
		var progress = el('hubCourseProgress');
		var text = el('hubCourseProgressText');
		if (progress) {
			progress.classList.add('active');
		}
		if (text) {
			text.classList.add('status-error');
			text.textContent = 'Report generation failed: ' + (message || 'Unknown error');
		}
		setHint(null);
		setProgressBar(null);
		setBusy(false);
		var btn = el('generateCourseBtn');
		if (btn) {
			btn.textContent = idleButtonText(btn);
		}
		stopGame();
		stopPolling();
	}

	function reloadOnceForReport(data) {
		if (!window.sessionStorage) {
			window.location.reload();
			return;
		}

		var reportIds = [];
		if (Array.isArray(data.report_ids) && data.report_ids.length > 0) {
			reportIds = data.report_ids;
		} else if (data.report_id) {
			reportIds = [data.report_id];
		}
		var reloadKey = 'course_report_reloaded:' + reportIds.join(',');
		if (!reportIds.length || window.sessionStorage.getItem(reloadKey)) {
			return;
		}
		window.sessionStorage.setItem(reloadKey, '1');
		window.location.reload();
	}

	function showReady(data) {
		var progress = el('hubCourseProgress');
		var btn = el('generateCourseBtn');
		if (progress) {
			progress.classList.remove('active');
		}
		setHint(null);
		setCourseMeta(data && data.completed_at);
		setBusy(false);
		if (btn) {
			btn.setAttribute('data-force', '1');
			btn.textContent = idleButtonText(btn);
		}
		stopGame();
		stopPolling();
	}

	function startCourseReportGeneration() {
		var progress = el('hubCourseProgress');
		var text = el('hubCourseProgressText');
		setBusy(true);
		if (progress) {
			progress.classList.add('active');
		}
		if (text) {
			text.classList.remove('status-error');
			text.textContent = 'Queuing course-wide report generation\u2026';
		}
		setHint(null);
		setProgressBar(null);
		startGame();

		var btn = el('generateCourseBtn');
		var requestUrl = generateUrl;
		if (btn && btn.getAttribute('data-force') === '1') {
			requestUrl += (requestUrl.indexOf('?') === -1 ? '?' : '&') + 'force=1';
		}

		fetch(requestUrl, {
			method: 'GET',
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) {
				if (data.status === 'queued') {
					taskId = data.task_id;
					updateProgressText(data);
					startPolling();
				} else {
					showFailure(data.message);
				}
			})
			.catch(function () {
				showFailure('Failed to reach Radar to start report generation. Try again.');
			});
	}

	function checkCourseReportStatus() {
		if (!taskId) {
			stopPolling();
			return;
		}
		pollAttempts += 1;
		if (pollAttempts > MAX_POLL_ATTEMPTS) {
			showFailure('Gave up waiting for a response after a very long time. Please try again.');
			return;
		}
		fetch(checkUrlTemplate.replace('__TASK__', taskId), {
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) {
				if (data.status === 'ready') {
					showReady(data);
					reloadOnceForReport(data);
				} else if (data.status === 'failed') {
					showFailure(data.message);
				} else if (data.status === 'pending') {
					updateProgressText(data);
					setBusy(true);
				}
			})
			.catch(function () {
				// Transient network hiccup: keep polling rather than giving up.
			});
	}

	function restoreStatusAfterRefresh() {
		fetch(checkCurrentUrl, {
			method: 'GET',
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) {
				var btn = el('generateCourseBtn');
				if (data.status === 'pending' && data.task_id) {
					taskId = data.task_id;
					var progress = el('hubCourseProgress');
					if (progress) {
						progress.classList.add('active');
					}
					updateProgressText(data);
					setBusy(true);
					if (btn) {
						btn.textContent = 'Report In Progress';
					}
					startGame();
					startPolling();
				} else if (data.status === 'ready') {
					showReady(data);
					reloadOnceForReport(data);
				} else if (data.status === 'failed') {
					showFailure(data.message);
				}
			})
			.catch(function () {
				// No-op: the manual "Generate" button still works even if this
				// best-effort restore call fails.
			});
	}

	var button = el('generateCourseBtn');
	if (button) {
		button.addEventListener('click', startCourseReportGeneration);
	}
	var initialCanvas = el('canvas');
	var gameToggle = el('hubCourseGameToggle');
	if (gameToggle) {
		gameToggle.addEventListener('click', toggleGame);
	}
	syncGameToggle();
	if (initialCanvas && isGameHidden()) {
		initialCanvas.classList.remove('active');
	}
	if (initialCanvas && initialCanvas.classList.contains('active')) {
		startGame();
	}
	// ?generate=1 comes from the Refresh menu on pages without the course panel.
	var params = new URLSearchParams(window.location.search);
	if (button && params.get('generate') === '1') {
		params.delete('generate');
		var query = params.toString();
		history.replaceState(null, '', window.location.pathname + (query ? '?' + query : '') + window.location.hash);
		startCourseReportGeneration();
	} else {
		restoreStatusAfterRefresh();
	}
})();
