/**
 * Табы «Сегодня / Вчера / Завтра / Календарь» с AJAX-загрузкой списка.
 */
window.SakuraDateTabs = (function () {
  function mount(root, { onLoad, defaultDate = 'today', showTomorrow = false }) {
    if (!root) return;

    const tabs = document.createElement('div');
    tabs.className = 'date-filter-tabs btn-group mb-3';
    tabs.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-date="today">Сегодня</button>
      <button type="button" class="btn btn-outline-secondary" data-date="yesterday">Вчера</button>
      ${showTomorrow ? '<button type="button" class="btn btn-outline-secondary" data-date="tomorrow">Завтра</button>' : ''}
      <input type="date" class="form-control date-filter-calendar" style="max-width:11rem" aria-label="Календарь">`;

    root.prepend(tabs);
    const calendar = tabs.querySelector('.date-filter-calendar');

    function setActive(value) {
      tabs.querySelectorAll('button').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.date === value);
        btn.classList.toggle('btn-sakura', btn.dataset.date === value);
        btn.classList.toggle('btn-outline-secondary', btn.dataset.date !== value);
      });
    }

    function load(value) {
      setActive(value === calendar.value ? null : value);
      if (value !== 'today' && value !== 'yesterday' && value !== 'tomorrow') {
        calendar.value = value;
      }
      onLoad(value);
    }

    tabs.querySelectorAll('button').forEach((btn) => {
      btn.addEventListener('click', () => load(btn.dataset.date));
    });
    calendar.addEventListener('change', () => {
      if (calendar.value) load(calendar.value);
    });

    load(defaultDate);
  }

  return { mount };
})();
