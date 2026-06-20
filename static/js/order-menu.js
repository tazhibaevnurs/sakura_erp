/**
 * Категории меню + корзина для заказов (навынос, доставка, приём).
 */
window.SakuraOrderMenu = (function () {
  function csrfToken() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  function mountMenu(container, categories, onAdd) {
    if (!container) return;
    container.innerHTML = '';
    if (!categories.length) {
      container.innerHTML = '<p class="text-muted small">Нет доступных блюд</p>';
      return;
    }
    categories.forEach((cat) => {
      const title = document.createElement('div');
      title.className = 'menu-category-title';
      title.textContent = cat.name;
      container.appendChild(title);

      const row = document.createElement('div');
      row.className = 'row g-2 mb-2';
      cat.items.forEach((item) => {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-xl-4';
        col.innerHTML = `
          <button type="button" class="menu-item-btn text-start w-100 h-100" data-item-id="${item.id}">
            <span class="d-block">${item.name}</span>
            <span class="text-muted small">${item.price} сом / ${item.unit}</span>
          </button>`;
        col.querySelector('button').addEventListener('click', () => onAdd(item));
        row.appendChild(col);
      });
      container.appendChild(row);
    });
  }

  function createCart() {
    const items = [];
    return {
      items,
      add(item, qty = 1) {
        const existing = items.find((r) => r.menu_item_id === item.id);
        if (existing) {
          existing.quantity = Number(existing.quantity) + Number(qty);
        } else {
          items.push({
            menu_item_id: item.id,
            name: item.name,
            price: item.price,
            unit: item.unit,
            quantity: qty,
          });
        }
      },
      remove(id) {
        const idx = items.findIndex((r) => r.menu_item_id === id);
        if (idx >= 0) items.splice(idx, 1);
      },
      total() {
        return items.reduce(
          (sum, r) => sum + Number(r.price) * Number(r.quantity),
          0
        );
      },
      payload() {
        return items.map(({ menu_item_id, quantity, note }) => ({
          menu_item_id,
          quantity,
          note: note || '',
        }));
      },
      clear() {
        items.length = 0;
      },
    };
  }

  function renderCart(container, cart, onChange) {
    if (!container) return;
    if (!cart.items.length) {
      container.innerHTML = '<p class="text-muted small mb-0">Корзина пуста</p>';
      return;
    }
    container.innerHTML = cart.items
      .map(
        (r) => `
      <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
        <div>
          <div class="fw-semibold">${r.name}</div>
          <small class="text-muted">${r.price} сом × ${r.quantity} ${r.unit}</small>
        </div>
        <div class="d-flex align-items-center gap-1">
          <input type="number" class="form-control form-control-sm cart-qty" style="width:4.5rem"
            min="0.001" step="0.001" value="${r.quantity}" data-id="${r.menu_item_id}">
          <button type="button" class="btn btn-sm btn-outline-danger cart-remove" data-id="${r.menu_item_id}">×</button>
        </div>
      </div>`
      )
      .join('');
    container.querySelectorAll('.cart-qty').forEach((input) => {
      input.addEventListener('change', () => {
        const row = cart.items.find(
          (r) => r.menu_item_id === Number(input.dataset.id)
        );
        if (row) row.quantity = input.value;
        onChange && onChange();
      });
    });
    container.querySelectorAll('.cart-remove').forEach((btn) => {
      btn.addEventListener('click', () => {
        cart.remove(Number(btn.dataset.id));
        onChange && onChange();
      });
    });
  }

  async function fetchMenu(url) {
    const resp = await fetch(url, { headers: { Accept: 'application/json' } });
    const data = await resp.json();
    return data.categories || [];
  }

  async function postJSON(url, payload) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Ошибка запроса');
    return data;
  }

  return { mountMenu, createCart, renderCart, fetchMenu, postJSON, csrfToken };
})();
