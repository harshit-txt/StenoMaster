/* ==========================================================================
   assignment.js - the three practice steps
     Step 1  Listen   (#player)        audio, speed slider, auto-redirect to reading
     Step 2  Reading  (#reading)       5-minute countdown, auto-redirect to typing
     Step 3  Typing   (#typing-form)   50-minute countdown, draft saving, auto-submit

   Time limits come from steno_project/settings.py (TYPING_SECONDS, READING_SECONDS,
   AUDIO_END_REDIRECT_SECONDS, WPM_MIN, WPM_MAX). The page passes them in data-* attributes.
   ========================================================================== */
(function () {
  'use strict';

  /* ---------- EDIT these switches ---------- */
  var ALLOW_SEEK = false;      // true = student may click the progress bar to jump around in the audio
  var ALLOW_PASTE = false;     // true = pasting into the typing pad is allowed
  var WARNING_SECONDS = 120;   // the "time is nearly up" warning appears at this many seconds left
  var DRAFT_SAVE_MS = 15000;   // typed text is also saved every 15 seconds (and 1 second after each key press)
  var PAD_SIZE_MIN = 16, PAD_SIZE_MAX = 40, PAD_SIZE_STEP = 2;   // text size limits for the A- / A+ buttons (px)

  /* ---------- small helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function mmss(total) {
    total = Math.max(0, Math.round(total));
    var m = Math.floor(total / 60), s = total % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }
  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function drop(key) { try { localStorage.removeItem(key); } catch (e) {} }

  /* ==================================================================
     STEP 1 - LISTEN
     ================================================================== */
  var player = $('player');
  if (player) {
    var audio = $('audio');
    var playBtn = $('play-btn');
    var bar = $('bar'), barFill = $('bar-fill');
    var timeCur = $('time-cur'), timeTotal = $('time-total');
    var range = $('wpm-range'), wpmValue = $('wpm-value'), speedNote = $('speed-note');
    var endBox = $('end-box'), endCount = $('end-count');

    var assignmentId = player.dataset.assignment;
    var baseWpm = parseInt(player.dataset.baseWpm, 10) || 80;     // speed the audio was recorded at
    var wpmMin = parseInt(player.dataset.wpmMin, 10) || 60;
    var wpmMax = parseInt(player.dataset.wpmMax, 10) || 120;
    var redirectSeconds = parseInt(player.dataset.redirectSeconds, 10) || 5;
    var nextUrl = player.dataset.nextUrl;
    var redirectTimer = null;

    // a new attempt starts here: forget any old typing draft for this dictation
    drop('steno-draft-' + assignmentId);

    // restore the speed chosen last time (default = the speed the audio was recorded at)
    var saved = parseInt(load('steno-wpm-' + assignmentId), 10);
    var wpm = saved >= wpmMin && saved <= wpmMax ? saved : Math.min(wpmMax, Math.max(wpmMin, baseWpm));
    range.value = wpm;

    var speedBox = $('speed-box'), speedLock = $('speed-lock'), restartBtn = $('restart-btn');
    var started = false;          // true once the student has pressed play: the speed is then locked

    // The audio is played faster/slower by changing playbackRate = chosen WPM / recorded WPM.
    // Some browsers reset playbackRate when the file loads or playback starts, so we set it again
    // at those moments too (see the event listeners below).
    function currentRate() { return wpm / baseWpm; }
    function pushRate() {
      var rate = currentRate();
      if (Math.abs(audio.playbackRate - rate) > 0.001) audio.playbackRate = rate;
      audio.defaultPlaybackRate = rate;
      // keep the voice pitch natural when the speed changes
      audio.preservesPitch = true; audio.mozPreservesPitch = true; audio.webkitPreservesPitch = true;
    }
    function applySpeed() {
      if (started) { range.value = wpm; return; }          // locked: ignore any change
      wpm = parseInt(range.value, 10);
      pushRate();
      wpmValue.textContent = wpm;
      store('steno-wpm-' + assignmentId, wpm);             // the typing page reads this to record the speed used
      updateNote();
    }
    function updateNote() {
      var x = (currentRate()).toFixed(2).replace(/0$/, '').replace(/\.0$/, '');
      var text = 'Recorded at ' + baseWpm + ' WPM, so you will hear it at ' + x + 'x speed.';
      if (isFinite(audio.duration)) text += ' It lasts about ' + mmss(audio.duration / currentRate()) + '.';
      speedNote.textContent = text;
    }
    function lockSpeed(on) {
      started = on;
      range.disabled = on;
      speedBox.classList.toggle('is-locked', on);
      speedLock.hidden = !on;
    }
    range.addEventListener('input', applySpeed);
    applySpeed();

    function setPlaying(on) {
      playBtn.classList.toggle('is-playing', on);
      playBtn.setAttribute('aria-label', on ? 'Pause' : 'Play');
    }
    playBtn.addEventListener('click', function () {
      if (audio.paused) {
        cancelRedirect();
        pushRate();                                        // make sure the chosen speed is applied before sound starts
        audio.play().catch(function () { /* browser blocked playback: user can press again */ });
      } else {
        audio.pause();
      }
    });
    // Space bar = play / pause (unless the student is using the slider)
    document.addEventListener('keydown', function (e) {
      if (e.code === 'Space' && document.activeElement === document.body) {
        e.preventDefault();
        playBtn.click();
      }
    });
    audio.addEventListener('play', function () { pushRate(); lockSpeed(true); setPlaying(true); });
    audio.addEventListener('playing', pushRate);
    audio.addEventListener('pause', function () { setPlaying(false); });
    audio.addEventListener('canplay', pushRate);
    function onMeta() { pushRate(); timeTotal.textContent = mmss(audio.duration); updateNote(); }
    audio.addEventListener('loadedmetadata', onMeta);
    if (audio.readyState >= 1) onMeta();          // metadata may already be loaded before this script ran
    audio.addEventListener('timeupdate', function () {
      timeCur.textContent = mmss(audio.currentTime);
      var pct = audio.duration ? (audio.currentTime / audio.duration) * 100 : 0;
      barFill.style.width = pct + '%';
      bar.setAttribute('aria-valuenow', Math.round(pct));
    });

    if (ALLOW_SEEK) {
      bar.classList.add('seekable');
      bar.addEventListener('click', function (e) {
        var r = bar.getBoundingClientRect();
        if (audio.duration) audio.currentTime = ((e.clientX - r.left) / r.width) * audio.duration;
      });
    }

    // audio finished -> short countdown, then the reading page opens
    audio.addEventListener('ended', function () {
      setPlaying(false);
      endBox.hidden = false;
      var left = redirectSeconds;
      endCount.textContent = left;
      redirectTimer = setInterval(function () {
        left -= 1;
        endCount.textContent = Math.max(0, left);
        if (left <= 0) { clearInterval(redirectTimer); window.location.href = nextUrl; }
      }, 1000);
    });
    function cancelRedirect() {
      if (redirectTimer) { clearInterval(redirectTimer); redirectTimer = null; }
      endBox.hidden = true;
    }

    // START AGAIN: back to 0:00, stopped, and the speed slider is unlocked so a new speed can be chosen.
    // (If the dictation is part-way through, ask first so it is not pressed by accident.)
    function startAgain() {
      var midway = started && !audio.ended && audio.currentTime > 0;
      if (midway && !window.confirm('Start the dictation again from the beginning?')) return;
      cancelRedirect();
      audio.pause();
      audio.currentTime = 0;
      lockSpeed(false);
      setPlaying(false);
      timeCur.textContent = mmss(0);
      barFill.style.width = '0%';
      pushRate();
    }
    restartBtn.addEventListener('click', startAgain);
    $('listen-again').addEventListener('click', startAgain);
  }

  /* ==================================================================
     STEP 2 - READING (countdown, then go to typing)
     ================================================================== */
  var reading = $('reading');
  if (reading) {
    var readTotal = parseInt(reading.dataset.seconds, 10) || 300;
    var readEnd = Date.now() + readTotal * 1000;
    var readTimer = $('timer'), readFill = $('bar-fill');
    var readGo = reading.dataset.nextUrl;
    (function tickRead() {
      var left = Math.max(0, Math.ceil((readEnd - Date.now()) / 1000));
      readTimer.textContent = mmss(left);
      readFill.style.width = ((readTotal - left) / readTotal) * 100 + '%';
      if (left <= 0) { window.location.href = readGo; return; }
      setTimeout(tickRead, 250);
    })();
  }

  /* ==================================================================
     STEP 3 - TYPING
     ================================================================== */
  var form = $('typing-form');
  if (form) {
    var pad = $('steno-pad');
    var timerEl = $('timer');
    var warnBox = $('time-warning');
    var wcEl = $('word-count');
    var statusEl = $('save-status');
    var dialog = $('submit-dialog');
    var typingId = form.dataset.assignment;
    var attemptId = form.dataset.attempt;                 // changes for every new attempt
    var totalSeconds = parseInt(form.dataset.total, 10);
    var remainingAtLoad = parseInt(form.dataset.remaining, 10);
    var endAt = Date.now() + remainingAtLoad * 1000;      // clock is based on the SERVER's remaining time
    var draftKey = 'steno-draft-' + typingId;
    var submitting = false;

    // speed the student listened at (recorded with the result)
    var chosenWpm = parseInt(load('steno-wpm-' + typingId), 10);
    if (chosenWpm) $('wpm-used').value = chosenWpm;

    /* --- word count --- */
    function countWords() {
      var t = pad.value.trim();
      var n = t ? t.split(/\s+/).length : 0;
      wcEl.textContent = n;
      return n;
    }

    /* --- draft saving (survives refresh / closed tab) --- */
    function saveDraft() {
      store(draftKey, JSON.stringify({ attempt: attemptId, text: pad.value }));
      statusEl.textContent = 'Saved on this device at ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '.';
    }
    (function restoreDraft() {
      var raw = load(draftKey);
      if (!raw) return;
      try {
        var d = JSON.parse(raw);
        // only restore a draft that belongs to THIS attempt
        if (d.attempt === attemptId && d.text && !pad.value) pad.value = d.text;
      } catch (e) {}
      countWords();
    })();
    var typingDebounce;
    pad.addEventListener('input', function () {
      countWords();
      clearTimeout(typingDebounce);
      typingDebounce = setTimeout(saveDraft, 1000);
    });
    setInterval(function () { if (!submitting && pad.value) saveDraft(); }, DRAFT_SAVE_MS);

    /* --- paste block (see ALLOW_PASTE at the top) --- */
    if (!ALLOW_PASTE) {
      ['paste', 'drop'].forEach(function (evt) {
        pad.addEventListener(evt, function (e) {
          e.preventDefault();
          statusEl.textContent = 'Pasting is switched off. Please type the text.';
        });
      });
    }

    /* --- text size buttons --- */
    var size = parseInt(load('steno-pad-size'), 10) || 22;
    function applySize() {
      size = Math.min(PAD_SIZE_MAX, Math.max(PAD_SIZE_MIN, size));
      document.documentElement.style.setProperty('--pad-size', size + 'px');
      store('steno-pad-size', size);
    }
    applySize();
    $('size-up').addEventListener('click', function () { size += PAD_SIZE_STEP; applySize(); });
    $('size-down').addEventListener('click', function () { size -= PAD_SIZE_STEP; applySize(); });

    /* --- submitting --- */
    function finish() {
      submitting = true;
      $('client-seconds').value = Math.max(0, totalSeconds - Math.max(0, Math.round((endAt - Date.now()) / 1000)));
      drop(draftKey);                // the text now lives on the server
      form.submit();                 // form.submit() does not trigger the "submit" event again
    }
    // pressing the Submit button opens the confirm box first
    form.addEventListener('submit', function (e) {
      if (submitting) return;
      e.preventDefault();
      var left = Math.max(0, Math.round((endAt - Date.now()) / 1000));
      $('submit-summary').textContent = 'You have typed ' + countWords() + ' words and have ' + mmss(left) + ' left.';
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else if (window.confirm('Submit your assignment')) finish();      // very old browsers
    });
    $('dialog-cancel').addEventListener('click', function () { dialog.close(); pad.focus(); });
    $('dialog-confirm').addEventListener('click', finish);

    /* --- warn before leaving the page by accident --- */
    window.addEventListener('beforeunload', function (e) {
      if (!submitting && pad.value.trim()) { e.preventDefault(); e.returnValue = ''; }
    });

    /* --- the countdown --- */
    var warned = false;
    (function tick() {
      var left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      timerEl.textContent = mmss(left);
      if (left <= WARNING_SECONDS && !warned) {
        warned = true;
        timerEl.classList.add('warn');
        warnBox.classList.add('show');
      }
      if (left <= 0) {
        // time is over: submit whatever has been typed, no questions asked
        if (dialog.open) dialog.close();
        finish();
        return;
      }
      setTimeout(tick, 250);
    })();
    countWords();
  }
})();
