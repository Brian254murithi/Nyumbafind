/* ==========================================================================
   NyumbaFind — frontend application (vanilla JS + fetch)
   ========================================================================== */

"use strict";

/* ---------- Configuration ----------
   Override the API base by defining window.NYUMBAFIND_API_BASE
   before loading this script, e.g. in a <script> tag:
       window.NYUMBAFIND_API_BASE = "https://api.example.com/api";
   No credentials or secrets belong in this file. */
const API_BASE = (window.NYUMBAFIND_API_BASE || "").replace(/\/$/, "");

const TOKEN_KEY = "nf_token";
const USER_KEY = "nf_user";

const COUNTY_LIST = [
  "Nairobi", "Mombasa", "Nakuru", "Kiambu", "Kisumu", "Machakos",
  "Kajiado", "Uasin Gishu", "Kericho", "Meru", "Murang'a", "Nyeri",
  "Kakamega", "Bungoma", "Siaya", "Kisii", "Busia", "Bomet",
  "Nandi", "Nyandarua", "Tharaka-Nithi", "Embu", "Kitui",
  "Taita-Taveta", "Lamu", "Kilifi", "Kwale", "Tana River",
  "Garissa", "Wajir", "Mandera", "Marsabit", "Isiolo",
  "Samburu", "Trans Nzoia", "Elgeyo-Marakwet", "West Pokot",
  "Turkana", "Laikipia", "Homabay", "Migori", "Nyamira", "Narok",
];

const PROPERTY_TYPES = {
  apartment: "Apartment",
  bedsitter: "Bedsitter",
  studio: "Studio",
  house: "House",
  maisonette: "Maisonette",
  duplex: "Duplex",
  townhouse: "Townhouse",
  bungalow: "Bungalow",
  condo: "Condominium",
};

const LOCATIONS = [
  { name: "Nairobi", county: "Nairobi", blurb: "Apartments, bedsitters & family homes", img: "photo-1545324418-cc1a3fa10c00", alt: "Nairobi apartment buildings" },
  { name: "Westlands", county: "Nairobi", blurb: "Modern apartments & condos", img: "photo-1486406146926-c627a92ad1ab", alt: "Westlands high-rise apartments" },
  { name: "Kiambu", county: "Kiambu", blurb: "Ruiru, Ruaka & Thika rentals", img: "photo-1600585154340-be6161a56a0c", alt: "House in Kiambu" },
  { name: "Mombasa", county: "Mombasa", blurb: "Nyali beachfront living", img: "photo-1512917774080-9991f1c4c750", alt: "Coastal home in Mombasa" },
  { name: "Nakuru", county: "Nakuru", blurb: "Spacious family homes", img: "photo-1480074568708-e7b720bb3f09", alt: "Family house in Nakuru" },
  { name: "Kisumu", county: "Kisumu", blurb: "Lakeside apartments & houses", img: "photo-1568605114967-8130f3a36994", alt: "Rental home in Kisumu" },
];

/* ---------- Utilities ---------- */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const escHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

const formatKSh = (amount) =>
  "KSh " + Number(amount || 0).toLocaleString("en-KE");

const debounce = (fn, ms = 300) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
};

/* Global image fallback: replaces a broken <img> with a styled placeholder. */
function nfImgFallback(img, label) {
  if (!img || img.dataset.fallbackDone) return;
  img.dataset.fallbackDone = "1";
  const placeholder = document.createElement("div");
  placeholder.className = "img-fallback";
  placeholder.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
    '<path d="M3 11.5 12 4l9 7.5v7a2 2 0 0 1-2 2h-4v-6h-6v6H5a2 2 0 0 1-2-2z"/></svg>' +
    `<span>${escHtml(label || "Image unavailable")}</span>`;
  img.replaceWith(placeholder);
}

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- API client ---------- */
async function api(path, { method = "GET", body, form, token } = {}) {
  const headers = {};
  const storedToken = token ?? localStorage.getItem(TOKEN_KEY);
  if (storedToken) headers.Authorization = `Token ${storedToken}`;

  let payload;
  if (form) {
    payload = form; // FormData — browser sets multipart boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });

  // 204 No Content
  if (response.status === 204) return { ok: true, status: response.status, data: null };

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  return { ok: response.ok, status: response.status, data };
}

const getToken = () => localStorage.getItem(TOKEN_KEY);
const getCurrentUser = () => {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
};

/* ---------- Toast notifications ---------- */
function toast(message, type = "info", ms = 3200) {
  const container = $("#toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icon =
    type === "success"
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 13 4 4L19 7"/></svg>'
      : type === "error"
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 6l12 12M18 6 6 18"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4m0 4h.01"/></svg>';
  el.innerHTML = `${icon}<span>${escHtml(message)}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add("out");
    el.addEventListener("animationend", () => el.remove(), { once: true });
  }, ms);
}

/* ---------- Star rendering ---------- */
function starsHtml(rating, size = "") {
  const pct = Math.max(0, Math.min(100, (Number(rating) || 0) / 5 * 100));
  return (
    `<span class="stars ${size}" role="img" aria-label="${Number(rating).toFixed(1)} out of 5 stars">` +
    '<span class="stars-base">★★★★★</span>' +
    `<span class="stars-fill" style="width:${pct}%">★★★★★</span>` +
    "</span>"
  );
}

/* ---------- Skeletons ---------- */
function skeletonCards(count = 6, target) {
  target.innerHTML = Array.from({ length: count }, () => `
    <div class="skeleton-card" aria-hidden="true">
      <div class="skeleton skeleton-media"></div>
      <div class="skeleton-body">
        <div class="skeleton skeleton-line w80"></div>
        <div class="skeleton skeleton-line w60"></div>
        <div class="skeleton skeleton-line w40"></div>
      </div>
    </div>`).join("");
}

/* ---------- Property cards ---------- */
function propertyCardHtml(p, index = 0) {
  const delay = Math.min(index, 5) * 0.07;
  const img = p.main_image_url || (p.images && p.images[0] && p.images[0].image_url);
  const rating = p.rating || {};
  const avg = Number(rating.average_rating || 0);
  const beds = p.property_type === "bedsitter" || p.property_type === "studio"
    ? "Bedsitter"
    : `${p.bedrooms} bd`;
  const location = [p.estate, p.town, p.county].filter(Boolean).join(" · ");

  return `
  <article class="property-card" style="transition-delay:${delay}s" data-property-id="${p.id}" tabindex="0" role="button"
           aria-label="View ${escHtml(p.title)}">
    <div class="card-media">
      ${img
        ? `<img src="${escHtml(img)}" alt="${escHtml(p.title)}" loading="lazy"
               onerror="nfImgFallback(this, '${escHtml(p.title)}')" />`
        : `<div class="img-fallback"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 11.5 12 4l9 7.5v7a2 2 0 0 1-2 2h-4v-6h-6v6H5a2 2 0 0 1-2-2z"/></svg><span>No photo yet</span></div>`}
      <span class="card-badge type">${escHtml(PROPERTY_TYPES[p.property_type] || p.property_type)}</span>
      ${p.is_sample ? '<span class="card-badge sample">Sample</span>' : ""}
      ${p.available ? `<span class="card-badge rent-badge">${formatKSh(p.rent)}</span>` : '<span class="card-badge unavailable">Unavailable</span>'}
    </div>
    <div class="card-body">
      <h3 class="card-title">${escHtml(p.title)}</h3>
      <p class="card-location">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>
        <span>${escHtml(location || p.county)}</span>
      </p>
      <div class="card-meta">
        <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6"/><path d="M3 18h18M6 10V7a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v3"/></svg>${beds}</span>
        <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12h16v2a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M6 12V5a2 2 0 0 1 4 0"/></svg>${p.bathrooms} ba</span>
        <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg>${p.bedrooms === 0 ? "Studio" : `${p.bedrooms} bed`}</span>
      </div>
      <div class="card-foot">
        <span class="card-price">${formatKSh(p.rent)}<small>/month</small></span>
        ${rating.review_count
          ? `<span class="rating-mini"><svg viewBox="0 0 24 24" fill="currentColor"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>${avg.toFixed(1)} (${rating.review_count})</span>`
          : '<span class="rating-mini" style="color:var(--color-gray-500)">Not yet reviewed</span>'}
      </div>
    </div>
  </article>`;
}

function renderCards(target, properties, emptyMessage) {
  if (!properties.length) {
    target.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;text-align:center;padding:3rem 1rem;color:var(--color-gray-500)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:52px;height:52px;margin:0 auto 1rem;opacity:.4"><path d="M3 11.5 12 4l9 7.5v7a2 2 0 0 1-2 2h-4v-6h-6v6H5a2 2 0 0 1-2-2z"/></svg>
        <p style="font-size:1.05rem;font-weight:600;color:var(--color-gray-700)">No properties found</p>
        <p>${escHtml(emptyMessage || "Try adjusting your filters or search a different location.")}</p>
      </div>`;
    return;
  }
  target.innerHTML = properties.map((p, i) => propertyCardHtml(p, i)).join("");
  observeCards(target);
}

/* Intersection Observer: staggered card entrances */
let cardObserver;
function observeCards(root = document) {
  if (!cardObserver && !reduceMotion) {
    cardObserver = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          cardObserver.unobserve(entry.target);
        }
      }),
      { threshold: 0.08, rootMargin: "0px 0px -30px 0px" }
    );
  }
  $$(".property-card:not(.in-view)", root).forEach((card) => {
    if (reduceMotion) card.classList.add("in-view");
    else cardObserver.observe(card);
  });
}

/* Subtle 3D tilt for featured cards (desktop only) */
function attachTilt(root = document) {
  if (reduceMotion || window.matchMedia("(pointer: coarse)").matches) return;
  $$(".property-card", root).forEach((card) => {
    card.classList.add("tilt");
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.setProperty("--ry", `${x * 5}deg`);
      card.style.setProperty("--rx", `${-y * 5}deg`);
    });
    card.addEventListener("mouseleave", () => {
      card.style.setProperty("--rx", "0deg");
      card.style.setProperty("--ry", "0deg");
    });
  });
}

/* ---------- Section loaders ---------- */
async function loadFeatured() {
  const grid = $("#featuredGrid");
  skeletonCards(4, grid);
  const { ok, data } = await api("/api/properties/?featured=true&page_size=8");
  if (ok && data) {
    renderCards(grid, data.results || [], "No featured listings right now.");
    attachTilt(grid);
  } else {
    grid.innerHTML = '<p class="empty-note" style="color:var(--color-gray-500)">Could not load featured properties. Please refresh.</p>';
  }
}

async function loadRecent() {
  const grid = $("#recentGrid");
  skeletonCards(4, grid);
  const { ok, data } = await api("/api/properties/?sort=newest&page_size=8");
  if (ok && data) renderCards(grid, data.results || []);
  else grid.innerHTML = '<p style="color:var(--color-gray-500)">Could not load recent listings.</p>';
}

async function loadLocations() {
  const grid = $("#locationGrid");
  grid.innerHTML = LOCATIONS.map((loc, i) => `
    <button class="location-card reveal" style="transition-delay:${i * 0.07}s"
            data-county="${escHtml(loc.county)}" data-name="${escHtml(loc.name)}"
            aria-label="Search rentals in ${escHtml(loc.name)}">
      <img src="https://images.unsplash.com/${loc.img}?auto=format&fit=crop&w=640&q=80"
           alt="${escHtml(loc.alt)}" loading="lazy"
           onerror="nfImgFallback(this, '${escHtml(loc.name)}')" />
      <span class="go-arrow" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14m-6-6 6 6-6 6"/></svg>
      </span>
      <span class="location-info">
        <strong>${escHtml(loc.name)}</strong>
        <span>${escHtml(loc.blurb)}</span>
      </span>
    </button>`).join("");

  $$(".location-card", grid).forEach((card) => {
    card.addEventListener("click", () => {
      const county = card.dataset.county;
      const name = card.dataset.name;
      setExploreFilter({ county, q: "" });
      document.getElementById("explore").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      toast(`Showing rentals in ${name}`, "info");
    });
  });

  // The cards carry the .reveal class, but they are
  // injected after initReveal() ran — register them
  // with the reveal observer so they become visible.
  observeReveals(grid);
}

/* ---------- Explore (search & filters) ---------- */
const exploreState = {
  county: "", town: "", q: "", property_type: "",
  min_rent: "", max_rent: "", bedrooms: "",
  available: false, sort: "newest", page: 1,
};

function exploreQueryParams() {
  const p = new URLSearchParams();
  if (exploreState.county) p.set("county", exploreState.county);
  if (exploreState.town) p.set("town", exploreState.town);
  if (exploreState.q) p.set("q", exploreState.q);
  if (exploreState.property_type) p.set("property_type", exploreState.property_type);
  if (exploreState.min_rent) p.set("min_rent", exploreState.min_rent);
  if (exploreState.max_rent) p.set("max_rent", exploreState.max_rent);
  if (exploreState.bedrooms !== "") p.set("bedrooms", exploreState.bedrooms);
  if (exploreState.available) p.set("available", "true");
  if (exploreState.sort) p.set("sort", exploreState.sort);
  p.set("page", exploreState.page);
  p.set("page_size", "9");
  return p.toString();
}

async function loadExplore() {
  const grid = $("#exploreGrid");
  const count = $("#resultsCount");
  const pagination = $("#explorePagination");
  skeletonCards(6, grid);
  count.textContent = "Searching…";
  pagination.innerHTML = "";

  const { ok, data } = await api(`/api/properties/?${exploreQueryParams()}`);
  if (!ok || !data) {
    count.textContent = "";
    renderCards(grid, [], "Something went wrong while loading listings.");
    return;
  }

  const results = data.results || [];
  count.textContent = `${data.count} listing${data.count === 1 ? "" : "s"} found`;
  renderCards(grid, results);

  // Pagination
  const totalPages = Math.ceil(data.count / 9) || 1;
  const page = exploreState.page;
  let buttons = "";
  buttons += `<button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""} aria-label="Previous page">‹</button>`;
  const windowPages = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || Math.abs(i - page) <= 2) windowPages.push(i);
  }
  let last = 0;
  windowPages.forEach((i) => {
    if (i - last > 1) buttons += `<span class="page-btn" style="border:none;cursor:default">…</span>`;
    buttons += `<button class="page-btn ${i === page ? "active" : ""}" data-page="${i}" ${i === page ? 'aria-current="page"' : ""}>${i}</button>`;
    last = i;
  });
  buttons += `<button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""} aria-label="Next page">›</button>`;
  pagination.innerHTML = buttons;

  $$(".page-btn[data-page]", pagination).forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = Number(btn.dataset.page);
      if (next >= 1 && next <= totalPages) {
        exploreState.page = next;
        loadExplore();
        document.getElementById("explore").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      }
    });
  });
}

function setExploreFilter(patch) {
  Object.assign(exploreState, patch, { page: 1 });
  syncFilterInputs();
  loadExplore();
}

function syncFilterInputs() {
  $("#filterCounty").value = exploreState.county;
  $("#filterType").value = exploreState.property_type;
  $("#filterMinRent").value = exploreState.min_rent;
  $("#filterMaxRent").value = exploreState.max_rent;
  $("#filterBeds").value = exploreState.bedrooms;
  $("#filterSort").value = exploreState.sort;
  $("#filterAvailable").checked = exploreState.available;
}

function initExploreFilters() {
  const map = {
    filterCounty: "county", filterType: "property_type",
    filterMinRent: "min_rent", filterMaxRent: "max_rent",
    filterBeds: "bedrooms", filterSort: "sort",
  };
  Object.entries(map).forEach(([id, key]) => {
    $(`#${id}`).addEventListener("change", (e) => {
      exploreState[key] = e.target.value;
      exploreState.page = 1;
      loadExplore();
    });
  });
  $("#filterAvailable").addEventListener("change", (e) => {
    exploreState.available = e.target.checked;
    exploreState.page = 1;
    loadExplore();
  });
  $("#filterClear").addEventListener("click", () => {
    Object.assign(exploreState, {
      county: "", town: "", q: "", property_type: "",
      min_rent: "", max_rent: "", bedrooms: "",
      available: false, sort: "newest", page: 1,
    });
    $("#searchLocation").value = "";
    $("#searchCounty").value = "";
    $("#searchType").value = "";
    $("#searchBeds").value = "";
    $("#searchMaxRent").value = "";
    syncFilterInputs();
    loadExplore();
  });

  // Hero search
  $("#searchForm").addEventListener("submit", (e) => {
    e.preventDefault();
    Object.assign(exploreState, {
      q: $("#searchLocation").value.trim(),
      county: $("#searchCounty").value,
      property_type: $("#searchType").value,
      bedrooms: $("#searchBeds").value,
      max_rent: $("#searchMaxRent").value,
      page: 1,
    });
    syncFilterInputs();
    loadExplore();
    document.getElementById("explore").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  });

  syncFilterInputs();
}

/* ---------- Reviews section ---------- */
async function loadReviewsSection() {
  // Global summary
  const { ok, data } = await api("/api/reviews/summary/");
  if (ok && data) {
    $("#globalAvg").textContent = data.average_rating.toFixed(1);
    $("#globalStars").innerHTML = starsHtml(data.average_rating);
    $("#globalCount").textContent = `${data.review_count} verified tenant reviews`;

    const dist = data.distribution || {};
    const max = Math.max(1, ...Object.values(dist).map(Number));
    $("#globalBars").innerHTML = [5, 4, 3, 2, 1].map((star) => {
      const value = Number(dist[String(star)] || 0);
      const pct = Math.round((value / max) * 100);
      return `
        <div class="rating-bar-row">
          <span>${star} ★</span>
          <div class="bar-track"><div class="bar-fill" data-width="${pct}%"></div></div>
          <span>${value}</span>
        </div>`;
    }).join("");

    const labels = {
      condition: "Condition", location: "Location", water: "Water reliability",
      security: "Security", value_for_money: "Value for money", landlord: "Landlord",
    };
    $("#globalCategories").innerHTML = Object.entries(labels).map(([key, label]) => {
      const value = Number(data.category_averages[key] || 0);
      const pct = Math.round((value / 5) * 100);
      return `
        <div class="category-row">
          <span class="cat-label">${label}</span>
          <div class="bar-track"><div class="bar-fill" data-width="${pct}%"></div></div>
          <span class="cat-value">${value.toFixed(1)}</span>
        </div>`;
    }).join("");
  }

  // Recent reviews
  const list = $("#reviewsList");
  const { ok: okReviews, data: reviewsData } = await api("/api/reviews/top/?page_size=6");
  if (okReviews && reviewsData) {
    list.innerHTML = (reviewsData.results || []).map(reviewHtml).join("") ||
      '<p style="color:var(--color-gray-500)">No reviews yet — be the first to share your experience.</p>';
  } else {
    list.innerHTML = '<p style="color:var(--color-gray-500)">Could not load reviews.</p>';
  }
}

function reviewHtml(r) {
  const initials = (r.tenant_name || "T").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  const avatar = r.avatar
    ? `<img src="${escHtml(r.avatar)}" alt="" loading="lazy" onerror="this.outerHTML='<span>${initials}</span>'" style="width:100%;height:100%;object-fit:cover" />`
    : initials;
  return `
  <article class="review-card">
    <div class="review-head">
      <span class="review-avatar">${avatar}</span>
      <div class="review-who">
        <strong>${escHtml(r.tenant_name)}${r.is_verified ? '<span class="verified-badge"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 13 4 4L19 7"/></svg>Verified tenant</span>' : ""}</strong>
        <small>${starsHtml(r.overall)} &nbsp;${new Date(r.created_at).toLocaleDateString("en-KE", { year: "numeric", month: "short", day: "numeric" })}</small>
      </div>
    </div>
    <p>${escHtml(r.comment)}</p>
    ${r.recommends === true ? '<p style="margin-top:.5rem;font-size:.85rem;color:var(--color-success);font-weight:600">✓ Would recommend</p>' : ""}
    <div class="review-prop">
      Review for <a href="#" data-open-property="${r.property?.id ?? r.property_id}">${escHtml(r.property?.title || "this property")}</a>
      · ${escHtml([r.property?.estate, r.property?.town, r.property?.county].filter(Boolean).join(", "))}
    </div>
    ${r.response ? `
      <div class="review-response">
        <strong>Response from ${escHtml(r.response.landlord_name)}</strong>
        ${escHtml(r.response.message)}
      </div>` : ""}
  </article>`;
}

/* ---------- Property detail modal ---------- */
let currentPropertyId = null;

async function openPropertyDetail(id) {
  currentPropertyId = id;
  const modal = $("#propertyModal");
  const body = $("#propertyModalBody");
  body.innerHTML = `
    <div class="pm-gallery"><div class="skeleton" style="aspect-ratio:16/10"></div></div>
    <div style="margin-top:1rem;display:flex;flex-direction:column;gap:.6rem">
      <div class="skeleton skeleton-line w80"></div>
      <div class="skeleton skeleton-line w60"></div>
      <div class="skeleton skeleton-line w40"></div>
    </div>`;
  openModal("propertyModal");

  const { ok, data: p } = await api(`/api/properties/${id}/`);
  if (!ok || !p) {
    body.innerHTML = '<p style="padding:2rem;text-align:center;color:var(--color-gray-500)">This listing is no longer available.</p>';
    return;
  }
  payState.propertiesById[p.id] = p;

  const images = p.images && p.images.length ? p.images : [];
  const mainSrc = p.main_image_url || (images[0] && images[0].image_url);
  const rating = p.rating || {};
  const galleryItems = mainSrc
    ? [{ url: mainSrc, alt: `${p.title} — main photo` }, ...images.filter((im) => im.image_url !== mainSrc).map((im) => ({ url: im.image_url, alt: im.alt_text || p.title }))]
    : images.map((im) => ({ url: im.image_url, alt: im.alt_text || p.title }));

  body.innerHTML = `
    <div class="pm-gallery">
      <div class="pm-main" id="pmMain">
        ${galleryItems.length
          ? `<img src="${escHtml(galleryItems[0].url)}" alt="${escHtml(galleryItems[0].alt)}" id="pmMainImg" onerror="nfImgFallback(this, '${escHtml(p.title)}')" />`
          : `<div class="img-fallback"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 11.5 12 4l9 7.5v7a2 2 0 0 1-2 2h-4v-6h-6v6H5a2 2 0 0 1-2-2z"/></svg><span>No photos yet</span></div>`}
      </div>
      ${galleryItems.length > 1 ? `
        <div class="pm-thumbs" role="tablist" aria-label="Property photos">
          ${galleryItems.map((g, i) => `
            <button class="pm-thumb ${i === 0 ? "active" : ""}" type="button" role="tab" aria-selected="${i === 0}" data-index="${i}">
              <img src="${escHtml(g.url)}" alt="${escHtml(g.alt)}" loading="lazy" onerror="nfImgFallback(this, 'Photo ${i + 1}')" />
            </button>`).join("")}
        </div>` : ""}
    </div>

    <div class="pm-head">
      <div>
        <h2 id="pmTitle">${escHtml(p.title)}</h2>
        <p class="pm-location">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>
          ${escHtml([p.estate, p.town, p.address, p.county].filter(Boolean).join(" · "))}
        </p>
      </div>
      <div class="pm-badges">
        <span class="card-badge type">${escHtml(PROPERTY_TYPES[p.property_type] || p.property_type)}</span>
        ${p.is_sample ? '<span class="card-badge sample">Sample listing</span>' : ""}
        ${p.available ? '<span class="card-badge" style="background:var(--color-success)">Available</span>' : '<span class="card-badge unavailable">Unavailable</span>'}
      </div>
    </div>

    <div style="display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap">
      <span class="pm-price">${formatKSh(p.rent)}<small> / month</small></span>
      ${rating.review_count
        ? `<span class="rating-mini">${starsHtml(rating.average_rating)} <strong>${Number(rating.average_rating).toFixed(1)}</strong> · ${rating.review_count} review${rating.review_count === 1 ? "" : "s"}</span>`
        : '<span class="rating-mini" style="color:var(--color-gray-500)">Not yet reviewed</span>'}
    </div>

    <div class="pm-meta">
      <div><strong>${p.property_type === "bedsitter" || p.property_type === "studio" ? "0" : p.bedrooms}</strong><span>Bedrooms</span></div>
      <div><strong>${p.bathrooms}</strong><span>Bathrooms</span></div>
      <div><strong>${escHtml(PROPERTY_TYPES[p.property_type] || p.property_type)}</strong><span>Type</span></div>
      <div><strong>${escHtml(p.owner_name || "—")}</strong><span>Listed by</span></div>
    </div>

    <div class="pm-section">
      <h3>About this home</h3>
      <p class="pm-desc">${escHtml(p.description)}</p>
    </div>

    ${p.amenities && p.amenities.length ? `
      <div class="pm-section">
        <h3>Amenities</h3>
        <div class="amenities">${p.amenities.map((a) => `<span class="amenity">${escHtml(a)}</span>`).join("")}</div>
      </div>` : ""}

    <div class="pm-section">
      <h3>Ratings breakdown</h3>
      <div class="pm-rating-grid">
        ${[
          ["Condition", rating.category_averages?.condition],
          ["Location", rating.category_averages?.location],
          ["Water reliability", rating.category_averages?.water],
          ["Security", rating.category_averages?.security],
          ["Value for money", rating.category_averages?.value_for_money],
          ["Landlord", rating.category_averages?.landlord],
        ].map(([label, value]) => `
          <div class="category-row">
            <span class="cat-label">${label}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${Math.round((Number(value) || 0) / 5 * 100)}%"></div></div>
            <span class="cat-value">${Number(value || 0).toFixed(1)}</span>
          </div>`).join("")}
      </div>
    </div>

    <div class="pm-section" id="pmReviews"></div>
    ${p.is_owner ? `<div class="pm-actions"><button class="btn btn-primary" id="pmEditBtn" type="button">Edit this listing</button></div>` : ""}
    ${paymentCtasHtml(p)}
  `;

  // Gallery thumbnail switching
  $$(".pm-thumb", body).forEach((thumb) => {
    thumb.addEventListener("click", () => {
      const idx = Number(thumb.dataset.index);
      const g = galleryItems[idx];
      const mainImg = $("#pmMainImg");
      if (mainImg) {
        mainImg.src = g.url;
        mainImg.alt = g.alt;
      }
      $$(".pm-thumb", body).forEach((t) => {
        t.classList.toggle("active", t === thumb);
        t.setAttribute("aria-selected", String(t === thumb));
      });
    });
  });

  $("#pmEditBtn")?.addEventListener("click", () => {
    closeModal("propertyModal");
    openDashboard({ editProperty: p });
  });

  loadPropertyReviews(p.id, $("#pmReviews"));
}

async function loadPropertyReviews(propertyId, container) {
  const user = getCurrentUser();
  const { ok, data } = await api(`/api/properties/${propertyId}/reviews/`);
  if (!ok || !data) {
    container.innerHTML = "<p>Could not load reviews.</p>";
    return;
  }

  const reviews = data.results || [];
  const summary = data.summary || {};

  container.innerHTML = `
    <h3>Tenant reviews <span style="color:var(--color-gray-500);font-weight:500;font-size:.9rem">(${summary.review_count || 0})</span></h3>
    <div class="reviews-list" style="margin-top:.8rem">
      ${reviews.length ? reviews.map(reviewHtml).join("") : '<p style="color:var(--color-gray-500)">No reviews yet — be the first to share your experience.</p>'}
    </div>
    <div id="pmReviewForm"></div>
  `;

  // Delegate clicks on "review for <property>" links inside this container
  container.addEventListener("click", (e) => {
    const link = e.target.closest("[data-open-property]");
    if (link) {
      e.preventDefault();
      const pid = Number(link.dataset.openProperty);
      if (pid && pid !== currentPropertyId) openPropertyDetail(pid);
    }
  });

  renderReviewForm(propertyId, $("#pmReviewForm"));
}

function starInputHtml(name, label) {
  return `
    <div class="star-row">
      <label id="${name}-label">${label}</label>
      <div class="star-input" role="radiogroup" aria-labelledby="${name}-label" data-field="${name}">
        ${[1, 2, 3, 4, 5].map((v) => `
          <button type="button" role="radio" aria-checked="false" aria-label="${v} star${v > 1 ? "s" : ""}" data-value="${v}">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>
          </button>`).join("")}
      </div>
    </div>`;
}

function renderReviewForm(propertyId, container) {
  const user = getCurrentUser();
  if (!user) {
    container.innerHTML = `
      <div class="review-form" style="text-align:center">
        <h3>Stayed here? Share your experience</h3>
        <p style="color:var(--color-gray-500);font-size:.9rem;margin-bottom:.8rem">Sign in to leave a verified tenant review.</p>
        <button class="btn btn-primary" id="reviewSignInBtn" type="button">Sign In to Review</button>
      </div>`;
    $("#reviewSignInBtn").addEventListener("click", () => openAuth("login"));
    return;
  }

  if (user.role === "landlord") {
    container.innerHTML = `<p style="color:var(--color-gray-500);font-size:.88rem;margin-top:.6rem">Landlords cannot review properties. Reviews are written by tenants.</p>`;
    return;
  }

  container.innerHTML = `
    <form class="review-form" id="reviewSubmitForm" novalidate>
      <h3>Leave a review</h3>
      <div class="form-error" id="reviewError" role="alert" hidden></div>
      ${starInputHtml("overall", "Overall")}
      ${starInputHtml("condition", "Property condition")}
      ${starInputHtml("location", "Location")}
      ${starInputHtml("water", "Water reliability")}
      ${starInputHtml("security", "Security")}
      ${starInputHtml("value_for_money", "Value for money")}
      ${starInputHtml("landlord_rating", "Landlord")}
      <label for="reviewComment" class="visually-hidden">Your review</label>
      <textarea id="reviewComment" placeholder="Tell other tenants about your experience — the good and the bad…" required></textarea>
      <label class="checkbox-label" style="margin-top:.6rem">
        <input type="checkbox" id="reviewRecommends" checked /> I would recommend this property
      </label>
      <button type="submit" class="btn btn-primary btn-block">Submit Review</button>
    </form>`;

  // Star input behaviour
  $$(".star-input", container).forEach((group) => {
    const buttons = $$("button", group);
    const paint = (value) => buttons.forEach((b) => {
      const lit = Number(b.dataset.value) <= value;
      b.classList.toggle("lit", lit);
      b.setAttribute("aria-checked", String(lit && Number(b.dataset.value) === value));
    });
    buttons.forEach((btn) => {
      btn.addEventListener("mouseenter", () => paint(Number(btn.dataset.value)));
      btn.addEventListener("click", () => paint(Number(btn.dataset.value)));
    });
    group.addEventListener("mouseleave", () => {
      const lit = buttons.filter((b) => b.classList.contains("lit")).length;
      paint(lit);
    });
  });

  $("#reviewSubmitForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = $("#reviewError");
    const payload = {};
    let valid = true;
    $$(".star-input", container).forEach((group) => {
      const lit = group.querySelectorAll("button.lit").length;
      if (!lit) valid = false;
      payload[group.dataset.field] = lit || null;
    });
    const comment = $("#reviewComment").value.trim();
    if (comment.length < 10) valid = false;

    if (!valid) {
      errorBox.textContent = "Please rate every category and write at least a 10-character comment.";
      errorBox.hidden = false;
      return;
    }

    payload.comment = comment;
    payload.recommends = $("#reviewRecommends").checked;

    const btn = $("#reviewSubmitForm .btn");
    btn.disabled = true;
    btn.textContent = "Submitting…";

    const res = await api(`/api/properties/${propertyId}/reviews/`, { method: "POST", body: payload });
    if (res.ok) {
      toast("Review submitted. Thank you!", "success");
      loadPropertyReviews(propertyId, container.closest("#pmReviews") || container);
      loadReviewsSection();
    } else {
      const msg = res.data?.errors?.detail || res.data?.errors?.comment?.[0] || "Could not submit your review.";
      errorBox.textContent = Array.isArray(msg) ? msg.join(" ") : msg;
      errorBox.hidden = false;
      btn.disabled = false;
      btn.textContent = "Submit Review";
    }
  });
}

/* ---------- Report a review ---------- */
async function reportReview(reviewId) {
  const reason = prompt("Why are you reporting this review?\nChoose: inaccurate, offensive, spam, suspicious, other");
  if (!reason) return;
  const description = prompt("Add a short description (optional):") || "";
  const res = await api(`/api/reviews/${reviewId}/report/`, {
    method: "POST",
    body: { reason: reason.trim().toLowerCase(), description },
  });
  if (res.ok) toast("Thanks — our moderation team will review this.", "success");
  else toast("Could not submit the report. Please try again.", "error");
}

/* ---------- Modals ---------- */
function openModal(id) {
  const modal = $(`#${id}`);
  modal.hidden = false;
  modal.classList.remove("closing");
  document.body.style.overflow = "hidden";
  const focusable = $("button, [href], input, select, textarea", modal);
  if (focusable) focusable.focus();
}

function closeModal(id) {
  const modal = $(`#${id}`);
  modal.classList.add("closing");
  document.body.style.overflow = "";
  if (id === "paymentModal" && typeof stopPolling === "function") {
    stopPolling();
  }
  setTimeout(() => {
    modal.hidden = true;
    modal.classList.remove("closing");
  }, reduceMotion ? 0 : 220);
}

function initModals() {
  $$("[data-close]").forEach((el) => {
    el.addEventListener("click", () => closeModal(el.dataset.close));
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      $$(".modal:not([hidden])").forEach((m) => closeModal(m.id));
      if (!$("#chatPanel").hidden) toggleChat(false);
    }
  });
}

/* ---------- Auth ---------- */
function openAuth(tab = "login") {
  $("#authModal").hidden = false;
  setAuthTab(tab);
  document.body.style.overflow = "hidden";
}

function setAuthTab(tab) {
  const isLogin = tab === "login";
  $("#tabLogin").classList.toggle("active", isLogin);
  $("#tabRegister").classList.toggle("active", !isLogin);
  $("#tabLogin").setAttribute("aria-selected", String(isLogin));
  $("#tabRegister").setAttribute("aria-selected", String(!isLogin));
  $("#loginForm").hidden = !isLogin;
  $("#registerForm").hidden = isLogin;
  $("#loginError").hidden = true;
  $("#registerError").hidden = true;
}

function updateAuthUI() {
  const user = getCurrentUser();
  const token = getToken();
  const loggedIn = Boolean(user && token);
  $("#navLoginBtn").style.display = loggedIn ? "none" : "";
  $("#navRegisterBtn").style.display = loggedIn ? "none" : "";
  $("#navUser").hidden = !loggedIn;
  if (loggedIn) {
    $("#navUserName").textContent = user.first_name || user.username;
    const isLandlord = user.role === "landlord" || user.role === "admin";
    $("#navDashboardBtn").style.display = isLandlord ? "" : "none";
    $("#ctaDashboardBtn").style.display = isLandlord ? "" : "none";
  }
}

async function loadMe() {
  const token = getToken();
  if (!token) { updateAuthUI(); return; }
  const { ok, data } = await api("/api/auth/me/");
  if (ok && data) {
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  } else {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
  updateAuthUI();
}

function initAuth() {
  $("#navLoginBtn").addEventListener("click", () => openAuth("login"));
  $("#navRegisterBtn").addEventListener("click", () => openAuth("register"));
  $("#heroListBtn").addEventListener("click", () => openAuth("register"));
  $("#ctaListBtn").addEventListener("click", () => openAuth("register"));
  $("#ctaDashboardBtn").addEventListener("click", () => openDashboard());
  $("#navDashboardBtn").addEventListener("click", () => openDashboard());
  $("#navLogoutBtn").addEventListener("click", logout);
  $("#tabLogin").addEventListener("click", () => setAuthTab("login"));
  $("#tabRegister").addEventListener("click", () => setAuthTab("register"));

  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = $("#loginError");
    errorBox.hidden = true;
    const btn = $("#loginSubmit");
    btn.disabled = true;
    btn.textContent = "Signing in…";
    const res = await api("/api/auth/login/", {
      method: "POST",
      body: {
        username: $("#loginUsername").value.trim(),
        password: $("#loginPassword").value,
      },
    });
    btn.disabled = false;
    btn.textContent = "Sign In";
    if (res.ok) {
      localStorage.setItem(TOKEN_KEY, res.data.token);
      localStorage.setItem(USER_KEY, JSON.stringify(res.data.user));
      updateAuthUI();
      closeModal("authModal");
      toast(`Welcome back, ${res.data.user.first_name || res.data.user.username}!`, "success");
    } else {
      errorBox.textContent = res.data?.errors?.detail || "Sign-in failed. Check your credentials.";
      errorBox.hidden = false;
    }
  });

  $("#registerForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = $("#registerError");
    errorBox.hidden = true;
    const btn = $("#registerSubmit");
    btn.disabled = true;
    btn.textContent = "Creating account…";
    const res = await api("/api/auth/register/", {
      method: "POST",
      body: {
        username: $("#regUsername").value.trim(),
        email: $("#regEmail").value.trim(),
        password: $("#regPassword").value,
        first_name: $("#regFirst").value.trim(),
        last_name: $("#regLast").value.trim(),
        role: $("#regRole").value,
      },
    });
    btn.disabled = false;
    btn.textContent = "Create Account";
    if (res.ok) {
      localStorage.setItem(TOKEN_KEY, res.data.token);
      localStorage.setItem(USER_KEY, JSON.stringify(res.data.user));
      updateAuthUI();
      closeModal("authModal");
      toast(res.data.user.role === "landlord"
        ? "Landlord account created — open your dashboard to list a property!"
        : "Account created. Welcome to NyumbaFind!", "success");
      if (res.data.user.role === "landlord") openDashboard();
    } else {
      const errors = res.data?.errors || {};
      const messages = Object.values(errors).flat();
      errorBox.innerHTML = messages.length
        ? `<ul>${messages.map((m) => `<li>${escHtml(m)}</li>`).join("")}</ul>`
        : "Registration failed. Please check your details.";
      errorBox.hidden = false;
    }
  });
}

async function logout() {
  const token = getToken();
  if (token) {
    await api("/api/auth/logout/", { method: "POST" }); // best-effort server-side invalidation
  }
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  updateAuthUI();
  toast("You've been signed out.", "info");
}

/* ---------- Landlord dashboard ---------- */
let editingProperty = null;

async function openDashboard(options = {}) {
  const user = getCurrentUser();
  if (!user || !getToken()) {
    openAuth("register");
    return;
  }
  if (user.role !== "landlord" && user.role !== "admin") {
    toast("The dashboard is for landlords. Register as a landlord to list properties.", "error");
    return;
  }

  const modal = $("#dashboardModal");
  const body = $("#dashboardBody");
  body.innerHTML = `
    <div class="dash-stats">
      ${Array.from({ length: 5 }, () => `
        <div class="dash-stat"><div class="skeleton skeleton-line w40"></div><div class="skeleton skeleton-line w60" style="height:22px;margin-top:.5rem"></div></div>`).join("")}
    </div>
    <div class="skeleton" style="height:220px;border-radius:12px"></div>`;
  openModal("dashboardModal");

  if (options.editProperty) {
    editingProperty = options.editProperty;
    renderListingForm(body, options.editProperty);
    return;
  }

  const { ok, data } = await api("/api/landlord/dashboard/");
  if (!ok || !data) {
    body.innerHTML = '<p style="padding:2rem;text-align:center;color:var(--color-gray-500)">Could not load your dashboard.</p>';
    return;
  }

  const s = data.stats;
  body.innerHTML = `
    <div class="dash-head">
      <div>
        <h2 id="dashTitle">${data.is_admin_view ? "Platform overview" : "Your dashboard"}</h2>
        <p style="color:var(--color-gray-500);font-size:.9rem">${data.is_admin_view ? "Admin view of all listings" : escHtml(user.business_name || "Your rental portfolio")}</p>
      </div>
      <button class="btn btn-accent" id="addPropertyBtn" type="button">+ Add Property</button>
    </div>
    <div class="dash-stats">
      <div class="dash-stat"><strong>${s.total_properties}</strong><span>Properties</span></div>
      <div class="dash-stat"><strong>${s.available_properties}</strong><span>Available</span></div>
      <div class="dash-stat"><strong>${formatKSh(s.average_rent)}</strong><span>Avg rent</span></div>
      <div class="dash-stat"><strong>${s.total_reviews}</strong><span>Reviews</span></div>
      <div class="dash-stat"><strong>${Number(s.average_rating).toFixed(1)} ★</strong><span>Avg rating</span></div>
    </div>
    <div class="pm-section" id="dashPayments">
      <h3>Payments</h3>
      <div class="pay-cta-group" id="dashPayCtas"></div>
      <div class="pay-toggle-row">
        <span>Collect rent via NyumbaFind
          <small>Let tenants pay rent for your properties through M-Pesa. You can turn this off at any time.</small>
        </span>
        <label class="switch">
          <input type="checkbox" id="acceptsPaymentsToggle" ${user.accepts_payments ? "checked" : ""} />
          <span class="slider" aria-hidden="true"></span>
        </label>
      </div>
      <h4 style="margin:1.2rem 0 .6rem;font-size:.95rem">Payment history</h4>
      <div id="payHistoryList">
        <div class="skeleton skeleton-line w80"></div>
        <div class="skeleton skeleton-line w60" style="margin-top:.5rem"></div>
      </div>
    </div>
    <div id="dashListingArea">
      <h3 style="margin:.8rem 0">Your listings</h3>
      <div class="dash-table-wrap">
        <table class="dash-table">
          <thead><tr><th>Photo</th><th>Title</th><th>Location</th><th>Rent</th><th>Rating</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${data.properties.map((p) => `
              <tr>
                <td data-label="Photo">${p.main_image_url ? `<img class="dash-thumb" src="${escHtml(p.main_image_url)}" alt="" loading="lazy" onerror="nfImgFallback(this,'${escHtml(p.title)}')" />` : ""}</td>
                <td data-label="Title"><strong>${escHtml(p.title)}</strong>${p.is_sample ? ' <span class="card-badge sample" style="position:static">Sample</span>' : ""}</td>
                <td data-label="Location">${escHtml([p.estate, p.town, p.county].filter(Boolean).join(", "))}</td>
                <td data-label="Rent">${formatKSh(p.rent)}</td>
                <td data-label="Rating">${p.review_count ? `${Number(p.average_rating).toFixed(1)} ★ (${p.review_count})` : "—"}</td>
                <td data-label="Status">${p.available ? '<span style="color:var(--color-success);font-weight:600">Available</span>' : '<span style="color:var(--color-gray-500)">Unavailable</span>'}</td>
                <td data-label="">
                  <div class="dash-row-actions">
                    <button class="dash-icon-btn" data-edit="${p.id}" aria-label="Edit ${escHtml(p.title)}" title="Edit">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg>
                    </button>
                    <button class="dash-icon-btn danger" data-delete="${p.id}" aria-label="Delete ${escHtml(p.title)}" title="Delete">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13"/></svg>
                    </button>
                  </div>
                </td>
              </tr>`).join("") || '<tr><td colspan="7" style="text-align:center;color:var(--color-gray-500);padding:1.5rem">No listings yet — click "Add Property" to create your first listing.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
    <div id="dashFormArea"></div>
    <div class="pm-section">
      <h3>Recent reviews on your properties</h3>
      <div class="reviews-list" style="margin-top:.8rem">
        ${data.recent_reviews.length ? data.recent_reviews.map(reviewHtml).join("") : '<p style="color:var(--color-gray-500)">No reviews yet.</p>'}
      </div>
    </div>`;

  $("#addPropertyBtn").addEventListener("click", () => {
    editingProperty = null;
    renderListingForm($("#dashFormArea"), null);
  });

  $$("[data-edit]", body).forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = data.properties.find((x) => x.id === Number(btn.dataset.edit));
      editingProperty = p;
      renderListingForm($("#dashFormArea"), p);
    });
  });

  $$("[data-delete]", body).forEach((btn) => {
    btn.addEventListener("click", async () => {
      const pid = Number(btn.dataset.delete);
      if (!confirm("Delete this listing? This cannot be undone.")) return;
      const res = await api(`/api/properties/${pid}/`, { method: "DELETE" });
      if (res.ok) {
        toast("Listing deleted.", "success");
        openDashboard();
      } else {
        toast("Could not delete this listing.", "error");
      }
    });
  });

  // Open property from dashboard review links
  body.addEventListener("click", (e) => {
    const link = e.target.closest("[data-open-property]");
    if (link) {
      e.preventDefault();
      const pid = Number(link.dataset.openProperty);
      if (pid) openPropertyDetail(pid);
    }
  });

  renderDashboardPayments(body, user);
}

function renderListingForm(container, property) {
  const isEdit = Boolean(property);
  editingProperty = property || null;
  container.innerHTML = `
    <form class="listing-form" id="listingForm" novalidate>
      <h3>${isEdit ? "Edit listing" : "Add a new property"}</h3>
      <div class="form-error" id="listingError" role="alert" hidden></div>
      <div class="field"><label for="lfTitle">Title</label>
        <input id="lfTitle" required value="${escHtml(property?.title || "")}" placeholder="e.g. Sunny 2BR Apartment in Roysambu" /></div>
      <div class="field" style="margin-top:.8rem"><label for="lfDesc">Description</label>
        <textarea id="lfDesc" required placeholder="Describe the home, the neighbourhood, water and power situation…">${escHtml(property?.description || "")}</textarea></div>
      <div class="field-row" style="margin-top:.8rem">
        <div class="field"><label for="lfType">Property type</label>
          <select id="lfType">${Object.entries(PROPERTY_TYPES).map(([v, l]) => `<option value="${v}" ${property?.property_type === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
        <div class="field"><label for="lfCounty">County</label>
          <select id="lfCounty">${COUNTY_LIST.map((c) => `<option ${property?.county === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
      </div>
      <div class="field-row" style="margin-top:.8rem">
        <div class="field"><label for="lfTown">Town</label>
          <input id="lfTown" value="${escHtml(property?.town || "")}" placeholder="e.g. Nairobi" /></div>
        <div class="field"><label for="lfEstate">Estate</label>
          <input id="lfEstate" value="${escHtml(property?.estate || "")}" placeholder="e.g. Roysambu" /></div>
      </div>
      <div class="field" style="margin-top:.8rem"><label for="lfAddress">Address</label>
        <input id="lfAddress" value="${escHtml(property?.address || "")}" placeholder="Street / landmark" /></div>
      <div class="field-row" style="margin-top:.8rem">
        <div class="field"><label for="lfRent">Monthly rent (KSh)</label>
          <input id="lfRent" type="number" min="500" step="100" required value="${property?.rent ?? ""}" placeholder="e.g. 15000" /></div>
        <div class="field"><label for="lfBeds">Bedrooms (0 = bedsitter/studio)</label>
          <input id="lfBeds" type="number" min="0" max="20" required value="${property?.bedrooms ?? 1}" /></div>
      </div>
      <div class="field-row" style="margin-top:.8rem">
        <div class="field"><label for="lfBaths">Bathrooms</label>
          <input id="lfBaths" type="number" min="0" max="20" step="0.5" required value="${property?.bathrooms ?? 1}" /></div>
        <div class="field"><label for="lfAmenities">Amenities (comma separated)</label>
          <input id="lfAmenities" value="${escHtml((property?.amenities || []).join(", "))}" placeholder="WiFi, Generator, Security" /></div>
      </div>
      <label class="checkbox-label" style="margin-top:.8rem">
        <input type="checkbox" id="lfAvailable" ${property ? (property.available ? "checked" : "") : "checked"} /> Currently available
      </label>
      <div class="field-row" style="margin-top:.8rem">
        <div class="field"><label for="lfMainImage">Main photo ${isEdit ? "(replace)" : ""}</label>
          <input id="lfMainImage" type="file" accept="image/*" /></div>
        <div class="field"><label for="lfImages">Extra photos (up to ${isEdit ? 12 - (property?.images?.length || 0) : 11})</label>
          <input id="lfImages" type="file" accept="image/*" multiple /></div>
      </div>
      <div style="display:flex;gap:.6rem;margin-top:1rem;flex-wrap:wrap">
        <button type="submit" class="btn btn-primary">${isEdit ? "Save changes" : "Publish listing"}</button>
        ${isEdit ? '<button type="button" class="btn btn-ghost" id="cancelEditBtn">Cancel</button>' : ""}
      </div>
    </form>`;

  $("#cancelEditBtn")?.addEventListener("click", () => {
    container.innerHTML = "";
    editingProperty = null;
  });

  $("#listingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = $("#listingError");
    errorBox.hidden = true;

    const form = new FormData();
    form.append("title", $("#lfTitle").value.trim());
    form.append("description", $("#lfDesc").value.trim());
    form.append("property_type", $("#lfType").value);
    form.append("county", $("#lfCounty").value);
    form.append("town", $("#lfTown").value.trim());
    form.append("estate", $("#lfEstate").value.trim());
    form.append("address", $("#lfAddress").value.trim());
    form.append("rent", $("#lfRent").value);
    form.append("bedrooms", $("#lfBeds").value);
    form.append("bathrooms", $("#lfBaths").value);
    form.append("available", $("#lfAvailable").checked ? "true" : "false");
    form.append("amenities", JSON.stringify(
      $("#lfAmenities").value.split(",").map((a) => a.trim()).filter(Boolean)
    ));
    const main = $("#lfMainImage").files[0];
    if (main) form.append("main_image", main);
    Array.from($("#lfImages").files).forEach((f) => form.append("images", f));

    const btn = $("#listingForm .btn-primary");
    btn.disabled = true;
    btn.textContent = "Saving…";

    const res = isEdit
      ? await api(`/api/properties/${editingProperty.id}/`, { method: "PATCH", form })
      : await api("/api/properties/", { method: "POST", form });

    btn.disabled = false;
    btn.textContent = isEdit ? "Save changes" : "Publish listing";

    if (res.ok) {
      toast(isEdit ? "Listing updated!" : "Your property is now live!", "success");
      editingProperty = null;
      openDashboard();
      loadFeatured();
      loadRecent();
      loadExplore();
    } else {
      const errors = res.data?.errors || {};
      const messages = Object.values(errors).flat();
      errorBox.innerHTML = messages.length
        ? `<ul>${messages.map((m) => `<li>${escHtml(m)}</li>`).join("")}</ul>`
        : "Could not save the listing. Please check your details.";
      errorBox.hidden = false;
    }
  });
}

/* ---------- AI chatbox ---------- */
const chatState = { open: false, history: [], sending: false, retryMessage: null };

function toggleChat(open) {
  const panel = $("#chatPanel");
  const fab = $("#chatFab");
  chatState.open = typeof open === "boolean" ? open : !chatState.open;
  fab.setAttribute("aria-expanded", String(chatState.open));

  if (chatState.open) {
    panel.hidden = false;
    fab.setAttribute("aria-expanded", "true");
    if (!chatState.history.length) {
      addChatMessage(
        "assistant",
        "Hi! I'm NyumbaFind AI. I can help you explore rental options in Kenya, compare properties, understand tenant ratings, and find a home that suits your budget. What are you looking for?"
      );
    }
    setTimeout(() => $("#chatText").focus(), reduceMotion ? 0 : 250);
  } else {
    panel.classList.add("closing");
    fab.setAttribute("aria-expanded", "false");
    setTimeout(() => {
      panel.hidden = true;
      panel.classList.remove("closing");
    }, reduceMotion ? 0 : 220);
  }
}

function addChatMessage(role, text, properties) {
  const messages = $("#chatMessages");
  const bubble = document.createElement("div");
  bubble.className = `chat-msg ${role}`;
  bubble.innerHTML = escHtml(text).replace(/\n/g, "<br>");
  if (properties && properties.length) {
    const wrap = document.createElement("div");
    wrap.className = "msg-props";
    properties.slice(0, 4).forEach((p) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "chat-prop";
      const img = p.main_image_url || (p.images && p.images[0] && p.images[0].image_url);
      card.innerHTML = `
        ${img ? `<img src="${escHtml(img)}" alt="" loading="lazy" onerror="nfImgFallback(this,'${escHtml(p.title)}')" />` : ""}
        <span class="cp-info">
          <span class="cp-title">${escHtml(p.title)}</span>
          <span class="cp-meta">${escHtml([p.estate, p.town, p.county].filter(Boolean).join(" · "))}${p.rating?.review_count ? ` · ${Number(p.rating.average_rating).toFixed(1)}★ (${p.rating.review_count})` : ""}</span>
          <span class="cp-rent">${formatKSh(p.rent)}/mo</span>
        </span>`;
      card.addEventListener("click", () => openPropertyDetail(p.id));
      wrap.appendChild(card);
    });
    bubble.appendChild(wrap);
  }
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  chatState.history.push({ role, text });
}

function showTyping() {
  const messages = $("#chatMessages");
  const typing = document.createElement("div");
  typing.className = "chat-msg assistant chat-typing";
  typing.id = "chatTyping";
  typing.setAttribute("aria-label", "NyumbaFind AI is typing");
  typing.innerHTML = "<span></span><span></span><span></span>";
  messages.appendChild(typing);
  messages.scrollTop = messages.scrollHeight;
}

function hideTyping() {
  $("#chatTyping")?.remove();
}

function showChatError(message) {
  const messages = $("#chatMessages");
  const el = document.createElement("div");
  el.className = "chat-error";
  el.innerHTML = `${escHtml(message)} <button type="button" id="chatRetry">Retry</button>`;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  $("#chatRetry").addEventListener("click", () => {
    el.remove();
    if (chatState.retryMessage) sendChatMessage(chatState.retryMessage);
  });
}

async function sendChatMessage(text) {
  const message = text.trim();
  if (!message || chatState.sending) return;
  chatState.sending = true;
  chatState.retryMessage = message;
  $("#chatSend").disabled = true;
  addChatMessage("user", message);
  $("#chatText").value = "";
  showTyping();

  try {
    const res = await api("/api/ai/chat/", { method: "POST", body: { message } });
    hideTyping();
    if (res.ok && res.data) {
      setChatStatus(true);
      addChatMessage("assistant", res.data.reply, res.data.properties);
    } else {
      showChatError(res.data?.errors?.message || "Something went wrong. Please try again.");
    }
  } catch {
    hideTyping();
    setChatStatus(false);
    showChatError("Cannot reach the assistant right now. Check your connection.");
  } finally {
    chatState.sending = false;
    $("#chatSend").disabled = false;
  }
}

function setChatStatus(online) {
  const status = $("#chatStatus");
  status.innerHTML = online
    ? '<span class="status-dot"></span>Online'
    : '<span class="status-dot offline"></span>Unavailable';
}

function initChat() {
  $("#chatFab").addEventListener("click", () => toggleChat(true));
  $("#chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    sendChatMessage($("#chatText").value);
  });
  $("#chatClear").addEventListener("click", () => {
    chatState.history = [];
    $("#chatMessages").innerHTML = "";
    addChatMessage(
      "assistant",
      "Conversation cleared. How can I help you find a home today?"
    );
  });
  $$("#chatChips .chip").forEach((chip) => {
    chip.addEventListener("click", () => sendChatMessage(chip.textContent));
  });
}

/* ---------- Navigation ---------- */
function initNavigation() {
  const header = $("#siteHeader");
  const toggle = $("#navToggle");
  const navLinks = $("#navLinks");

  window.addEventListener("scroll", () => {
    header.classList.toggle("scrolled", window.scrollY > 8);
  }, { passive: true });

  toggle.addEventListener("click", () => {
    const open = navLinks.classList.toggle("open");
    toggle.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  });

  navLinks.addEventListener("click", (e) => {
    if (e.target.classList.contains("nav-link")) {
      navLinks.classList.remove("open");
      toggle.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });

  // Active link highlighting
  const sections = ["featured", "locations", "explore", "reviews", "how", "faq"];
  const linkMap = {};
  $$(".nav-link").forEach((link) => {
    linkMap[link.getAttribute("href").slice(1)] = link;
  });
  if ("IntersectionObserver" in window && !reduceMotion) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          Object.values(linkMap).forEach((l) => l.classList.remove("active"));
          linkMap[entry.target.id]?.classList.add("active");
        }
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    sections.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
  }
}

/* ---------- Reveal on scroll ---------- */
let revealObserver = null;

// Observe .reveal elements — including ones injected
// AFTER initReveal() ran (e.g. the location cards,
// which are rendered by loadLocations()). Without
// this, dynamically added .reveal elements stay
// invisible because .reveal { opacity: 0 }.
function observeReveals(root = document) {
  const elements = $$(".reveal:not(.in-view)", root);
  if (!elements.length) return;
  if (reduceMotion || !("IntersectionObserver" in window)) {
    elements.forEach((el) => el.classList.add("in-view"));
    return;
  }
  if (!revealObserver) {
    revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
  }
  elements.forEach((el) => revealObserver.observe(el));
}

function initReveal() {
  observeReveals();
  animateBars();

  // Animate rating bars when visible
  const barObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        $$(".bar-fill", entry.target).forEach((bar) => {
          bar.style.width = bar.dataset.width || "0%";
        });
        barObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });
  $$(".rating-bars, .category-bars, .pm-rating-grid").forEach((el) => barObserver.observe(el));

  // Hero stat count-up
  const counters = $$("[data-count]");
  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = Number(el.dataset.count);
      const start = performance.now();
      const duration = 1200;
      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        el.textContent = Math.round(target * (1 - Math.pow(1 - progress, 3)));
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      counterObserver.unobserve(el);
    });
  }, { threshold: 0.6 });
  counters.forEach((el) => counterObserver.observe(el));
}

function animateBars() {
  $$(".bar-fill").forEach((bar) => {
    bar.style.width = bar.dataset.width || "0%";
  });
}

/* ---------- Review card "report" delegation (global) ---------- */
function initGlobalDelegation() {
  document.addEventListener("click", (e) => {
    const card = e.target.closest(".property-card[data-property-id]");
    if (card && !e.target.closest("button")) {
      openPropertyDetail(Number(card.dataset.propertyId));
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const card = e.target.closest?.(".property-card[data-property-id]");
      if (card) openPropertyDetail(Number(card.dataset.propertyId));
    }
  });
}

/* ---------- County selects ---------- */
function initCountySelects() {
  const options = '<option value="">All counties</option>' +
    COUNTY_LIST.map((c) => `<option value="${c}">${c}</option>`).join("");
  ["searchCounty", "filterCounty", "mapCounty"].forEach((id) => {
    const el = $(`#${id}`);
    if (el) el.innerHTML = options;
  });
}

/* ---------- Map search (Leaflet + OpenStreetMap) ---------- */
const FAV_KEY = "nf_favorites";

const mapState = {
  q: "", county: "", town: "", estate: "",
  property_type: "", min_rent: "", max_rent: "", bedrooms: "",
  available: false, saved_only: false, sort: "newest",
  page: 1,
  useBounds: false,
  bounds: null,
  autoSearch: false,
  firstLoad: true,
};

let leafletMap = null;
let markerCluster = null;
let mapMarkersById = {};
let mapMoveTimer = null;
let geoSearchTimer = null;
let mapResultsCache = [];

const getFavorites = () => {
  try {
    return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));
  } catch {
    return new Set();
  }
};

function saveFavorite(id, fav) {
  const favs = getFavorites();
  if (fav) favs.add(id);
  else favs.delete(id);
  localStorage.setItem(FAV_KEY, JSON.stringify([...favs]));
}

function formatShortRent(rent) {
  const n = Number(rent || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${Math.round(n / 1000)}K`;
  return `${n}`;
}

function mapQueryParams(forMarkers) {
  const p = new URLSearchParams();
  if (mapState.county) p.set("county", mapState.county);
  if (mapState.town) p.set("town", mapState.town);
  if (mapState.estate) p.set("estate", mapState.estate);
  if (mapState.q) p.set("q", mapState.q);
  if (mapState.property_type) p.set("property_type", mapState.property_type);
  if (mapState.min_rent) p.set("min_rent", mapState.min_rent);
  if (mapState.max_rent) p.set("max_rent", mapState.max_rent);
  if (mapState.bedrooms !== "") p.set("bedrooms", mapState.bedrooms);
  if (mapState.available) p.set("available", "true");
  if (mapState.sort) p.set("sort", mapState.sort);

  if (forMarkers) {
    p.set("has_coords", "true");
    p.set("page_size", "500");
    if (mapState.useBounds && mapState.bounds) {
      p.set("min_lat", mapState.bounds.min_lat);
      p.set("max_lat", mapState.bounds.max_lat);
      p.set("min_lng", mapState.bounds.min_lng);
      p.set("max_lng", mapState.bounds.max_lng);
    }
  } else if (mapState.saved_only) {
    // Saved properties are a client-side (browser) filter,
    // so fetch the full set and paginate locally.
    p.set("page_size", "500");
  } else {
    p.set("page", mapState.page);
    p.set("page_size", "9");
  }
  return p.toString();
}

function applySavedOnly(list) {
  if (!mapState.saved_only) return list;
  const favs = getFavorites();
  return list.filter((p) => favs.has(p.id));
}

function setMapView(mode) {
  const section = $("#map");
  section.classList.toggle("list-mode", mode === "list");
  section.dataset.view = mode;
  $("#viewMapBtn").classList.toggle("active", mode === "map");
  $("#viewListBtn").classList.toggle("active", mode === "list");
  $("#viewMapBtn").setAttribute("aria-pressed", String(mode === "map"));
  $("#viewListBtn").setAttribute("aria-pressed", String(mode === "list"));
  if (mode === "map" && leafletMap) {
    setTimeout(() => leafletMap.invalidateSize(), 60);
  }
}

function syncMapInputs() {
  $("#mapCounty").value = mapState.county;
  $("#mapType").value = mapState.property_type;
  $("#mapMinRent").value = mapState.min_rent;
  $("#mapMaxRent").value = mapState.max_rent;
  $("#mapBeds").value = mapState.bedrooms;
  $("#mapAvailable").checked = mapState.available;
  $("#mapSaved").checked = mapState.saved_only;
}

function setMapFilter(patch) {
  Object.assign(mapState, patch, { page: 1 });
  syncMapInputs();
  loadMapResults();
  loadMapMarkers();
}

/* ---- Markers ---- */
function priceMarkerHtml(p) {
  const favs = getFavorites();
  const fav = favs.has(p.id)
    ? '<span class="pm-marker-fav" aria-hidden="true">♥</span>'
    : "";
  return `<div class="pm-marker" data-marker-id="${p.id}">${formatShortRent(p.rent)}${fav}</div>`;
}

function makePriceMarker(p) {
  const icon = L.divIcon({
    className: "pm-marker-wrap",
    html: priceMarkerHtml(p),
    iconSize: [64, 34],
    iconAnchor: [32, 30],
    popupAnchor: [0, -30],
  });
  const marker = L.marker([Number(p.latitude), Number(p.longitude)], {
    icon,
    title: p.title,
    keyboard: true,
  });
  marker.propertyId = p.id;
  marker.bindPopup(mapPopupHtml(p), { maxWidth: 280, closeButton: true });
  marker.on("popupopen", () => setSelectedMarker(p.id));
  marker.on("popupclose", () => clearSelectedMarker());
  return marker;
}

function clusterIconFactory(cluster) {
  const count = cluster.getChildCount();
  const sizeClass =
    count > 20 ? "pm-cluster-large" : count > 8 ? "" : "pm-cluster-small";
  return L.divIcon({
    className: "pm-cluster-wrap",
    html: `<div class="pm-cluster ${sizeClass}"><span>${count}</span></div>`,
    iconSize: [46, 46],
    iconAnchor: [23, 23],
  });
}

function setSelectedMarker(id) {
  Object.values(mapMarkersById).forEach((m) => {
    const el = m.getElement();
    if (el) {
      const inner = el.querySelector(".pm-marker");
      if (inner) inner.classList.toggle("selected", m.propertyId === id);
    }
  });
  highlightCard(id, true);
}

function clearSelectedMarker() {
  Object.values(mapMarkersById).forEach((m) => {
    const el = m.getElement();
    if (el) {
      const inner = el.querySelector(".pm-marker");
      if (inner) inner.classList.remove("selected");
    }
  });
  $$(".property-card.card-highlight").forEach((card) =>
    card.classList.remove("card-highlight")
  );
}

function highlightCard(id, on) {
  const card = document.querySelector(
    `.property-card[data-property-id="${id}"]`
  );
  if (card) card.classList.toggle("card-highlight", on);
}

function highlightMarker(id, on) {
  const marker = mapMarkersById[id];
  if (!marker) return;
  const el = marker.getElement();
  if (!el) return;
  const inner = el.querySelector(".pm-marker");
  if (inner) inner.classList.toggle("hover", on);
}



/* ---- Popup ---- */
function mapPopupHtml(p) {
  const img = p.main_image_url;
  const rating = p.rating || {};
  const avg = Number(rating.average_rating || 0);
  const beds =
    p.property_type === "bedsitter" || p.property_type === "studio"
      ? "Bedsitter"
      : `${p.bedrooms} bd`;
  const location = [p.estate, p.town, p.county].filter(Boolean).join(" · ");
  const favs = getFavorites();
  const isFav = favs.has(p.id);

  return `
    <div class="pm-popup">
      <div class="pm-popup-media">
        ${img
          ? `<img src="${escHtml(img)}" alt="${escHtml(p.title)}" loading="lazy" onerror="nfImgFallback(this, '${escHtml(p.title)}')" />`
          : `<div class="img-fallback"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 11.5 12 4l9 7.5v7a2 2 0 0 1-2 2h-4v-6h-6v6H5a2 2 0 0 1-2-2z"/></svg><span>No photo</span></div>`}
        <span class="pm-popup-type">${escHtml(PROPERTY_TYPES[p.property_type] || p.property_type)}</span>
        <span class="pm-popup-avail ${p.available ? "yes" : "no"}">${p.available ? "Available" : "Unavailable"}</span>
      </div>
      <div class="pm-popup-body">
        <h3>${escHtml(p.title)}</h3>
        <p class="pm-popup-loc">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>
          <span>${escHtml(location || p.county)}</span>
        </p>
        <div class="pm-popup-meta">${beds} · ${p.bathrooms} ba${rating.review_count ? ` · ★ ${avg.toFixed(1)} (${rating.review_count})` : ""}</div>
        <div class="pm-popup-foot">
          <span class="pm-popup-price">${formatKSh(p.rent)}<small>/month</small></span>
        </div>
        <div class="pm-popup-actions">
          <button class="btn btn-primary btn-sm" type="button" data-map-view="${p.id}">View Property</button>
          <button class="pm-fav-btn ${isFav ? "active" : ""}" type="button" data-map-fav="${p.id}" aria-label="${isFav ? "Remove from saved" : "Save property"}" aria-pressed="${isFav}">${isFav ? "♥" : "♡"}</button>
        </div>
      </div>
    </div>`;
}

function refreshPopupFor(propertyId) {
  const marker = mapMarkersById[propertyId];
  if (!marker) return;
  const p = mapResultsCache.find((x) => x.id === propertyId);
  if (p) {
    marker.setPopupContent(mapPopupHtml(p));
  }
  const el = marker.getElement();
  if (el) {
    const inner = el.querySelector(".pm-marker");
    if (inner) {
      inner.querySelector(".pm-marker-fav")?.remove();
      if (getFavorites().has(propertyId)) {
        inner.insertAdjacentHTML(
          "beforeend",
          '<span class="pm-marker-fav" aria-hidden="true">♥</span>'
        );
      }
    }
  }
}

/* ---- Loading ---- */
function showMapLoading(on) {
  $("#mapLoading").hidden = !on;
}

async function loadMapMarkers() {
  if (!leafletMap || !markerCluster) return;
  showMapLoading(true);
  const { ok, data } = await api(`/api/properties/?${mapQueryParams(true)}`);
  markerCluster.clearLayers();
  mapMarkersById = {};
  if (!ok || !data) {
    showMapLoading(false);
    return;
  }
  const results = applySavedOnly(data.results || []);
  mapResultsCache = results;
  const markers = [];
  results.forEach((p) => {
    if (p.latitude == null || p.longitude == null) return;
    const marker = makePriceMarker(p);
    mapMarkersById[p.id] = marker;
    markers.push(marker);
  });
  markerCluster.addLayers(markers);
  showMapLoading(false);
  $("#mapEmpty").hidden = results.length > 0;
  if (results.length === 0) {
    $("#mapMobileCount").textContent = "0 listings";
  }

  if (mapState.firstLoad && results.length) {
    mapState.firstLoad = false;
    fitMapToMarkers(results);
  }
}

function fitMapToMarkers(results) {
  if (!leafletMap || !results.length) return;
  const points = results
    .filter((p) => p.latitude != null && p.longitude != null)
    .map((p) => [Number(p.latitude), Number(p.longitude)]);
  if (!points.length) return;
  leafletMap.flyToBounds(L.latLngBounds(points).pad(0.15), {
    duration: reduceMotion ? 0 : 0.8,
  });
}

function updateMapCounts() {
  const count = $("#mapResultsCount");
  const mobile = $("#mapMobileCount");
  if (mobile && count) mobile.textContent = count.textContent;
}

async function loadMapResults() {
  const grid = $("#mapGrid");
  const count = $("#mapResultsCount");
  const pagination = $("#mapPagination");
  skeletonCards(6, grid);
  count.textContent = "Searching…";
  pagination.innerHTML = "";

  const { ok, data } = await api(`/api/properties/?${mapQueryParams(false)}`);
  if (!ok || !data) {
    count.textContent = "";
    renderCards(grid, [], "Something went wrong while loading listings.");
    return;
  }

  const allResults = data.results || [];
  const results = applySavedOnly(allResults);
  const total = mapState.saved_only ? results.length : data.count;
  count.textContent = `${total} listing${total === 1 ? "" : "s"} found`;
  updateMapCounts();

  const totalPages = Math.ceil(total / 9) || 1;
  const page = Math.min(mapState.page, totalPages);
  const pageResults = mapState.saved_only
    ? results.slice((page - 1) * 9, page * 9)
    : results;
  renderCards(grid, pageResults);
  let buttons = "";
  buttons += `<button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""} aria-label="Previous page">‹</button>`;
  const windowPages = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || Math.abs(i - page) <= 2) windowPages.push(i);
  }
  let last = 0;
  windowPages.forEach((i) => {
    if (i - last > 1) buttons += `<span class="page-btn" style="border:none;cursor:default">…</span>`;
    buttons += `<button class="page-btn ${i === page ? "active" : ""}" data-page="${i}" ${i === page ? 'aria-current="page"' : ""}>${i}</button>`;
    last = i;
  });
  buttons += `<button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""} aria-label="Next page">›</button>`;
  pagination.innerHTML = buttons;

  $$(".page-btn[data-page]", pagination).forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = Number(btn.dataset.page);
      if (next >= 1 && next <= totalPages) {
        mapState.page = next;
        loadMapResults();
        $("#map").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      }
    });
  });

  // Card hover ↔ marker highlight
  $$(".property-card", grid).forEach((card) => {
    const id = Number(card.dataset.propertyId);
    card.addEventListener("mouseenter", () => highlightMarker(id, true));
    card.addEventListener("mouseleave", () => highlightMarker(id, false));
    card.addEventListener("focus", () => highlightMarker(id, true));
    card.addEventListener("blur", () => highlightMarker(id, false));
  });

  updateMapCounts(results.length);
}

/* ---- Location autocomplete ---- */
const GEO_ICONS = {
  county: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/></svg>',
  town: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M5 21V7l7-4 7 4v14"/><path d="M9 21v-6h6v6"/></svg>',
  estate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
};

async function searchLocations(q) {
  const { ok, data } = await api(
    `/api/locations/search/?${new URLSearchParams({ q }).toString()}`
  );
  return ok && data ? data.results || [] : [];
}

function renderGeoDropdown(results) {
  const dropdown = $("#geoDropdown");
  if (!results.length) {
    dropdown.innerHTML = '<div class="geo-empty">No matching locations — try a county, town or estate with listings.</div>';
    dropdown.hidden = false;
    return;
  }
  dropdown.innerHTML = results
    .map(
      (r, i) => `
      <button class="geo-item" type="button" data-geo-index="${i}">
        <span class="geo-item-icon" aria-hidden="true">${GEO_ICONS[r.type] || GEO_ICONS.estate}</span>
        <span class="geo-item-info">
          <span class="geo-item-name">${escHtml(r.name)}</span>
          <span class="geo-item-sub">${escHtml([r.town && r.type !== "town" ? r.town : "", r.county].filter(Boolean).join(" · "))}</span>
        </span>
        <span class="geo-item-count">${r.count} listing${r.count === 1 ? "" : "s"}</span>
      </button>`
    )
    .join("");
  dropdown.hidden = false;
  $$(".geo-item", dropdown).forEach((item) => {
    item.addEventListener("click", () => {
      applyLocation(results[Number(item.dataset.geoIndex)]);
    });
  });
}

function applyLocation(loc) {
  $("#geoDropdown").hidden = true;
  $("#mapSearch").value = loc.name;
  mapState.q = "";
  if (loc.type === "county") {
    setMapFilter({ county: loc.name, town: "", estate: "" });
  } else if (loc.type === "town") {
    setMapFilter({ county: loc.county, town: loc.name, estate: "" });
  } else {
    setMapFilter({ county: loc.county, town: loc.town || "", estate: loc.name });
  }
  if (
    leafletMap &&
    loc.latitude != null &&
    loc.longitude != null
  ) {
    const zoom = loc.type === "county" ? 10 : loc.type === "town" ? 12 : 14;
    leafletMap.flyTo(
      [Number(loc.latitude), Number(loc.longitude)],
      zoom,
      { duration: reduceMotion ? 0 : 0.9 }
    );
  }
  toast(
    `Showing ${loc.name} — ${loc.count} listing${loc.count === 1 ? "" : "s"}`,
    "success"
  );
}

function initGeoSearch() {
  const input = $("#mapSearch");
  const dropdown = $("#geoDropdown");

  input.addEventListener("input", () => {
    const q = input.value.trim();
    clearTimeout(geoSearchTimer);
    if (q.length < 2) {
      dropdown.hidden = true;
      return;
    }
    geoSearchTimer = setTimeout(async () => {
      const results = await searchLocations(q);
      renderGeoDropdown(results);
    }, 300);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dropdown.hidden = true;
      input.blur();
      return;
    }
    const items = $$(".geo-item", dropdown);
    if (!items.length) return;
    const active = dropdown.querySelector(".geo-item.active");
    let idx = active ? items.indexOf(active) : -1;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      idx = Math.min(items.length - 1, idx + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      idx = Math.max(0, idx - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target = items[idx >= 0 ? idx : 0];
      if (target) {
        target.click();
        return;
      }
      // No known location matches — fall back to a
      // full-text search across the listing fields.
      const q = input.value.trim();
      if (q.length >= 2) {
        dropdown.hidden = true;
        setMapFilter({ q });
        toast(`Searching for "${q}"`, "success");
      }
      return;
    } else {
      return;
    }
    items.forEach((item) => item.classList.remove("active"));
    if (items[idx]) {
      items[idx].classList.add("active");
      items[idx].scrollIntoView({ block: "nearest" });
    }
  });

  input.addEventListener("blur", () => {
    setTimeout(() => {
      dropdown.hidden = true;
    }, 150);
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".geo-search-wrap")) {
      dropdown.hidden = true;
    }
  });
}

/* ---- Map move / search area ---- */
function onMapMove() {
  clearTimeout(mapMoveTimer);
  mapMoveTimer = setTimeout(() => {
    if (!leafletMap) return;
    if (mapState.autoSearch) {
      updateBoundsFromMap();
      loadMapResults();
      loadMapMarkers();
    } else {
      showAreaBar(true);
    }
  }, reduceMotion ? 50 : 350);
}

function updateBoundsFromMap() {
  const b = leafletMap.getBounds();
  mapState.useBounds = true;
  mapState.bounds = {
    min_lat: b.getSouth().toFixed(5),
    max_lat: b.getNorth().toFixed(5),
    min_lng: b.getWest().toFixed(5),
    max_lng: b.getEast().toFixed(5),
  };
  $("#mapAreaLabel").textContent = "Search this visible area?";
}

function showAreaBar(show) {
  const bar = $("#mapAreaBar");
  if (!show) {
    bar.hidden = true;
    return;
  }
  updateBoundsFromMap();
  bar.hidden = false;
}

/* ---- Fullscreen ---- */
function toggleMapFullscreen() {
  const pane = $("#mapPane");
  if (!document.fullscreenElement) {
    if (pane.requestFullscreen) {
      pane.requestFullscreen().catch(() => toast("Fullscreen not available.", "error"));
    }
  } else if (document.exitFullscreen) {
    document.exitFullscreen();
  }
}

/* ---- Init ---- */
/* ---- Map tile providers ---------------------------- */
// Built-in, key-less Leaflet-compatible providers, in
// fallback order. The map engine, markers, search and
// listings never depend on any single provider being
// reachable — if one fails, the next is used
// automatically.
const MAP_TILE_PROVIDERS = [
  {
    name: "OpenStreetMap",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    subdomains: "abc",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
  },
  {
    name: "CARTO",
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    subdomains: "abcd",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>',
  },
];

// The primary provider can be overridden server-side
// (MAP_TILE_URL / MAP_TILE_ATTRIBUTION / MAP_TILE_API_KEY
// in the environment). Any API key is injected here from
// Django settings — never committed to the frontend code.
function configuredTileProviders() {
  const cfg = window.NYUMBAFIND_MAP_CONFIG || {};
  if (cfg.tileUrl) {
    let url = cfg.tileUrl;
    if (cfg.apiKey) {
      url +=
        (url.includes("?") ? "&" : "?") +
        "key=" +
        encodeURIComponent(cfg.apiKey);
    }
    return [
      {
        name: "Configured provider",
        url,
        subdomains: "abc",
        attribution: cfg.attribution || "Map data",
      },
      ...MAP_TILE_PROVIDERS, // built-ins remain as fallbacks
    ];
  }
  return MAP_TILE_PROVIDERS;
}

let tileLayer = null;
let tileProviderList = [];
let tileProviderIndex = 0;
let tileErrorCount = 0;

function attachTileLayer(provider) {
  // The map is created once — only the tile layer is
  // swapped, never the map itself.
  if (tileLayer) {
    tileLayer.off("tileerror");
    tileLayer.off("load");
    leafletMap.removeLayer(tileLayer);
  }
  tileLayer = L.tileLayer(provider.url, {
    attribution: provider.attribution,
    maxZoom: 19,
    subdomains: provider.subdomains || "abc",
  });
  tileLayer.on("tileerror", onTileError);
  tileLayer.on("load", () => {
    // Layout settled — recalculate the map size.
    leafletMap.invalidateSize();
  });
  tileLayer.addTo(leafletMap);
}

function onTileError() {
  tileErrorCount += 1;
  // A handful of failed tiles can be transient;
  // sustained failures mean this provider is
  // unreachable — switch to the next one
  // automatically.
  if (
    tileErrorCount >= 4 &&
    tileProviderIndex < tileProviderList.length - 1
  ) {
    tileProviderIndex += 1;
    tileErrorCount = 0;
    $("#mapTilesNotice").hidden = true;
    attachTileLayer(tileProviderList[tileProviderIndex]);
    toast(
      `Map tiles switched to ${tileProviderList[tileProviderIndex].name}.`,
      "info"
    );
    return;
  }
  if (tileErrorCount >= 8) {
    $("#mapTilesNotice").hidden = false;
  }
}

function initMapSearch() {
  const section = $("#map");
  if (!section || section.dataset.initialized === "true") {
    // Never initialize twice — Leaflet throws
    // "Map container is already initialized".
    return;
  }
  section.dataset.initialized = "true";

  // View toggle
  $("#viewMapBtn").addEventListener("click", () => setMapView("map"));
  $("#viewListBtn").addEventListener("click", () => setMapView("list"));
  $("#mapShowMapBtn").addEventListener("click", () => setMapView("map"));
  $("#mapShowListBtn").addEventListener("click", () => setMapView("list"));

  // Filters
  const filterMap = {
    mapCounty: "county", mapType: "property_type",
    mapMinRent: "min_rent", mapMaxRent: "max_rent",
    mapBeds: "bedrooms",
  };
  Object.entries(filterMap).forEach(([id, key]) => {
    $(`#${id}`).addEventListener("change", (e) => {
      setMapFilter({ [key]: e.target.value });
    });
  });
  $("#mapAvailable").addEventListener("change", (e) => {
    setMapFilter({ available: e.target.checked });
  });
  $("#mapSaved").addEventListener("change", (e) => {
    setMapFilter({ saved_only: e.target.checked });
  });
  $("#mapClear").addEventListener("click", () => {
    Object.assign(mapState, {
      q: "", county: "", town: "", estate: "",
      property_type: "", min_rent: "", max_rent: "", bedrooms: "",
      available: false, saved_only: false, sort: "newest", page: 1,
      useBounds: false, bounds: null,
    });
    $("#mapSearch").value = "";
    syncMapInputs();
    showAreaBar(false);
    loadMapResults();
    loadMapMarkers();
    if (leafletMap) {
      leafletMap.flyTo([-0.45, 37.9], 6, { duration: reduceMotion ? 0 : 0.8 });
    }
  });
  $("#mapEmptyClear").addEventListener("click", () => {
    $("#mapClear").click();
  });

  // Search-this-area
  $("#mapSearchAreaBtn").addEventListener("click", () => {
    updateBoundsFromMap();
    showAreaBar(false);
    mapState.page = 1;
    loadMapResults();
    loadMapMarkers();
  });
  $("#mapAutoSearch").addEventListener("change", (e) => {
    mapState.autoSearch = e.target.checked;
    if (!e.target.checked) showAreaBar(false);
  });

  // Fullscreen
  $("#mapFullscreenBtn").addEventListener("click", toggleMapFullscreen);

  // Popup actions (delegated)
  $("#mapPane").addEventListener("click", (e) => {
    const viewBtn = e.target.closest("[data-map-view]");
    if (viewBtn) {
      openPropertyDetail(Number(viewBtn.dataset.mapView));
      return;
    }
    const favBtn = e.target.closest("[data-map-fav]");
    if (favBtn) {
      const id = Number(favBtn.dataset.mapFav);
      const favs = getFavorites();
      const nowFav = !favs.has(id);
      saveFavorite(id, nowFav);
      refreshPopupFor(id);
      if (mapState.saved_only) {
        loadMapResults();
        loadMapMarkers();
      }
      toast(
        nowFav ? "Property saved." : "Property removed from saved.",
        "success"
      );
    }
  });

  initGeoSearch();

  // ---- Leaflet map -------------------------------------
  const mapElement = document.getElementById("propertyMap");
  if (!mapElement) {
    console.error("NyumbaFind: map container #propertyMap not found.");
    $("#mapUnavailable").hidden = false;
    loadMapResults();
    return;
  }
  if (typeof L === "undefined") {
    console.error("NyumbaFind: Leaflet failed to load.");
    $("#mapUnavailable").hidden = false;
    loadMapResults();
    return;
  }
  if (mapElement.dataset.mapInitialized === "true") {
    return;
  }

  try {
    leafletMap = L.map(mapElement, {
      center: [-0.45, 37.9],
      zoom: 6,
      zoomControl: true,
      scrollWheelZoom: false,
      worldCopyJump: true,
    });
  } catch (err) {
    console.error("NyumbaFind: map initialization failed.", err);
    $("#mapUnavailable").hidden = false;
    loadMapResults();
    return;
  }
  mapElement.dataset.mapInitialized = "true";
  leafletMap.attributionControl.setPrefix(false);

  // Tile layer with automatic provider fallback: a
  // blocked tile network must not silently produce a
  // blank map — the next provider is used instead.
  tileProviderList = configuredTileProviders();
  tileProviderIndex = 0;
  tileErrorCount = 0;
  attachTileLayer(tileProviderList[0]);

  $("#mapTilesRetry").addEventListener("click", () => {
    tileProviderIndex = 0;
    tileErrorCount = 0;
    $("#mapTilesNotice").hidden = true;
    attachTileLayer(tileProviderList[0]);
    leafletMap.invalidateSize();
  });

  // Avoid hijacking page scroll; enable zoom when the map is interacted with.
  leafletMap.on("click", () => leafletMap.scrollWheelZoom.enable());
  leafletMap.on("mouseout", () => leafletMap.scrollWheelZoom.disable());

  markerCluster = L.markerClusterGroup({
    chunkedLoading: true,
    chunkInterval: 200,
    chunkDelay: 50,
    maxClusterRadius: 60,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    iconCreateFunction: clusterIconFactory,
  });
  leafletMap.addLayer(markerCluster);

  leafletMap.on("moveend", onMapMove);
  leafletMap.on("resize", () => leafletMap.invalidateSize());

  // Recalculate when the map scrolls into view — the layout
  // may have changed while it was off-screen.
  if ("IntersectionObserver" in window) {
    const sizeObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          leafletMap.invalidateSize();
        }
      });
    }, { threshold: 0.05 });
    sizeObserver.observe(mapElement);
  }

  // Safety net: recalc after fonts/layout settle.
  setTimeout(() => {
    if (leafletMap) leafletMap.invalidateSize();
  }, 300);

  loadMapResults();
  loadMapMarkers();
}

/* ---------- M-Pesa payments ---------- */
const payState = {
  config: null,          // public payment configuration
  current: null,         // payment being initiated {purpose, amount, property}
  lastPayment: null,     // last transaction object
  pollTimer: null,
  pollCount: 0,
  pollInterval: 3000,    // ms
  maxPolls: 40,          // ~2 minutes of polling
  propertiesById: {},    // property objects for payment CTAs
};

function payPurposeLabel(purpose) {
  return {
    listing_fee: "Listing fee",
    viewing_fee: "Viewing / booking fee",
    rental_payment: "Rent payment",
  }[purpose] || purpose;
}

function formatPhone(phone) {
  const digits = String(phone || "").replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("254")) {
    return `+254 ${digits.slice(3, 6)} ${digits.slice(6, 9)} ${digits.slice(9)}`;
  }
  return phone || "";
}

async function loadPaymentConfig() {
  const { ok, data } = await api("/api/payments/config/");
  if (ok && data) payState.config = data;
  return payState.config;
}

/* Payment CTAs shown inside the property detail modal.
   Only rendered for signed-in viewers who are not the owner. */
function paymentCtasHtml(p) {
  const user = getCurrentUser();
  const cfg = payState.config;
  if (!user || !getToken() || !cfg || p.is_owner) return "";

  const cta = [];
  if (cfg.enabled_purposes.includes("viewing_fee")) {
    cta.push(`
      <button class="pay-cta" type="button" data-pay-purpose="viewing_fee"
        data-pay-amount="${cfg.viewing_fee_amount}" data-pay-property-id="${p.id}">
        <span class="pay-cta-label">
          <strong>Book a viewing</strong>
          <small>Secure M-Pesa booking — refundable if the viewing doesn't happen</small>
        </span>
        <span class="pay-cta-amount">${formatKSh(cfg.viewing_fee_amount)}</span>
        <svg class="pay-cta-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>
      </button>`);
  }
  if (
    cfg.enabled_purposes.includes("rental_payment") &&
    cfg.rental_payments_enabled &&
    p.owner_accepts_payments
  ) {
    cta.push(`
      <button class="pay-cta" type="button" data-pay-purpose="rental_payment"
        data-pay-amount="${p.rent}" data-pay-property-id="${p.id}">
        <span class="pay-cta-label">
          <strong>Pay rent via M-Pesa</strong>
          <small>This landlord accepts rent payments through NyumbaFind</small>
        </span>
        <span class="pay-cta-amount">${formatKSh(p.rent)}</span>
        <svg class="pay-cta-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>
      </button>`);
  }
  if (!cta.length) return "";
  return `<div class="pay-cta-group">${cta.join("")}</div>`;
}

/* Dashboard payments block: listing-fee CTA, rent-collection
   authorization toggle and payment history. */
function renderDashboardPayments(body, user) {
  const cfg = payState.config;
  const ctaBox = $("#dashPayCtas", body);
  if (ctaBox && cfg && cfg.enabled_purposes.includes("listing_fee")) {
    ctaBox.innerHTML = `
      <button class="pay-cta" type="button" data-pay-purpose="listing_fee"
        data-pay-amount="${cfg.listing_fee_amount}">
        <span class="pay-cta-label">
          <strong>Pay listing fee</strong>
          <small>Keep your properties visible to thousands of tenants</small>
        </span>
        <span class="pay-cta-amount">${formatKSh(cfg.listing_fee_amount)}</span>
        <svg class="pay-cta-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>
      </button>`;
  }

  const toggle = $("#acceptsPaymentsToggle", body);
  if (toggle) {
    toggle.addEventListener("change", async (e) => {
      const res = await api("/api/auth/me/", {
        method: "PATCH",
        body: { accepts_payments: e.target.checked },
      });
      if (res.ok) {
        toast(
          e.target.checked
            ? "Tenants can now pay rent for your properties via M-Pesa."
            : "Rent collection turned off.",
          "success"
        );
      } else {
        toast("Could not update payment settings.", "error");
        e.target.checked = !e.target.checked;
      }
    });
  }

  loadPaymentHistory($("#payHistoryList", body));
}

async function loadPaymentHistory(container) {
  if (!container) return;
  const { ok, data } = await api("/api/payments/history/");
  if (!ok || !data) {
    container.innerHTML = '<p style="color:var(--color-gray-500)">Could not load payment history.</p>';
    return;
  }
  const list = data.results || [];
  container.innerHTML = list.length
    ? list.map(payHistoryItemHtml).join("")
    : '<p style="color:var(--color-gray-500)">No payments yet.</p>';
}

function payHistoryItemHtml(p) {
  return `
    <div class="pay-history-item">
      <div class="pay-history-info">
        <strong>${escHtml(payPurposeLabel(p.purpose))}${p.property_title ? ` — ${escHtml(p.property_title)}` : ""}</strong>
        <small>${escHtml(p.reference)} · ${new Date(p.created).toLocaleDateString("en-KE")}${p.mpesa_receipt_number ? ` · M-Pesa ${escHtml(p.mpesa_receipt_number)}` : ""}</small>
      </div>
      <div class="pay-history-right">
        <strong>${formatKSh(p.amount)}</strong>
        <span class="pay-status-pill ${escHtml(p.status)}">${escHtml(p.status)}</span>
      </div>
    </div>`;
}

/* Payment modal steps */
const PAY_STEPS = ["payStepDetails", "payStepProcessing", "payStepSuccess", "payStepFailed"];

function showPayStep(id) {
  PAY_STEPS.forEach((step) => {
    const el = $(`#${step}`);
    if (el) el.hidden = step !== id;
  });
}

function openPaymentModal(context) {
  payState.current = context;
  showPayStep("payStepDetails");
  const errEl = $("#payError");
  if (errEl) errEl.hidden = true;
  const form = $("#payForm");
  if (form) form.reset();

  const rows = [
    ["Payment for", payPurposeLabel(context.purpose)],
  ];
  if (context.property) {
    rows.push(["Property", context.property.title]);
    rows.push([
      "Location",
      [context.property.estate, context.property.town, context.property.county]
        .filter(Boolean).join(", "),
    ]);
  }
  rows.push(["Total", formatKSh(context.amount)]);

  $("#paySummary").innerHTML = rows.map(([k, v], i) => `
    <div class="pay-summary-row ${i === rows.length - 1 ? "total" : ""}">
      <span>${escHtml(k)}</span><strong>${escHtml(v)}</strong>
    </div>`).join("");

  openModal("paymentModal");
}

async function initiatePayment(e) {
  e.preventDefault();
  const ctx = payState.current;
  if (!ctx) return;

  const errEl = $("#payError");
  const showError = (msg) => {
    errEl.textContent = msg;
    errEl.hidden = false;
  };
  errEl.hidden = true;

  const phoneRaw = $("#payPhone").value.trim();
  const description = $("#payDescription").value.trim();

  // Client-side validation — the server re-validates everything.
  const digits = phoneRaw.replace(/\D/g, "");
  if (!/^(?:2547\d{8}|07\d{8}|7\d{8})$/.test(digits)) {
    showError("Enter a valid Kenyan mobile number, e.g. 0712 345 678.");
    return;
  }

  const btn = $("#paySubmit");
  const originalLabel = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = "Sending M-Pesa prompt…";

  const res = await api("/api/payments/stk-push/", {
    method: "POST",
    body: {
      purpose: ctx.purpose,
      amount: ctx.amount,
      phone_number: phoneRaw,
      property_id: ctx.property ? ctx.property.id : null,
      description,
    },
  });

  btn.disabled = false;
  btn.innerHTML = originalLabel;

  // 202 = new transaction accepted for processing;
  // 200 = an identical transaction is already active — keep polling it.
  if (res.status === 202 || res.status === 200) {
    payState.lastPayment = res.data;
    startPolling(res.data);
    return;
  }

  // 503 = Daraja rejected/unreachable — a failed transaction is returned
  // so the user sees the receipt and can retry.
  if (res.status === 503 && res.data?.transaction) {
    payState.lastPayment = res.data.transaction;
    showPayFailed(
      res.data.transaction,
      "Payment could not be started",
      true,
      res.data?.errors?.detail || res.data.transaction.failure_message
    );
    return;
  }

  const messages = res.data?.errors
    ? Object.values(res.data.errors).flat().join(" ")
    : "Could not start the payment. Please try again.";
  showError(messages);
}

function stopPolling() {
  if (payState.pollTimer) {
    clearInterval(payState.pollTimer);
    payState.pollTimer = null;
  }
}

/* Poll the authenticated status endpoint. Never marks a payment
   successful locally — only the server-reported status is shown. */
function startPolling(payment) {
  stopPolling();
  payState.lastPayment = payment;
  $("#payProcessingPhone").textContent = formatPhone(payment.phone_number);
  $("#payProcessingAmount").textContent = formatKSh(payment.amount);
  showPayStep("payStepProcessing");
  payState.pollCount = 0;

  payState.pollTimer = setInterval(async () => {
    payState.pollCount += 1;
    const { ok, data } = await api(`/api/payments/${payment.reference}/status/`);

    if (!ok || !data) {
      stopPolling();
      showPayFailed(
        payState.lastPayment,
        "Could not confirm payment",
        false,
        "We couldn't reach the server to confirm your payment. Check your M-Pesa messages or your payment history in the dashboard — do not pay twice."
      );
      return;
    }

    if (data.status === "successful") {
      stopPolling();
      showPaySuccess(data);
      return;
    }
    if (["failed", "cancelled", "expired"].includes(data.status)) {
      stopPolling();
      showPayFailed(data, failureTitle(data.status), true);
      return;
    }
    if (payState.pollCount >= payState.maxPolls) {
      stopPolling();
      showPayFailed(
        data,
        "Still processing",
        false,
        "The payment is taking longer than usual. Check your M-Pesa messages — you can follow the status anytime in your dashboard. Please don't pay twice."
      );
    }
  }, payState.pollInterval);
}

function failureTitle(status) {
  return {
    failed: "Payment failed",
    cancelled: "Payment cancelled",
    expired: "Payment expired",
  }[status] || "Payment not completed";
}

function receiptHtml(p) {
  const rows = [["Purpose", payPurposeLabel(p.purpose)]];
  if (p.property_title) rows.push(["Property", p.property_title]);
  rows.push(
    ["Amount", formatKSh(p.amount)],
    ["Reference", p.reference],
    ["M-Pesa receipt", p.mpesa_receipt_number || "—"],
    ["Phone", formatPhone(p.phone_number)],
    ["Date", p.created ? new Date(p.created).toLocaleString("en-KE") : "—"]
  );
  return rows
    .map(([k, v]) => `<div class="pay-receipt-row"><span>${escHtml(k)}</span><strong>${escHtml(v)}</strong></div>`)
    .join("");
}

function showPaySuccess(p) {
  $("#payReceipt").innerHTML =
    `<div class="pay-receipt-row highlight"><span>Status</span><strong>Payment successful ✓</strong></div>` +
    receiptHtml(p);
  showPayStep("payStepSuccess");
  toast(
    `Payment of ${formatKSh(p.amount)} successful${p.mpesa_receipt_number ? ` — M-Pesa receipt ${p.mpesa_receipt_number}` : ""}.`,
    "success",
    5000
  );
}

function showPayFailed(p, title, canRetry, message) {
  $("#payFailedTitle").textContent = title || "Payment not completed";
  $("#payFailedMessage").textContent =
    message || p.failure_message || "The payment was not completed.";
  $("#payFailedReceipt").innerHTML =
    `<div class="pay-receipt-row"><span>Status</span><strong style="color:var(--color-accent)">${escHtml(p.status)}</strong></div>` +
    receiptHtml(p);
  $("#payRetry").style.display = canRetry ? "" : "none";
  showPayStep("payStepFailed");
}

function initPayments() {
  loadPaymentConfig();

  const form = $("#payForm");
  if (form) form.addEventListener("submit", initiatePayment);

  $("#payDone")?.addEventListener("click", () => closeModal("paymentModal"));
  $("#payFailedDone")?.addEventListener("click", () => closeModal("paymentModal"));

  $("#payRetry")?.addEventListener("click", () => {
    if (payState.current) openPaymentModal(payState.current);
  });

  $("#payCancelWait")?.addEventListener("click", () => {
    stopPolling();
    showPayFailed(
      payState.lastPayment,
      "Prompt not received",
      true,
      "The M-Pesa prompt didn't arrive. Check that the phone number is correct and that the phone has M-Pesa registered. You can try again — you will only be charged if you approve the prompt on your phone."
    );
  });

  // Delegate all payment CTA clicks (property modal + dashboard).
  document.addEventListener("click", (e) => {
    const cta = e.target.closest("[data-pay-purpose]");
    if (!cta) return;
    if (!getCurrentUser() || !getToken()) {
      openAuth("login");
      toast("Log in to pay with M-Pesa.", "error");
      return;
    }
    const propertyId = cta.dataset.payPropertyId
      ? Number(cta.dataset.payPropertyId)
      : null;
    openPaymentModal({
      purpose: cta.dataset.payPurpose,
      amount: Number(cta.dataset.payAmount),
      property: propertyId ? payState.propertiesById[propertyId] || null : null,
    });
  });
}

/* ---------- Init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initReveal();
  initModals();
  initAuth();
  initChat();
  initExploreFilters();
  initCountySelects();
  initGlobalDelegation();
  initPayments();
  initMapSearch();
  loadMe();
  loadFeatured();
  loadRecent();
  loadLocations();
  loadReviewsSection();
  loadExplore();
});
