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

  function renderTimeline(track, slots, dateStr, startMins, endMins) {
    track.innerHTML = "";

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
      track.appendChild(block);
    });

    if (startMins != null && endMins != null && endMins > startMins) {
      const sel = document.createElement("div");
      sel.className = "time-range-bar__selection";
      sel.style.left = `${pctOnBar(startMins)}%`;
      sel.style.width = `${Math.max(pctOnBar(endMins) - pctOnBar(startMins), 0.8)}%`;
      track.appendChild(sel);
    }
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
        <div class="time-range-bar__track"></div>
        <div class="time-range-bar__labels">
          <span>08:00</span><span>12:00</span><span>16:00</span><span>20:00</span><span>24:00</span>
        </div>
      </div>
      <p class="time-range-picker__hint text-muted small mb-2">
        Укажите время в полях ниже. Красная полоса — уже занято.
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

    const sync = () => {
      const startMins = parseInputTime(startInput?.value);
      const endMins = parseInputTime(endInput?.value);
      pickStartEl.textContent = startInput?.value || "—";
      pickEndEl.textContent = endInput?.value || "—";
      const dateStr = dateInput?.value || "";
      renderTimeline(track, bookedSlots, dateStr, startMins, endMins);
      if (onChange) onChange({ start: startMins, end: endMins });
    };

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
