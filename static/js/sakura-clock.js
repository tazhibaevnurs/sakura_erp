/**
 * Сакура: текущее время и выбор интервала (без кругового 24-часового циферблата).
 */
(function (global) {
  const MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
  ];
  const DAYS_RU = [
    "воскресенье", "понедельник", "вторник", "среда",
    "четверг", "пятница", "суббота",
  ];

  const pad = (n) => String(n).padStart(2, "0");

  const formatDigital = (d) =>
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

  const formatDate = (d) =>
    `${DAYS_RU[d.getDay()]}, ${d.getDate()} ${MONTHS_RU[d.getMonth()]} ${d.getFullYear()}`;

  const formatTimeShort = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  const localDateKey = (d) =>
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  const parseInputTime = (val) => {
    if (!val) return null;
    const [h, m] = val.split(":").map(Number);
    return (h || 0) * 60 + (m || 0);
  };

  const minutesToInputValue = (mins) => {
    const h = Math.floor(mins / 60) % 24;
    const m = mins % 60;
    return `${pad(h)}:${pad(m)}`;
  };

  const DAY_START = 8 * 60;
  const DAY_END = 24 * 60;
  const DAY_SPAN = DAY_END - DAY_START;

  const pctOnBar = (mins) => {
    const clamped = Math.max(DAY_START, Math.min(mins, DAY_END));
    return ((clamped - DAY_START) / DAY_SPAN) * 100;
  };

  function mountLive(container) {
    container.classList.add("sakura-live-clock");
    container.innerHTML = `
      <div class="sakura-live-clock__time">00:00:00</div>
      <div class="sakura-live-clock__date"></div>
      <div class="sakura-live-clock__tz">Душанбе (UTC+5)</div>
    `;
    const timeEl = container.querySelector(".sakura-live-clock__time");
    const dateEl = container.querySelector(".sakura-live-clock__date");

    const tick = () => {
      const now = new Date();
      timeEl.textContent = formatDigital(now);
      dateEl.textContent = formatDate(now);
    };
    tick();
    return setInterval(tick, 1000);
  }

  const SNAP = 15;
  const MIN_DURATION = 15;

  const snapMins = (m) => Math.round(m / SNAP) * SNAP;

  const minsFromPct = (pct) => DAY_START + (pct / 100) * DAY_SPAN;

  const pctFromClientX = (el, clientX) => {
    const rect = el.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    return (x / rect.width) * 100;
  };

  const clientXToMins = (el, clientX) =>
    snapMins(minsFromPct(pctFromClientX(el, clientX)));

  function getBookedRanges(slots, dateStr) {
    return slots
      .map((slot) => {
        const start = new Date(slot.start);
        const end = new Date(slot.end);
        if (dateStr && localDateKey(start) !== dateStr) return null;
        return {
          start: start.getHours() * 60 + start.getMinutes(),
          end: end.getHours() * 60 + end.getMinutes(),
        };
      })
      .filter(Boolean);
  }

  function overlapsBooked(startMins, endMins, booked) {
    return booked.some((b) => startMins < b.end && endMins > b.start);
  }

  function clampRange(startMins, endMins, booked) {
    let start = snapMins(Math.max(DAY_START, Math.min(startMins, DAY_END - MIN_DURATION)));
    let end = snapMins(Math.min(DAY_END, Math.max(endMins, start + MIN_DURATION)));
    if (end <= start) end = Math.min(DAY_END, start + MIN_DURATION);
    if (overlapsBooked(start, end, booked)) return null;
    return { start, end };
  }

  function renderBookedSlots(layer, slots, dateStr) {
    layer.innerHTML = "";
    slots.forEach((slot) => {
      const start = new Date(slot.start);
      const end = new Date(slot.end);
      if (dateStr && localDateKey(start) !== dateStr) return;

      const m1 = start.getHours() * 60 + start.getMinutes();
      const m2 = end.getHours() * 60 + end.getMinutes();
      const left = pctOnBar(m1);
      const right = pctOnBar(m2);
      const width = Math.max(right - left, 0.8);

      const block = document.createElement("div");
      block.className = "time-range-bar__booked";
      block.style.left = `${left}%`;
      block.style.width = `${width}%`;
      const tableLabel = slot.table ? `, стол №${slot.table}` : "";
      block.title = `${slot.guest || "Бронь"}${tableLabel}: ${formatTimeShort(start)}–${formatTimeShort(end)}`;
      layer.appendChild(block);
    });
  }

  function updateSelectionEl(sel, startMins, endMins) {
    if (startMins == null || endMins == null || endMins <= startMins) {
      sel.style.display = "none";
      return;
    }
    sel.style.display = "block";
    sel.style.left = `${pctOnBar(startMins)}%`;
    sel.style.width = `${Math.max(pctOnBar(endMins) - pctOnBar(startMins), 0.8)}%`;
  }

  function renderTimeline(track, slots, dateStr, startMins, endMins) {
    const layer = track.querySelector(".time-range-bar__booked-layer");
    const sel = track.querySelector(".time-range-bar__selection");
    if (layer) renderBookedSlots(layer, slots, dateStr);
    if (sel) updateSelectionEl(sel, startMins, endMins);
  }

  function mountPicker(container, options) {
    const {
      bookedSlots = [],
      dateInput,
      startInput,
      endInput,
      onChange,
    } = options;

    container.classList.add("time-range-picker");
    container.innerHTML = `
      <div class="time-range-picker__now">
        <span class="time-range-picker__now-label">Сейчас</span>
        <strong class="time-range-picker__now-value">00:00:00</strong>
      </div>
      <div class="time-range-picker__selected">
        <div><span class="text-muted">Начало</span> <strong class="time-range-picker__start">—</strong></div>
        <div><span class="text-muted">Конец</span> <strong class="time-range-picker__end">—</strong></div>
      </div>
      <div class="time-range-bar" aria-hidden="true">
        <div class="time-range-bar__track">
          <div class="time-range-bar__booked-layer"></div>
          <div class="time-range-bar__selection">
            <div class="time-range-bar__handle time-range-bar__handle--start" data-handle="start"></div>
            <div class="time-range-bar__handle time-range-bar__handle--end" data-handle="end"></div>
          </div>
        </div>
        <div class="time-range-bar__labels">
          <span>08:00</span><span>12:00</span><span>16:00</span><span>20:00</span><span>24:00</span>
        </div>
      </div>
      <p class="time-range-picker__hint text-muted small mb-2">
        Перетащите синюю полосу или её края мышью. Красная — уже занято.
      </p>
      <div class="time-range-picker__presets">
        <span class="small text-muted me-1">Быстро:</span>
        <button type="button" class="btn btn-sm btn-outline-secondary" data-preset="60">1 ч</button>
        <button type="button" class="btn btn-sm btn-outline-secondary" data-preset="120">2 ч</button>
        <button type="button" class="btn btn-sm btn-outline-secondary" data-preset="180">3 ч</button>
      </div>
    `;

    const track = container.querySelector(".time-range-bar__track");
    const nowEl = container.querySelector(".time-range-picker__now-value");
    const pickStartEl = container.querySelector(".time-range-picker__start");
    const pickEndEl = container.querySelector(".time-range-picker__end");

    let dragState = null;

    const getBooked = () => getBookedRanges(bookedSlots, dateInput?.value || "");

    const sync = () => {
      const startMins = parseInputTime(startInput?.value);
      const endMins = parseInputTime(endInput?.value);
      pickStartEl.textContent = startInput?.value || "—";
      pickEndEl.textContent = endInput?.value || "—";
      const dateStr = dateInput?.value || "";
      renderTimeline(track, bookedSlots, dateStr, startMins, endMins);
      if (onChange) onChange({ start: startMins, end: endMins });
    };

    const setRange = (startMins, endMins) => {
      if (startInput) startInput.value = minutesToInputValue(startMins);
      if (endInput) endInput.value = minutesToInputValue(endMins);
      sync();
    };

    const minsAt = (clientX) => clientXToMins(track, clientX);

    const endDrag = () => {
      dragState = null;
      track.classList.remove("time-range-bar__track--dragging");
      document.body.classList.remove("time-range-dragging");
      document.removeEventListener("mousemove", onDragMove);
      document.removeEventListener("mouseup", endDrag);
      document.removeEventListener("touchmove", onTouchMove);
      document.removeEventListener("touchend", endDrag);
      sync();
    };

    const onDragMove = (clientX) => {
      if (!dragState) return;
      const booked = getBooked();
      const m = minsAt(clientX);

      if (dragState.mode === "move") {
        const delta = m - dragState.pointerStart;
        const duration = dragState.origEnd - dragState.origStart;
        let newStart = dragState.origStart + delta;
        let newEnd = dragState.origEnd + delta;
        if (newStart < DAY_START) {
          newStart = DAY_START;
          newEnd = newStart + duration;
        }
        if (newEnd > DAY_END) {
          newEnd = DAY_END;
          newStart = newEnd - duration;
        }
        const valid = clampRange(newStart, newEnd, booked);
        if (valid) setRange(valid.start, valid.end);
      } else if (dragState.mode === "resize-start") {
        const valid = clampRange(m, dragState.origEnd, booked);
        if (valid && valid.end - valid.start >= MIN_DURATION) {
          setRange(valid.start, dragState.origEnd);
        }
      } else if (dragState.mode === "resize-end") {
        const valid = clampRange(dragState.origStart, m, booked);
        if (valid && valid.end - valid.start >= MIN_DURATION) {
          setRange(dragState.origStart, valid.end);
        }
      } else if (dragState.mode === "create") {
        let start = dragState.anchor;
        let end = m;
        if (end < start) [start, end] = [end, start];
        if (end - start < MIN_DURATION) end = start + MIN_DURATION;
        const valid = clampRange(start, end, booked);
        if (valid) setRange(valid.start, valid.end);
      }
    };

    const onMouseMove = (e) => {
      if (!dragState) return;
      e.preventDefault();
      onDragMove(e.clientX);
    };

    const onTouchMove = (e) => {
      if (!dragState || !e.touches.length) return;
      e.preventDefault();
      onDragMove(e.touches[0].clientX);
    };

    const beginDrag = (state, e) => {
      e.preventDefault();
      e.stopPropagation();
      dragState = state;
      track.classList.add("time-range-bar__track--dragging");
      document.body.classList.add("time-range-dragging");
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", endDrag);
      document.addEventListener("touchmove", onTouchMove, { passive: false });
      document.addEventListener("touchend", endDrag);
    };

    const onTrackDown = (e) => {
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      if (e.type === "mousedown" && e.button !== 0) return;

      const handle = e.target.closest("[data-handle]");
      const startMins = parseInputTime(startInput?.value);
      const endMins = parseInputTime(endInput?.value);

      if (handle?.dataset.handle === "start" && startMins != null && endMins != null) {
        beginDrag({ mode: "resize-start", origStart: startMins, origEnd: endMins }, e);
        return;
      }
      if (handle?.dataset.handle === "end" && startMins != null && endMins != null) {
        beginDrag({ mode: "resize-end", origStart: startMins, origEnd: endMins }, e);
        return;
      }
      if (e.target.closest(".time-range-bar__selection") && startMins != null && endMins != null) {
        beginDrag({
          mode: "move",
          origStart: startMins,
          origEnd: endMins,
          pointerStart: minsAt(clientX),
        }, e);
        return;
      }

      const clicked = minsAt(clientX);
      const booked = getBooked();
      if (booked.some((b) => clicked >= b.start && clicked < b.end)) return;

      const duration =
        startMins != null && endMins != null && endMins > startMins
          ? endMins - startMins
          : 120;
      let newStart = clicked;
      let newEnd = clicked + duration;
      if (newEnd > DAY_END) {
        newEnd = DAY_END;
        newStart = Math.max(DAY_START, newEnd - duration);
      }
      const valid = clampRange(newStart, newEnd, booked);
      if (!valid) return;

      setRange(valid.start, valid.end);
      beginDrag({
        mode: "create",
        anchor: valid.start,
        origStart: valid.start,
        origEnd: valid.end,
      }, e);
    };

    track.addEventListener("mousedown", onTrackDown);
    track.addEventListener("touchstart", onTrackDown, { passive: false });

    const liveTick = () => {
      nowEl.textContent = formatDigital(new Date());
    };
    liveTick();
    const liveIv = setInterval(liveTick, 1000);

    dateInput?.addEventListener("change", sync);
    startInput?.addEventListener("change", sync);
    startInput?.addEventListener("input", sync);
    endInput?.addEventListener("change", sync);
    endInput?.addEventListener("input", sync);

    container.querySelectorAll("[data-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mins = Number(btn.dataset.preset);
        let startMins = parseInputTime(startInput?.value);
        if (startMins == null) {
          const now = new Date();
          startMins = now.getHours() * 60 + Math.ceil(now.getMinutes() / 15) * 15;
        }
        if (startInput) startInput.value = minutesToInputValue(startMins);
        if (endInput) endInput.value = minutesToInputValue(startMins + mins);
        sync();
      });
    });

    sync();

    return () => clearInterval(liveIv);
  }

  global.SakuraClock = { mountLive, mountPicker };
})(window);
