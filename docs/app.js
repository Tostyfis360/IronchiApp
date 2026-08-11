const SOURCE_LABELS = {
  jooble: "Jooble",
  infojobs: "InfoJobs",
  jobtoday: "Job Today",
  indeed: "Indeed",
  mango: "Mango",
};

const state = {
  jobs: [],
  filtered: [],
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
    renderStatus(await statusResp.value.json());
  } else {
    el("status-line").textContent =
      "Aún no hay datos: la primera ejecución automática todavía no se ha completado.";
  }

  populateFilters();
  applyFilters();
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

function populateFilters() {
  const citySelect = el("filter-city");
  const brandSelect = el("filter-brand");
  const sourceSelect = el("filter-source");

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
  const city = el("filter-city").value;
  const contract = el("filter-contract").value;
  const brand = el("filter-brand").value;
  const source = el("filter-source").value;
  const sortBy = el("sort").value;

  let jobs = state.jobs.filter((job) => {
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
}

function jobCard(job) {
  const a = document.createElement("a");
  a.className = "job-card";
  a.href = job.url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";

  const companyBits = [escapeHtml(job.company)];
  if (job.brand_tier === "priority") {
    const brandLabel =
      job.brand_name && job.brand_name !== job.company ? ` · ${escapeHtml(job.brand_name)}` : "";
    companyBits.push(`<span class="star">★</span>${brandLabel}`);
  }

  const tags = [];
  if (job.contract_type === "full") {
    tags.push(`<span class="tag tag-full">Jornada completa</span>`);
  } else if (job.contract_type === "part") {
    tags.push(`<span class="tag tag-part">Media jornada</span>`);
  }
  tags.push(`<span class="tag tag-city">${escapeHtml(job.city)}</span>`);

  a.innerHTML = `
    <div class="card-top">
      <div>
        <p class="job-title">${escapeHtml(job.title)}</p>
        <p class="job-company">${companyBits.join(" ")}</p>
      </div>
      ${job.is_new ? `<span class="new-tag" title="Nueva desde la última actualización"></span>` : ""}
    </div>
    <div class="tag-row">${tags.join("")}</div>
    <div class="card-meta">
      <span class="place">${escapeHtml(job.location_raw || job.city)} · ${SOURCE_LABELS[job.source] || job.source}</span>
      <span class="salary">${job.salary_raw ? escapeHtml(job.salary_raw) : ""}</span>
    </div>
  `;
  return a;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
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

["search", "filter-city", "filter-contract", "filter-brand", "filter-source", "sort"].forEach(
  (id) => {
    const node = el(id);
    node.addEventListener(id === "search" ? "input" : "change", applyFilters);
  }
);

loadData();
