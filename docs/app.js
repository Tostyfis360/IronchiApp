const SOURCE_LABELS = {
  jooble: "Jooble",
  infojobs: "InfoJobs",
  jobtoday: "Job Today",
  indeed: "Indeed",
  mango: "Mango",
};

const STORAGE_KEY = "empleoModaState.v1";

const state = {
  jobs: [],
  filtered: [],
  categories: [],
  interested: [],
  discarded: [],
  discoverQueue: [],
  discoverAnimating: false,
  mode: "search",
};

const el = (id) => document.getElementById(id);

function stripAccents(text) {
  return (text || "").normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function normalizeText(text) {
  return stripAccents(text).toLowerCase();
}

function parseSalaryValue(raw) {
  if (!raw) return null;
  const numbers = raw.replace(/\./g, "").match(/\d+(?:,\d+)?/g);
  if (!numbers) return null;
  const values = numbers.map((n) => parseFloat(n.replace(",", ".")));
  return Math.max(...values);
}

function timeValue(job) {
  const raw = job.posted_date || job.first_seen_at;
  const t = raw ? Date.parse(raw) : NaN;
  return Number.isNaN(t) ? 0 : t;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

/* ---------------------------------------------------------------------
   Persistencia local (interesantes / descartadas)
   Solo vive en este navegador/dispositivo — no hay servidor detrás.
--------------------------------------------------------------------- */

function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { interested: [], discarded: [] };
    const parsed = JSON.parse(raw);
    return {
      interested: Array.isArray(parsed.interested) ? parsed.interested : [],
      discarded: Array.isArray(parsed.discarded) ? parsed.discarded : [],
    };
  } catch {
    return { interested: [], discarded: [] };
  }
}

function savePersisted() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ interested: state.interested, discarded: state.discarded })
    );
  } catch {
    /* localStorage no disponible (modo privado, cuota...): la sesión sigue funcionando */
  }
}

function jobById(id) {
  return state.jobs.find((j) => j.id === id);
}

/* ---------------------------------------------------------------------
   Carga de datos
--------------------------------------------------------------------- */

async function loadData() {
  const [jobsResp, statusResp] = await Promise.allSettled([
    fetch("data/jobs.json", { cache: "no-store" }),
    fetch("data/status.json", { cache: "no-store" }),
  ]);

  if (jobsResp.status === "fulfilled" && jobsResp.value.ok) {
    state.jobs = await jobsResp.value.json();
  } else {
    state.jobs = [];
  }

  if (statusResp.status === "fulfilled" && statusResp.value.ok) {
    const status = await statusResp.value.json();
    state.categories = status.categories || [];
    renderStatus(status);
  } else {
    el("status-line").textContent =
      "Aún no hay datos: la primera ejecución automática todavía no se ha completado.";
  }

  const persisted = loadPersisted();
  state.interested = persisted.interested;
  state.discarded = persisted.discarded;

  populateFilters();
  applyFilters();
  updateListCounts();
  if (state.mode === "discover") refreshDiscoverQueue();
}

function renderStatus(status) {
  const generated = status.generated_at
    ? new Date(status.generated_at).toLocaleString("es-ES", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "—";

  const sourceBits = Object.entries(status.sources || {}).map(([name, info]) => {
    const label = SOURCE_LABELS[name] || name;
    if (info.ok === true) return `${label} ✓ (${info.count})`;
    if (info.ok === null) return `${label} —`;
    return `${label} ⚠`;
  });

  el("status-line").textContent =
    `Última actualización: ${generated} · ${status.total_jobs ?? 0} ofertas` +
    (status.new_jobs ? ` (${status.new_jobs} nuevas)` : "") +
    ` · ${sourceBits.join(" · ")}`;
}

/* ---------------------------------------------------------------------
   Vista "Buscar": filtros + cuadrícula
--------------------------------------------------------------------- */

function populateFilters() {
  const categorySelect = el("filter-category");
  const citySelect = el("filter-city");
  const brandSelect = el("filter-brand");
  const sourceSelect = el("filter-source");

  // Preferimos la lista de categorías configuradas (status.json) para que el
  // filtro las muestre todas aunque una tenga 0 resultados ahora mismo; si no
  // hay status.json disponible, las deducimos de las ofertas cargadas.
  const categories = state.categories.length
    ? state.categories.map((c) => [c.key, c.label])
    : [
        ...new Map(
          state.jobs.map((j) => [j.category || "moda", j.category_label || "Moda y retail"])
        ),
      ];
  categories.sort((a, b) => a[1].localeCompare(b[1]));
  for (const [value, label] of categories) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    categorySelect.appendChild(opt);
  }

  const cities = [...new Set(state.jobs.map((j) => j.city))].sort();
  for (const city of cities) {
    const opt = document.createElement("option");
    opt.value = city;
    opt.textContent = city;
    citySelect.appendChild(opt);
  }

  const brands = [
    ...new Set(
      state.jobs
        .filter((j) => j.brand_tier === "priority")
        .map((j) => j.brand_name || j.company)
    ),
  ].sort();
  for (const brand of brands) {
    const opt = document.createElement("option");
    opt.value = brand;
    opt.textContent = brand;
    brandSelect.appendChild(opt);
  }
  const otherOpt = document.createElement("option");
  otherOpt.value = "__otras__";
  otherOpt.textContent = "Otras marcas";
  brandSelect.appendChild(otherOpt);

  const sources = [...new Set(state.jobs.map((j) => j.source))].sort();
  for (const source of sources) {
    const opt = document.createElement("option");
    opt.value = source;
    opt.textContent = SOURCE_LABELS[source] || source;
    sourceSelect.appendChild(opt);
  }
}

function applyFilters() {
  const query = normalizeText(el("search").value.trim());
  const category = el("filter-category").value;
  const city = el("filter-city").value;
  const contract = el("filter-contract").value;
  const brand = el("filter-brand").value;
  const source = el("filter-source").value;
  const sortBy = el("sort").value;

  let jobs = state.jobs.filter((job) => {
    if (state.discarded.includes(job.id)) return false;
    if (category && (job.category || "moda") !== category) return false;
    if (city && job.city !== city) return false;
    if (contract && job.contract_type !== contract) return false;
    if (source && job.source !== source) return false;
    if (brand) {
      if (brand === "__otras__" && job.brand_tier === "priority") return false;
      if (brand !== "__otras__" && (job.brand_name || job.company) !== brand) return false;
    }
    if (query) {
      const haystack = normalizeText(`${job.title} ${job.company}`);
      if (!haystack.includes(query)) return false;
    }
    return true;
  });

  jobs = jobs.slice().sort((a, b) => {
    if (sortBy === "date") return timeValue(b) - timeValue(a);
    if (sortBy === "salary") {
      const sa = parseSalaryValue(a.salary_raw) ?? -1;
      const sb = parseSalaryValue(b.salary_raw) ?? -1;
      return sb - sa;
    }
    return (b.score || 0) - (a.score || 0);
  });

  state.filtered = jobs;
  renderJobs();
  if (state.mode === "discover") refreshDiscoverQueue();
}

function tagsFor(job) {
  const tags = [];
  tags.push(
    `<span class="tag tag-category">${escapeHtml(job.category_label || "Moda y retail")}</span>`
  );
  if (job.contract_type === "full") {
    tags.push(`<span class="tag tag-full">Jornada completa</span>`);
  } else if (job.contract_type === "part") {
    tags.push(`<span class="tag tag-part">Media jornada</span>`);
  }
  tags.push(`<span class="tag tag-city">${escapeHtml(job.city)}</span>`);
  return tags.join("");
}

function companyLineFor(job) {
  const bits = [escapeHtml(job.company)];
  if (job.brand_tier === "priority") {
    const brandLabel =
      job.brand_name && job.brand_name !== job.company ? ` · ${escapeHtml(job.brand_name)}` : "";
    bits.push(`<span class="star">★</span>${brandLabel}`);
  }
  return bits.join(" ");
}

function dismissJob(jobId) {
  if (!state.discarded.includes(jobId)) state.discarded.push(jobId);
  const interestedIdx = state.interested.indexOf(jobId);
  if (interestedIdx !== -1) state.interested.splice(interestedIdx, 1);
  savePersisted();
  updateListCounts();
  applyFilters();
}

function jobCard(job) {
  const card = document.createElement("div");
  card.className = "job-card";

  card.innerHTML = `
    <a class="job-card-link" href="${job.url}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(job.title)}"></a>
    <button type="button" class="card-dismiss" title="Descartar, no volver a mostrar">✕</button>
    <div class="card-body">
      <div class="card-top">
        <div>
          <p class="job-title">${escapeHtml(job.title)}</p>
          <p class="job-company">${companyLineFor(job)}</p>
        </div>
        ${job.is_new ? `<span class="new-tag" title="Nueva desde la última actualización"></span>` : ""}
      </div>
      <div class="tag-row">${tagsFor(job)}</div>
      <div class="card-meta">
        <span class="place">${escapeHtml(job.location_raw || job.city)} · ${SOURCE_LABELS[job.source] || job.source}</span>
        <span class="salary">${job.salary_raw ? escapeHtml(job.salary_raw) : ""}</span>
      </div>
    </div>
  `;

  card.querySelector(".card-dismiss").addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dismissJob(job.id);
  });

  return card;
}

function renderJobs() {
  const grid = el("job-grid");
  grid.innerHTML = "";
  const emptyState = el("empty-state");

  if (state.filtered.length === 0) {
    emptyState.hidden = false;
  } else {
    emptyState.hidden = true;
    const fragment = document.createDocumentFragment();
    for (const job of state.filtered) fragment.appendChild(jobCard(job));
    grid.appendChild(fragment);
  }

  el("result-count").textContent = `${state.filtered.length} oferta${
    state.filtered.length === 1 ? "" : "s"
  } encontrada${state.filtered.length === 1 ? "" : "s"}`;
}

/* ---------------------------------------------------------------------
   Vista "Descubrir": pila deslizable
--------------------------------------------------------------------- */

function refreshDiscoverQueue() {
  state.discoverQueue = state.filtered.filter(
    (j) => !state.interested.includes(j.id) && !state.discarded.includes(j.id)
  );
  renderStack();
}

function updateListCounts() {
  el("count-interested").textContent = state.interested.length;
  el("count-discarded").textContent = state.discarded.length;
}

function buildStackCard(job, isTop) {
  const card = document.createElement("div");
  card.className = "stack-card " + (isTop ? "is-top" : "is-peek");
  card.innerHTML = `
    <div class="card-top">
      <div>
        <p class="job-title">${escapeHtml(job.title)}</p>
        <p class="job-company">${companyLineFor(job)}</p>
      </div>
      ${job.is_new ? `<span class="new-tag" title="Nueva desde la última actualización"></span>` : ""}
    </div>
    <div class="tag-row">${tagsFor(job)}</div>
    <div class="card-meta">
      <span class="place">${escapeHtml(job.location_raw || job.city)} · ${SOURCE_LABELS[job.source] || job.source}</span>
      <span class="salary">${job.salary_raw ? escapeHtml(job.salary_raw) : ""}</span>
    </div>
    ${isTop ? `<span class="swipe-flag swipe-flag-like">Interesa</span><span class="swipe-flag swipe-flag-skip">Descartar</span>` : ""}
  `;
  return card;
}

function renderStack() {
  const stackEl = el("discover-stack");
  const emptyEl = el("discover-empty");
  const actionsEl = el("discover-actions");
  stackEl.innerHTML = "";

  if (state.discoverQueue.length === 0) {
    emptyEl.hidden = false;
    actionsEl.hidden = true;
    return;
  }
  emptyEl.hidden = true;
  actionsEl.hidden = false;

  const [top, next] = state.discoverQueue;
  if (next) stackEl.appendChild(buildStackCard(next, false));
  const topEl = buildStackCard(top, true);
  stackEl.appendChild(topEl);
  attachDrag(topEl, top.id);
}

function decide(jobId, decision) {
  if (decision === "interested" && !state.interested.includes(jobId)) {
    state.interested.push(jobId);
  } else if (decision === "discarded" && !state.discarded.includes(jobId)) {
    state.discarded.push(jobId);
  }
  savePersisted();
  updateListCounts();
  state.discoverQueue = state.discoverQueue.filter((j) => j.id !== jobId);
  renderStack();
}

function flingCard(cardEl, jobId, decision) {
  if (state.discoverAnimating) return;
  state.discoverAnimating = true;
  const dir = decision === "interested" ? 1 : -1;
  cardEl.style.transition = "transform 0.35s ease, opacity 0.35s ease";
  cardEl.style.transform = `translate(${dir * 640}px, -40px) rotate(${dir * 22}deg)`;
  cardEl.style.opacity = "0";
  window.setTimeout(() => {
    state.discoverAnimating = false;
    decide(jobId, decision);
  }, 260);
}

function attachDrag(cardEl, jobId) {
  const likeFlag = cardEl.querySelector(".swipe-flag-like");
  const skipFlag = cardEl.querySelector(".swipe-flag-skip");
  let startX = 0;
  let startY = 0;
  let dx = 0;
  let dragging = false;

  const onPointerDown = (e) => {
    if (state.discoverAnimating) return;
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    cardEl.style.transition = "none";
    cardEl.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e) => {
    if (!dragging) return;
    dx = e.clientX - startX;
    const dy = (e.clientY - startY) * 0.15;
    cardEl.style.transform = `translate(${dx}px, ${dy}px) rotate(${dx / 18}deg)`;
    const strength = Math.min(Math.abs(dx) / 100, 1);
    if (dx > 0) {
      likeFlag.style.opacity = strength;
      skipFlag.style.opacity = 0;
    } else {
      skipFlag.style.opacity = strength;
      likeFlag.style.opacity = 0;
    }
  };

  const onPointerUp = () => {
    if (!dragging) return;
    dragging = false;
    if (Math.abs(dx) > 110) {
      flingCard(cardEl, jobId, dx > 0 ? "interested" : "discarded");
    } else {
      cardEl.style.transition = "transform 0.25s ease";
      cardEl.style.transform = "";
      likeFlag.style.opacity = 0;
      skipFlag.style.opacity = 0;
    }
    dx = 0;
  };

  cardEl.addEventListener("pointerdown", onPointerDown);
  cardEl.addEventListener("pointermove", onPointerMove);
  cardEl.addEventListener("pointerup", onPointerUp);
  cardEl.addEventListener("pointercancel", onPointerUp);
}

function currentTopCard() {
  return document.querySelector("#discover-stack .stack-card.is-top");
}

/* ---------------------------------------------------------------------
   Listas laterales (interesantes / descartadas)
--------------------------------------------------------------------- */

function openSideList(kind) {
  const list = kind === "interested" ? state.interested : state.discarded;
  const titleText = kind === "interested" ? "Interesantes" : "Descartadas";
  el("side-list-title").textContent = `${titleText} (${list.length})`;
  el("side-list-clear").hidden = list.length === 0;

  const itemsEl = el("side-list-items");
  const emptyEl = el("side-list-empty");
  itemsEl.innerHTML = "";

  const jobs = list.map(jobById).filter(Boolean);
  if (jobs.length === 0) {
    emptyEl.hidden = false;
    emptyEl.textContent =
      kind === "interested"
        ? "Aún no has marcado ninguna oferta como interesante."
        : "No has descartado ninguna oferta.";
  } else {
    emptyEl.hidden = true;
    for (const job of jobs) itemsEl.appendChild(sideItem(job, kind));
  }

  el("discover-stack").hidden = true;
  el("discover-actions").hidden = true;
  el("discover-empty").hidden = true;
  el("discover-lists").hidden = true;
  el("side-list").hidden = false;
}

function closeSideList() {
  el("side-list").hidden = true;
  el("discover-lists").hidden = false;
  refreshDiscoverQueue();
}

function sideItem(job, kind) {
  const row = document.createElement("div");
  row.className = "side-item";

  const link = document.createElement("a");
  link.href = job.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.innerHTML = `
    <p class="job-title">${escapeHtml(job.title)}</p>
    <p class="job-company">${companyLineFor(job)}</p>
  `;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = kind === "interested" ? "Quitar" : "Restaurar";
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    const list = kind === "interested" ? state.interested : state.discarded;
    const idx = list.indexOf(job.id);
    if (idx !== -1) list.splice(idx, 1);
    savePersisted();
    updateListCounts();
    openSideList(kind);
  });

  row.appendChild(link);
  row.appendChild(btn);
  return row;
}

/* ---------------------------------------------------------------------
   Cambio de modo (Buscar / Descubrir)
--------------------------------------------------------------------- */

function setMode(mode) {
  state.mode = mode;
  for (const btn of document.querySelectorAll(".mode-btn")) {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", String(active));
  }
  el("view-search").hidden = mode !== "search";
  el("view-discover").hidden = mode !== "discover";
  if (mode === "discover") {
    el("side-list").hidden = true;
    el("discover-lists").hidden = false;
    refreshDiscoverQueue();
  }
}

/* ---------------------------------------------------------------------
   Cableado de eventos
--------------------------------------------------------------------- */

["search", "filter-category", "filter-city", "filter-contract", "filter-brand", "filter-source", "sort"].forEach(
  (id) => {
    const node = el(id);
    node.addEventListener(id === "search" ? "input" : "change", applyFilters);
  }
);

for (const btn of document.querySelectorAll(".mode-btn")) {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
}

el("discover-skip").addEventListener("click", () => {
  const top = currentTopCard();
  if (top && state.discoverQueue[0]) flingCard(top, state.discoverQueue[0].id, "discarded");
});
el("discover-like").addEventListener("click", () => {
  const top = currentTopCard();
  if (top && state.discoverQueue[0]) flingCard(top, state.discoverQueue[0].id, "interested");
});

el("show-interested").addEventListener("click", () => openSideList("interested"));
el("show-discarded").addEventListener("click", () => openSideList("discarded"));
el("side-list-back").addEventListener("click", closeSideList);
el("side-list-clear").addEventListener("click", () => {
  const kind = el("side-list-title").textContent.startsWith("Interesantes")
    ? "interested"
    : "discarded";
  if (kind === "interested") state.interested = [];
  else state.discarded = [];
  savePersisted();
  updateListCounts();
  openSideList(kind);
});

setMode("search");
loadData();
