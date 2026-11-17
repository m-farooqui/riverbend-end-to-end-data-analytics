let products = [
  { id: "RB-101", name: "Hudson Valley Lager", category: "Beer", style: "Crisp lager", price: 13.99, size: "6 pack", color: "#315b3b", badge: "Local", description: "Clean, bright, and brewed for relaxed afternoons." },
  { id: "RB-102", name: "North Country IPA", category: "Beer", style: "Hazy IPA", price: 15.99, size: "4 pack", color: "#b95035", badge: "Popular", description: "Juicy citrus notes with a smooth, balanced finish." },
  { id: "RB-201", name: "Finger Lakes Riesling", category: "Wine", style: "Semi-dry white", price: 18.5, size: "750 ml", color: "#d2a743", badge: "Staff pick", description: "Fresh stone fruit, bright acidity, and a clean finish." },
  { id: "RB-202", name: "Catskill Cabernet", category: "Wine", style: "Dry red", price: 24.0, size: "750 ml", color: "#71343b", badge: "New", description: "Dark fruit, gentle oak, and a long dinner-friendly finish." },
  { id: "RB-301", name: "Albany Small Batch Gin", category: "Spirits", style: "Botanical gin", price: 31.99, size: "750 ml", color: "#446d6c", badge: "Small batch", description: "Juniper, citrus peel, and a subtle herbal character." },
  { id: "RB-401", name: "Orchard Sparkler", category: "Nonalcoholic", style: "Sparkling apple", price: 8.99, size: "4 pack", color: "#c4772f", badge: "0.0%", description: "A lively alcohol-free option with crisp orchard flavor." }
];

const state = {
  cart: JSON.parse(localStorage.getItem("riverbend_cart") || "[]"),
  events: JSON.parse(localStorage.getItem("riverbend_events") || "[]"),
  category: "All",
  search: "",
  promo: null
};

const $ = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
const makeId = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7).toUpperCase()}`;

function recordEvent(eventType, details = {}) {
  const eventRecord = {
    event_id: makeId("EVT"),
    session_id: sessionStorage.getItem("riverbend_session"),
    event_type: eventType,
    event_timestamp: new Date().toISOString(),
    channel: "online_store",
    ...details
  };
  state.events.push(eventRecord);
  localStorage.setItem("riverbend_events", JSON.stringify(state.events));
  updateEventCount();
  fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eventRecord)
  }).catch(() => null);
}

async function loadProducts() {
  try {
    const response = await fetch("/api/products");
    if (!response.ok) return;
    const apiProducts = await response.json();
    if (apiProducts.length) products = apiProducts;
  } catch (_) {
    // The static hosted demo uses the built-in catalog when the API is unavailable.
  }
}

function saveCart() {
  localStorage.setItem("riverbend_cart", JSON.stringify(state.cart));
  renderCart();
}

function initializeSession() {
  if (!sessionStorage.getItem("riverbend_session")) {
    sessionStorage.setItem("riverbend_session", makeId("SES"));
    recordEvent("session_started", { referrer: document.referrer || "direct" });
  }
}

function renderFilters() {
  const categories = ["All", ...new Set(products.map(product => product.category))];
  $("#categoryFilters").innerHTML = categories.map(category =>
    `<button class="filter-button ${state.category === category ? "active" : ""}" data-category="${category}">${category}</button>`
  ).join("");
}

function renderProducts() {
  const filtered = products.filter(product => {
    const categoryMatch = state.category === "All" || product.category === state.category;
    const searchMatch = `${product.name} ${product.category} ${product.style}`.toLowerCase().includes(state.search.toLowerCase());
    return categoryMatch && searchMatch;
  });

  $("#productGrid").innerHTML = filtered.length ? filtered.map(product => `
    <article class="product-card" data-product-id="${product.id}">
      <div class="product-visual"><small>${product.badge}</small><span style="background:${product.color}">R</span></div>
      <div class="product-details">
        <div class="product-meta"><span>${product.category}</span><span>${product.size}</span></div>
        <h3>${product.name}</h3>
        <p>${product.description}</p>
        <div class="product-footer"><span class="product-price">${money(product.price)}</span><button class="button button-primary add-button" data-id="${product.id}">Add to cart</button></div>
      </div>
    </article>
  `).join("") : `<p>No products match your search.</p>`;
}

function addToCart(productId) {
  const existing = state.cart.find(item => item.productId === productId);
  if (existing) existing.quantity += 1;
  else state.cart.push({ productId, quantity: 1 });
  const product = products.find(item => item.id === productId);
  recordEvent("add_to_cart", { product_id: productId, product_name: product.name, unit_price: product.price });
  saveCart();
  openCart();
}

function changeQuantity(productId, amount) {
  const item = state.cart.find(cartItem => cartItem.productId === productId);
  if (!item) return;
  item.quantity += amount;
  recordEvent(amount > 0 ? "cart_quantity_increased" : "cart_quantity_decreased", { product_id: productId, quantity: Math.max(item.quantity, 0) });
  state.cart = state.cart.filter(cartItem => cartItem.quantity > 0);
  saveCart();
}

function calculateTotal() {
  const subtotal = state.cart.reduce((sum, item) => {
    const product = products.find(entry => entry.id === item.productId);
    return sum + product.price * item.quantity;
  }, 0);
  return state.promo === "SUMMER10" ? subtotal * .9 : subtotal;
}

function renderCart() {
  const count = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  $("#cartCount").textContent = count;
  $("#cartTotal").textContent = money(calculateTotal());
  $("#checkoutButton").disabled = count === 0;
  $("#cartItems").innerHTML = count ? state.cart.map(item => {
    const product = products.find(entry => entry.id === item.productId);
    return `<div class="cart-item">
      <span class="cart-swatch" style="background:${product.color}"></span>
      <div><h4>${product.name}</h4><small>${money(product.price)} each</small></div>
      <div class="quantity-controls"><button data-action="decrease" data-id="${product.id}">−</button><span>${item.quantity}</span><button data-action="increase" data-id="${product.id}">+</button></div>
    </div>`;
  }).join("") : `<div class="empty-cart">Your cart is empty.<br>Add a product to begin a demo transaction.</div>`;
}

function openCart() {
  $("#cartDrawer").classList.add("open");
  $("#cartDrawer").setAttribute("aria-hidden", "false");
  $("#drawerOverlay").classList.add("open");
}

function closeCart() {
  $("#cartDrawer").classList.remove("open");
  $("#cartDrawer").setAttribute("aria-hidden", "true");
  $("#drawerOverlay").classList.remove("open");
}

function updateEventCount() {
  $("#eventCount").textContent = `${state.events.length} event${state.events.length === 1 ? "" : "s"} recorded`;
}

function downloadEvents() {
  const payload = {
    source_system: "riverbend_online_store",
    exported_at: new Date().toISOString(),
    events: state.events
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `riverbend-online-events-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
  recordEvent("event_exported", { exported_event_count: state.events.length });
}

async function completeOrder(form) {
  const data = new FormData(form);
  const orderId = makeId("ORD");
  const orderTotal = calculateTotal();
  const orderItems = state.cart.map(item => {
    const product = products.find(entry => entry.id === item.productId);
    return { product_id: product.id, product_name: product.name, quantity: item.quantity, unit_price: product.price };
  });

  recordEvent("age_verified", { verification_method: "customer_attestation", result: "passed" });
  recordEvent("order_completed", {
    order_id: orderId,
    customer_name: data.get("name"),
    customer_email: data.get("email"),
    fulfillment_method: data.get("fulfillment"),
    store: data.get("store"),
    loyalty_enrollment: data.get("loyalty") === "on",
    promotion_code: state.promo,
    order_total: Number(orderTotal.toFixed(2)),
    order_items: orderItems
  });

  try {
    await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        order_id: orderId,
        customer_name: data.get("name"),
        customer_email: data.get("email"),
        fulfillment_method: data.get("fulfillment"),
        store: data.get("store"),
        loyalty_enrollment: data.get("loyalty") === "on",
        promotion_code: state.promo,
        order_total: Number(orderTotal.toFixed(2)),
        order_items: orderItems
      })
    });
  } catch (_) {
    // The browser event remains available for export if the API is offline.
  }

  state.cart = [];
  state.promo = null;
  saveCart();
  form.reset();
  $("#checkoutDialog").close();
  closeCart();
  $("#successMessage").textContent = `Demo order ${orderId} was recorded for ${money(orderTotal)}. You can export it from the Demo Data section.`;
  $("#successDialog").showModal();
}

document.addEventListener("click", event => {
  const addButton = event.target.closest(".add-button");
  const filterButton = event.target.closest(".filter-button");
  const quantityButton = event.target.closest(".quantity-controls button");
  const productCard = event.target.closest(".product-card");

  if (addButton) addToCart(addButton.dataset.id);
  else if (filterButton) {
    state.category = filterButton.dataset.category;
    recordEvent("category_filtered", { category: state.category });
    renderFilters();
    renderProducts();
  } else if (quantityButton) {
    changeQuantity(quantityButton.dataset.id, quantityButton.dataset.action === "increase" ? 1 : -1);
  } else if (productCard) {
    const product = products.find(item => item.id === productCard.dataset.productId);
    recordEvent("product_viewed", { product_id: product.id, product_name: product.name, category: product.category });
  }
});

$("#searchInput").addEventListener("input", event => {
  state.search = event.target.value;
  renderProducts();
});
$("#searchInput").addEventListener("change", event => recordEvent("product_searched", { search_term: event.target.value }));
$("#cartButton").addEventListener("click", openCart);
$("#closeCart").addEventListener("click", closeCart);
$("#drawerOverlay").addEventListener("click", closeCart);
$("#ageYes").addEventListener("click", () => {
  $("#ageGate").classList.add("hidden");
  recordEvent("age_gate_passed", { response: "21_or_older" });
});
$("#ageNo").addEventListener("click", () => {
  recordEvent("age_gate_failed", { response: "under_21" });
  $(".age-card").innerHTML = `<span class="eyebrow">Access unavailable</span><h1>Thanks for being honest</h1><p>You must be 21 or older to enter this demonstration store.</p>`;
});
$("#applyPromo").addEventListener("click", () => {
  const code = $("#promoInput").value.trim().toUpperCase();
  const accepted = code === "SUMMER10";
  state.promo = accepted ? code : null;
  $("#promoMessage").textContent = accepted ? "SUMMER10 applied: 10% off the demo order." : "Promotion code not recognized. Try SUMMER10.";
  recordEvent("promotion_attempted", { promotion_code: code, accepted });
  renderCart();
});
$("#checkoutButton").addEventListener("click", () => {
  if (!state.cart.length) return;
  recordEvent("checkout_started", { cart_item_count: state.cart.reduce((sum, item) => sum + item.quantity, 0), cart_total: calculateTotal() });
  $("#checkoutDialog").showModal();
});
$("#closeCheckout").addEventListener("click", () => $("#checkoutDialog").close());
$("#checkoutForm").addEventListener("submit", event => {
  event.preventDefault();
  if (event.currentTarget.reportValidity()) completeOrder(event.currentTarget);
});
$("#closeSuccess").addEventListener("click", () => $("#successDialog").close());
$("#downloadEvents").addEventListener("click", downloadEvents);
$("#clearEvents").addEventListener("click", () => {
  state.events = [];
  localStorage.removeItem("riverbend_events");
  updateEventCount();
});

async function startStore() {
  initializeSession();
  await loadProducts();
  renderFilters();
  renderProducts();
  renderCart();
  updateEventCount();
}

startStore();
