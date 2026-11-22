/* ET-tomo — tasks: general / missing wedge / sparse view; all algorithms */

(function () {
  "use strict";

  const TASKS = ["general", "missing wedge", "sparse view"];

  const METRIC_LABELS = {
    protocol_affine_ssim: "Affine SSIM",
    protocol_affine_cc: "Affine CC",
    protocol_wedge_out_cc: "Wedge-out CC",
    protocol_wedge_in_cc: "Wedge-in CC",
    protocol_fsc_res_0p5_px: "FSC 0.5 (px)",
    protocol_fsc_res_0p143_px: "FSC 0.143 (px)",
    psnr: "PSNR (dB)",
    ssim: "SSIM",
    mse: "MSE",
    r2: "R²",
    dice: "Dice",
    elongation: "Elongation",
    runtime_s: "Runtime",
    image: "Image",
    method_group: "Category",
    status: "Status",
  };

  const ALG_COLORS = {
    wbp: "#06b6d4",
    "astra-fbp": "#4C78A8",
    "astra-sirt": "#0891b2",
    "tigre-sirt": "#10b981",
    genfire: "#8b5cf6",
    sirt: "#64748b",
    isonet: "#E89A3C",
    deepdewedge: "#0284c7",
    wucon: "#7c3aed",
    dart: "#f59e0b",
    "tvr-dart": "#d97706",
    tvm: "#94a3b8",
  };

  const DEFAULT_PRIMARY = {
    general: [
      "protocol_affine_ssim",
      "protocol_affine_cc",
      "ssim",
      "psnr",
      "dice",
    ],
    "missing wedge": [
      "protocol_affine_ssim",
      "protocol_affine_cc",
      "protocol_wedge_out_cc",
      "protocol_wedge_in_cc",
      "ssim",
      "psnr",
    ],
    "sparse view": [
      "protocol_affine_ssim",
      "protocol_affine_cc",
      "ssim",
      "psnr",
      "dice",
    ],
  };

  /** Task claim columns (default board + best tags). */
  const CLAIM_BY_TASK = {
    general: ["protocol_affine_ssim", "protocol_affine_cc", "dice"],
    "missing wedge": [
      "protocol_wedge_in_cc",
      "protocol_wedge_out_cc",
      "protocol_affine_cc",
      "protocol_affine_ssim",
    ],
    "sparse view": ["protocol_affine_ssim", "protocol_affine_cc", "dice"],
  };

  const PROTOCOL_KEYS = new Set([
    "protocol_affine_ssim",
    "protocol_affine_cc",
    "protocol_wedge_out_cc",
    "protocol_wedge_in_cc",
    "protocol_fsc_res_0p5_px",
    "protocol_fsc_res_0p143_px",
  ]);

  /** Never tag best — even as provisional claim. */
  const NEVER_BEST = new Set([
    "runtime_s",
    "psnr",
    "mse",
    "r2",
    "image",
    "status",
    "method_group",
  ]);

  /** When protocol_* is not in the cohort yet, board still needs a claim. */
  const PROVISIONAL_CLAIM = {
    general: ["ssim", "dice"],
    "missing wedge": ["ssim"],
    "sparse view": ["ssim", "dice"],
  };

  const HIGHER = new Set([
    "psnr",
    "ssim",
    "r2",
    "dice",
    "protocol_affine_ssim",
    "protocol_affine_cc",
    "protocol_wedge_in_cc",
    "protocol_wedge_out_cc",
  ]);
  const LOWER = new Set([
    "mse",
    "fsc_resolution_px",
    "edge_rise_px",
    "hausdorff95_px",
    "porosity_abs_error",
    "protocol_fsc_res_0p5_px",
    "protocol_fsc_res_0p143_px",
    "runtime_s",
  ]);

  const TASK_HINT = {
    general:
      "Claim: affine SSIM/CC (Dice for grey prior) at SM_70 @ 1°. Best is tagged within each method family — not a cross-family champion.",
    "missing wedge":
      "Claim: wedge-in/out CC (+ affine CC). Sweep tilt range at 1°. Best within family on claim columns only.",
    "sparse view":
      "Claim: affine SSIM/CC at SM_70 while varying step (1°/2°/4°). Best within family on claim columns only.",
  };

  const state = {
    data: null,
    task: "general",
    dataset: "SM_70",
    step: 1,
    sortKey: null,
    sortDir: "desc",
    /** null = task defaults; Set of metric keys when user filters */
    visibleMetrics: null,
    explorerTask: "general",
    explorerDataset: "SM_70",
    explorerMetric: "protocol_affine_ssim",
  };

  function $(id) {
    return document.getElementById(id);
  }

  function labelMetric(k) {
    return METRIC_LABELS[k] || k;
  }

  function fmt(v) {
    if (v == null || v === "") return "—";
    if (typeof v === "number") {
      if (!Number.isFinite(v)) return "—";
      return Math.abs(v) >= 100 ? v.toFixed(2) : v.toFixed(4);
    }
    return String(v);
  }

  function colorFor(name) {
    return ALG_COLORS[name] || "#64748b";
  }

  function primary() {
    return (state.data && state.data.primary_by_task) || DEFAULT_PRIMARY;
  }

  function rows() {
    return (state.data && state.data.rows) || [];
  }

  function conditions() {
    return (state.data && state.data.conditions) || [];
  }

  function datasetMenu() {
    const menu = (state.data && state.data.dataset_menu) || [];
    if (menu.length) return menu;
    const map = {};
    rows().forEach((r) => {
      map[r.dataset] = {
        id: r.dataset,
        tilt_abs: r.tilt_abs,
        label: r.dataset,
      };
    });
    return Object.values(map).sort((a, b) => (b.tilt_abs || 0) - (a.tilt_abs || 0));
  }

  function rowStep(r) {
    if (r.angular_step_deg != null) return Number(r.angular_step_deg);
    const c = conditions().find((x) => x.id === r.condition_id);
    return c ? Number(c.angular_step_deg) || 1 : 1;
  }

  /** All algorithms for the active task × condition. */
  function filteredRows() {
    return rows().filter((r) => {
      if (state.task === "general") {
        return r.dataset === "SM_70" && rowStep(r) === 1;
      }
      if (state.task === "missing wedge") {
        return r.dataset === state.dataset && rowStep(r) === 1;
      }
      // sparse view
      return r.dataset === "SM_70" && rowStep(r) === Number(state.step);
    });
  }

  function initTheme() {
    const stored = localStorage.getItem("et-tomo-theme");
    let theme = stored;
    if (!theme) {
      theme = window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
    }
    document.documentElement.setAttribute("data-theme", theme);
    $("theme-toggle").addEventListener("click", () => {
      const next =
        document.documentElement.getAttribute("data-theme") === "dark"
          ? "light"
          : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("et-tomo-theme", next);
    });
  }

  function initNavSpy() {
    const links = [...document.querySelectorAll(".nav-links a[data-nav]")];
    const sections = links
      .map((a) => document.getElementById(a.dataset.nav))
      .filter(Boolean);
    function setActive(id) {
      links.forEach((a) => a.classList.toggle("active", a.dataset.nav === id));
    }
    setActive("home");
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-35% 0px -45% 0px", threshold: [0.1, 0.35, 0.6] }
    );
    sections.forEach((s) => obs.observe(s));
  }

  function parseHash() {
    const raw = (location.hash || "").replace(/^#/, "");
    if (!raw) return;
    const map = {};
    raw.split("&").forEach((p) => {
      const [k, v] = p.split("=");
      if (k) map[k] = decodeURIComponent(v || "");
    });
    if (map.task && TASKS.includes(map.task)) state.task = map.task;
    if (map.dataset) state.dataset = map.dataset;
    if (map.step) state.step = Number(map.step) || 1;
    if (map.sort) state.sortKey = map.sort;
  }

  function writeHash() {
    const bits = [
      "leaderboard",
      `task=${encodeURIComponent(state.task)}`,
      `dataset=${encodeURIComponent(state.dataset)}`,
      `step=${encodeURIComponent(String(state.step))}`,
    ];
    if (state.sortKey) bits.push(`sort=${encodeURIComponent(state.sortKey)}`);
    history.replaceState(null, "", `#${bits.join("&")}`);
  }

  function metricValue(row, key) {
    if (key === "runtime_s") {
      const ex = row.execution || {};
      const v = ex.runtime_seconds ?? ex.wall_time_s;
      return typeof v === "number" ? v : null;
    }
    if (key === "method_group") return row.method_group || null;
    const m = row.metrics || {};
    return m[key] != null ? m[key] : null;
  }

  function claimKeys() {
    return CLAIM_BY_TASK[state.task] || CLAIM_BY_TASK.general;
  }

  function hasProtocolMetrics(list) {
    const pool = list || rows();
    return pool.some((r) =>
      Object.keys(r.metrics || {}).some((k) => PROTOCOL_KEYS.has(k))
    );
  }

  /** Protocol claim when audited; else provisional SSIM/Dice so the board is usable. */
  function activeClaimKeys(list) {
    const pool = list || filteredRows();
    if (hasProtocolMetrics(pool)) {
      return claimKeys();
    }
    return PROVISIONAL_CLAIM[state.task] || PROVISIONAL_CLAIM.general;
  }

  function isClaimMetric(metric, list) {
    if (NEVER_BEST.has(metric)) return false;
    return activeClaimKeys(list).includes(metric);
  }

  function bestInPool(metric, values) {
    const finite = Object.entries(values).filter(
      ([, v]) => typeof v === "number" && Number.isFinite(v)
    );
    if (!finite.length) return new Set();
    let best;
    if (HIGHER.has(metric)) best = Math.max(...finite.map(([, v]) => v));
    else if (LOWER.has(metric)) best = Math.min(...finite.map(([, v]) => v));
    else return new Set();
    return new Set(
      finite.filter(([, v]) => Math.abs(v - best) < 1e-12).map(([k]) => k)
    );
  }

  /** Best only on claim metrics, and only within each method family. */
  function bestFor(metric, rowList) {
    if (!isClaimMetric(metric, rowList)) return new Set();
    const winners = new Set();
    // Dice / grey-prior morphology: only grey prior family.
    if (metric === "dice") {
      const gp = rowList.filter((r) => r.method_group === "grey prior");
      const col = {};
      gp.forEach((r) => {
        const v = metricValue(r, metric);
        if (typeof v === "number") col[r.algorithm] = v;
      });
      return bestInPool(metric, col);
    }
    // Wedge in/out: claim for self-supervised on missing-wedge task.
    if (
      state.task === "missing wedge" &&
      (metric === "protocol_wedge_in_cc" || metric === "protocol_wedge_out_cc")
    ) {
      const ss = rowList.filter((r) => r.method_group === "self-supervised");
      const col = {};
      ss.forEach((r) => {
        const v = metricValue(r, metric);
        if (typeof v === "number") col[r.algorithm] = v;
      });
      return bestInPool(metric, col);
    }
    // Affine / provisional SSIM: within each family.
    const groups = {};
    rowList.forEach((r) => {
      const g = r.method_group || "other";
      (groups[g] = groups[g] || []).push(r);
    });
    Object.values(groups).forEach((list) => {
      const col = {};
      list.forEach((r) => {
        const v = metricValue(r, metric);
        if (typeof v === "number") col[r.algorithm] = v;
      });
      bestInPool(metric, col).forEach((a) => winners.add(a));
    });
    return winners;
  }

  function availableMetricKeys(list) {
    const preferred = primary()[state.task] || DEFAULT_PRIMARY.general;
    const present = (k) => list.some((r) => metricValue(r, k) != null);
    const hasProto = hasProtocolMetrics(list);
    const keys = [];
    activeClaimKeys(list).forEach((k) => {
      if (PROTOCOL_KEYS.has(k) && !hasProto) return;
      if (present(k) && !keys.includes(k)) keys.push(k);
    });
    preferred.forEach((k) => {
      if (PROTOCOL_KEYS.has(k) && !hasProto) return;
      if (present(k) && !keys.includes(k)) keys.push(k);
    });
    [
      "ssim",
      "psnr",
      "r2",
      "dice",
      "mse",
      "elongation",
      "fsc_resolution_px",
      "hausdorff95_px",
      "porosity_abs_error",
    ].forEach((k) => {
      if (present(k) && !keys.includes(k)) keys.push(k);
    });
    ["runtime_s", "image", "status"].forEach((k) => {
      if (!keys.includes(k)) keys.push(k);
    });
    Object.keys(
      list.reduce((acc, r) => Object.assign(acc, r.metrics || {}), {})
    ).forEach((k) => {
      if (!keys.includes(k) && present(k)) keys.push(k);
    });
    return keys;
  }

  /** Claim columns for the active task (+ status). No runtime. */
  function coreMetricKeys(list) {
    const all = availableMetricKeys(list);
    const core = [];
    activeClaimKeys(list).forEach((k) => {
      if (all.includes(k) && !core.includes(k)) core.push(k);
    });
    if (!core.length) {
      ["ssim", "dice"].forEach((k) => {
        if (all.includes(k) && !core.includes(k)) core.push(k);
      });
    }
    if (all.includes("status") && !core.includes("status")) core.push("status");
    return core.length ? core : all.slice(0, 6);
  }

  /** Default board = claim metrics (not every diagnostic column). */
  function defaultMetricKeys(list) {
    return coreMetricKeys(list);
  }

  function columnKeys(list) {
    const all = availableMetricKeys(list);
    const chosen =
      state.visibleMetrics == null
        ? defaultMetricKeys(list)
        : all.filter((k) => state.visibleMetrics.has(k));
    return ["method_group", ...(chosen.length ? chosen : defaultMetricKeys(list))];
  }

  function renderMetricFilter(list) {
    const host = $("metric-filter-list");
    if (!host) return;
    const all = availableMetricKeys(list);
    const active = new Set(
      state.visibleMetrics == null
        ? defaultMetricKeys(list)
        : [...state.visibleMetrics]
    );
    host.innerHTML = "";
    all.forEach((k) => {
      const id = `metric-vis-${k}`;
      const label = document.createElement("label");
      label.htmlFor = id;
      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = id;
      input.checked = active.has(k);
      input.addEventListener("change", () => {
        const next = new Set(
          state.visibleMetrics == null
            ? defaultMetricKeys(list)
            : [...state.visibleMetrics]
        );
        if (input.checked) next.add(k);
        else next.delete(k);
        state.visibleMetrics = next;
        renderLeaderboard();
        writeHash();
      });
      label.appendChild(input);
      label.appendChild(document.createTextNode(labelMetric(k)));
      host.appendChild(label);
    });
  }

  function renderTaskTabs(hostId, active, onPick) {
    const host = $(hostId);
    host.innerHTML = "";
    TASKS.forEach((id) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tab" + (id === active ? " active" : "");
      btn.textContent = id;
      btn.addEventListener("click", () => onPick(id));
      host.appendChild(btn);
    });
  }

  function stepsAvailable(dataset) {
    const steps = new Set();
    rows().forEach((r) => {
      if (r.dataset === dataset) steps.add(rowStep(r));
    });
    const arr = [...steps].sort((a, b) => a - b);
    return arr.length ? arr : [1];
  }

  function applyTaskFilterVisibility() {
    const dsSel = $("dataset-select");
    const stepSel = $("step-select");
    const dsLabel = $("dataset-label");
    const stepLabel = $("step-label");
    const hint = $("task-hint");
    hint.textContent = TASK_HINT[state.task] || "";

    if (state.task === "general") {
      state.dataset = "SM_70";
      state.step = 1;
      dsSel.disabled = true;
      stepSel.disabled = true;
      dsLabel.style.opacity = "0.55";
      stepLabel.style.opacity = "0.55";
    } else if (state.task === "missing wedge") {
      state.step = 1;
      dsSel.disabled = false;
      stepSel.disabled = true;
      dsLabel.style.opacity = "1";
      stepLabel.style.opacity = "0.55";
    } else {
      state.dataset = "SM_70";
      dsSel.disabled = true;
      stepSel.disabled = false;
      dsLabel.style.opacity = "0.55";
      stepLabel.style.opacity = "1";
    }
  }

  function renderDatasetSelects() {
    const menu = datasetMenu();
    const sel = $("dataset-select");
    const exSel = $("explorer-dataset");
    sel.innerHTML = "";
    exSel.innerHTML = "";
    const list = menu.length
      ? menu
      : [{ id: "SM_70", label: "SM_70", tilt_abs: 70 }];
    if (!list.some((d) => d.id === state.dataset)) {
      state.dataset = list.some((d) => d.id === "SM_70") ? "SM_70" : list[0].id;
    }
    if (!list.some((d) => d.id === state.explorerDataset)) {
      state.explorerDataset = state.dataset;
    }
    list.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = d.label || d.id;
      sel.appendChild(opt);
      exSel.appendChild(opt.cloneNode(true));
    });
    sel.value = state.dataset;
    exSel.value = state.explorerDataset;
    sel.onchange = () => {
      state.dataset = sel.value;
      renderLeaderboard();
      writeHash();
    };
    exSel.onchange = () => {
      state.explorerDataset = exSel.value;
      renderExplorer();
    };
  }

  function renderStepSelect() {
    const sel = $("step-select");
    const steps = stepsAvailable(
      state.task === "sparse view" ? "SM_70" : state.dataset
    );
    sel.innerHTML = "";
    if (!steps.includes(Number(state.step))) state.step = steps[0];
    steps.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = String(s);
      opt.textContent = `${s}°`;
      sel.appendChild(opt);
    });
    sel.value = String(state.step);
    sel.onchange = () => {
      state.step = Number(sel.value) || 1;
      renderLeaderboard();
      writeHash();
    };
  }

  function renderConfigPanel() {
    const host = $("config-panel");
    const ds = state.task === "sparse view" ? "SM_70" : state.dataset;
    const step = state.task === "missing wedge" || state.task === "general" ? 1 : state.step;
    const tilt = Number(String(ds).replace("SM_", "")) || "—";
    const wedge = tilt !== "—" ? 180 - 2 * tilt : "—";
    host.innerHTML = `
      <span><strong style="color:var(--text)">Task</strong> ${state.task}</span>
      <span><strong style="color:var(--text)">Dataset</strong> ${ds}</span>
      <span><strong style="color:var(--text)">Tilt</strong> ±${tilt}°</span>
      <span><strong style="color:var(--text)">Wedge</strong> ${wedge}°</span>
      <span><strong style="color:var(--text)">Step</strong> ${step}°</span>
    `;
  }

  function fmtNum(v, digits) {
    if (v == null || typeof v !== "number" || !Number.isFinite(v)) return "—";
    if (Math.abs(v) >= 1000) return v.toFixed(0);
    return v.toFixed(digits == null ? 3 : digits);
  }

  function histSparkline(counts, edges) {
    if (!Array.isArray(counts) || !counts.length) return "";
    const w = 280;
    const h = 64;
    const max = Math.max(...counts, 1);
    const bw = w / counts.length;
    const bars = counts
      .map((c, i) => {
        const bh = (c / max) * (h - 4);
        const x = i * bw;
        const y = h - bh;
        return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${Math.max(bw - 0.6, 0.8).toFixed(2)}" height="${bh.toFixed(2)}" fill="currentColor" opacity="0.85"/>`;
      })
      .join("");
    const lo = Array.isArray(edges) && edges.length ? fmtNum(edges[0], 0) : "";
    const hi =
      Array.isArray(edges) && edges.length > 1
        ? fmtNum(edges[edges.length - 1], 0)
        : "";
    return `<svg class="hist-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Intensity histogram">${bars}</svg>
      <div style="display:flex;justify-content:space-between;color:var(--faint);font-size:0.72rem"><span>${lo}</span><span>intensity</span><span>${hi}</span></div>`;
  }

  function intensityHist(inten) {
    if (Array.isArray(inten.hist_counts) && inten.hist_counts.length) {
      return histSparkline(inten.hist_counts, inten.hist_edges);
    }
    // Near-binary phantoms often omit full histograms — synthesize 2 bins.
    if (inten.is_near_binary && inten.zero_frac != null && inten.min != null && inten.max != null) {
      const z = Math.max(0, Math.min(1, inten.zero_frac));
      return histSparkline([z, 1 - z], [inten.min, inten.max]);
    }
    return "";
  }

  function renderDatasetProfile() {
    const host = $("dataset-profile");
    const toggle = $("dataset-profile-toggle");
    if (!host) return;
    const ds = state.task === "sparse view" ? "SM_70" : state.dataset;
    const profiles = (state.data && state.data.dataset_profiles) || {};
    const p = profiles[ds];
    if (!p) {
      host.innerHTML = "";
      if (toggle) {
        toggle.hidden = true;
        toggle.open = false;
      }
      return;
    }
    if (toggle) toggle.hidden = false;
    const gt = p.gt_stats || {};
    const inten = gt.intensity || {};
    const morph = gt.morphology || {};
    const geom = gt.geometry || {};
    const edge = gt.edge || {};
    const angles = p.tilt_angles || {};
    const shape = Array.isArray(gt.shape) ? gt.shape.join(" × ") : "—";
    const figHref = gt.figure
      ? String(gt.figure).replace(/^docs\//, "../")
      : null;

    host.innerHTML = `
      <div class="dataset-profile-head">
        <h3>${p.id} · dataset profile</h3>
        <span class="meta">${p.name || ""} · ${p.type || "simulated"}${p.has_ground_truth ? " · GT yes" : ""}</span>
      </div>
      <div class="profile-grid">
        <div class="profile-block">
          <h4>Basic</h4>
          <dl>
            <dt>Tilt range</dt><dd>${p.tilt_min != null ? p.tilt_min + "° … " + p.tilt_max + "°" : "—"}</dd>
            <dt>Missing wedge</dt><dd>${p.missing_wedge_deg != null ? p.missing_wedge_deg + "°" : "—"}</dd>
            <dt>Angular step</dt><dd>${p.angular_step_deg != null ? p.angular_step_deg + "°" : "—"}</dd>
            <dt>Projections</dt><dd>${p.num_projections != null ? p.num_projections : angles.count || "—"}</dd>
            <dt>Proj. shape</dt><dd>${Array.isArray(p.projection_shape) ? p.projection_shape.join(" × ") : "—"}</dd>
            <dt>Angle file</dt><dd>${angles.count != null ? angles.count + " angles" : "—"}</dd>
            <dt>Median Δθ</dt><dd>${angles.median_step_deg != null ? fmtNum(angles.median_step_deg, 2) + "°" : "—"}</dd>
          </dl>
        </div>
        <div class="profile-block">
          <h4>GT intensity</h4>
          <dl>
            <dt>Volume shape</dt><dd>${shape}</dd>
            <dt>dtype</dt><dd>${gt.dtype || "—"}</dd>
            <dt>min / max</dt><dd>${fmtNum(inten.min, 1)} / ${fmtNum(inten.max, 1)}</dd>
            <dt>mean ± std</dt><dd>${fmtNum(inten.mean, 2)} ± ${fmtNum(inten.std, 2)}</dd>
            <dt>median</dt><dd>${fmtNum(inten.median, 2)}</dd>
            <dt>unique levels</dt><dd>${inten.n_unique != null ? inten.n_unique : "—"}${inten.is_near_binary ? " (near-binary)" : ""}</dd>
            <dt>zero fraction</dt><dd>${inten.zero_frac != null ? (100 * inten.zero_frac).toFixed(1) + "%" : "—"}</dd>
          </dl>
          ${intensityHist(inten)}
        </div>
        <div class="profile-block">
          <h4>Morphology / geometry</h4>
          <dl>
            <dt>Solid frac. (global)</dt><dd>${morph.solid_fraction_global_incl_background != null ? (100 * morph.solid_fraction_global_incl_background).toFixed(1) + "%" : "—"}</dd>
            <dt>Porosity (in sphere)</dt><dd>${morph.porosity_in_sphere != null ? (100 * morph.porosity_in_sphere).toFixed(1) + "%" : "—"}</dd>
            <dt>Solid components</dt><dd>${morph.n_solid_components != null ? morph.n_solid_components : "—"}</dd>
            <dt>Pore components</dt><dd>${morph.n_pore_components_in_sphere != null ? morph.n_pore_components_in_sphere : "—"}</dd>
            <dt>Mean pore radius</dt><dd>${morph.mean_pore_radius_edt != null ? fmtNum(morph.mean_pore_radius_edt, 2) + " px" : "—"}</dd>
            <dt>Mean wall thick.</dt><dd>${morph.mean_wall_thickness_edt != null ? fmtNum(morph.mean_wall_thickness_edt, 2) + " px" : "—"}</dd>
            <dt>Elongation</dt><dd>${geom.elongation_sqrt_lmax_lmin != null ? fmtNum(geom.elongation_sqrt_lmax_lmin, 3) : "—"}</dd>
            <dt>Edge contrast</dt><dd>${edge.contrast != null ? fmtNum(edge.contrast, 1) : "—"}</dd>
          </dl>
        </div>
      </div>
      ${
        p.note || figHref
          ? `<p class="profile-note">${p.note || ""}${
              figHref
                ? (p.note ? " · " : "") +
                  '<a href="' +
                  figHref +
                  '" target="_blank" rel="noopener">analysis figure</a>'
                : ""
            }</p>`
          : ""
      }
    `;
  }

  function renderLeaderboard() {
    renderTaskTabs("task-tabs", state.task, (id) => {
      state.task = id;
      state.sortKey = null;
      if (id === "general" || id === "sparse view") state.dataset = "SM_70";
      if (id === "general" || id === "missing wedge") state.step = 1;
      renderLeaderboard();
      writeHash();
    });
    renderDatasetSelects();
    renderStepSelect();
    applyTaskFilterVisibility();
    renderConfigPanel();
    renderDatasetProfile();

    const list = filteredRows();
    const banner = $("lb-banner");
    const bannerText = $("lb-banner-text");
    const hasProtocol = list.some((r) =>
      Object.keys(r.metrics || {}).some((k) => PROTOCOL_KEYS.has(k))
    );
    if (!list.length) {
      banner.hidden = false;
      bannerText.textContent =
        "No results for this task/condition yet. Default general view uses SM_70 @ 1° when available.";
    } else if (!hasProtocol) {
      banner.hidden = false;
      bannerText.textContent =
        "Protocol_* not in this cohort yet — using SSIM/Dice as temporary claim proxies. Best = within method family only. Runtime / PSNR are diagnostic.";
    } else {
      banner.hidden = false;
      bannerText.textContent =
        "Comparing claim metrics for this task. Best = within method family only. Runtime / raw PSNR are diagnostic.";
    }

    renderMetricFilter(list);
    const keys = columnKeys(list);
    const thead = $("lb-table").querySelector("thead");
    const tbody = $("lb-table").querySelector("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    const hr = document.createElement("tr");
    ["Rank", "Algorithm", ...keys].forEach((k) => {
      const th = document.createElement("th");
      th.textContent = k === "Rank" || k === "Algorithm" ? k : labelMetric(k);
      if (k === "Rank") th.className = "sticky-rank";
      else if (k === "Algorithm") th.className = "sticky-alg";
      else if (k === "method_group") th.className = "sticky-cat";
      if (
        k !== "Rank" &&
        k !== "Algorithm" &&
        k !== "image" &&
        k !== "status" &&
        k !== "method_group"
      ) {
        th.addEventListener("click", () => {
          if (state.sortKey === k) {
            state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
          } else {
            state.sortKey = k;
            state.sortDir = HIGHER.has(k) ? "desc" : "asc";
          }
          renderLeaderboard();
          writeHash();
        });
      }
      hr.appendChild(th);
    });
    thead.appendChild(hr);

    const sortKey =
      state.sortKey ||
      activeClaimKeys(list).find(
        (k) => keys.includes(k) && list.some((r) => metricValue(r, k) != null)
      ) ||
      keys.find(
        (k) =>
          PROTOCOL_KEYS.has(k) && list.some((r) => metricValue(r, k) != null)
      ) ||
      keys.find((k) => k === "ssim") ||
      keys.find((k) => k !== "method_group") ||
      keys[0];

    if (!state.sortKey && sortKey) {
      state.sortDir = HIGHER.has(sortKey) ? "desc" : "asc";
    }

    const sorted = [...list].sort((a, b) => {
      const va = metricValue(a, sortKey);
      const vb = metricValue(b, sortKey);
      if (typeof va === "string" || typeof vb === "string") {
        return String(va || "").localeCompare(String(vb || ""));
      }
      if (va == null && vb == null) return a.algorithm.localeCompare(b.algorithm);
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return state.sortDir === "asc" ? cmp : -cmp;
    });

    const bestMap = {};
    keys.forEach((k) => {
      bestMap[k] = bestFor(k, sorted);
    });

    $("lb-empty").hidden = sorted.length > 0;
    sorted.forEach((r, i) => {
      const tr = document.createElement("tr");
      const rank = document.createElement("td");
      rank.className = "rank sticky-rank";
      rank.textContent = String(i + 1);
      tr.appendChild(rank);
      const alg = document.createElement("td");
      alg.className = "sticky-alg";
      alg.innerHTML = `<strong>${r.algorithm}</strong>`;
      tr.appendChild(alg);
      keys.forEach((k) => {
        const td = document.createElement("td");
        if (k === "image") {
          const ex = r.execution || {};
          const img = ex.docker_image || ex.image || "—";
          td.textContent =
            typeof img === "string" && img.includes("/")
              ? img.split("/").pop()
              : fmt(img);
          td.className = "muted";
          td.title = String(img);
        } else if (k === "status") {
          const pill = document.createElement("span");
          pill.className =
            "status-pill" + (r.status === "audited" ? " audited" : "");
          pill.textContent = r.status || "legacy";
          td.appendChild(pill);
        } else if (k === "method_group") {
          td.textContent = r.method_group || "—";
          td.className = "muted sticky-cat";
        } else {
          const v = metricValue(r, k);
          td.textContent = fmt(v);
          if (bestMap[k] && bestMap[k].has(r.algorithm)) {
            td.className = "best";
          } else if (v == null) {
            td.className = "muted";
          } else if (!isClaimMetric(k, list)) {
            td.className = "muted";
          }
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    requestAnimationFrame(() => {
      syncTableScrollUi();
      requestAnimationFrame(syncTableScrollUi);
    });
  }

  function syncTableScrollUi() {
    const wrap = $("lb-table-wrap");
    const bar = $("lb-scroll-bar");
    const left = $("lb-scroll-left");
    const right = $("lb-scroll-right");
    if (!wrap || !bar || !left || !right) return;
    const max = Math.max(0, wrap.scrollWidth - wrap.clientWidth);
    const can = max > 2;
    bar.dataset.canScroll = can ? "true" : "false";
    left.disabled = wrap.scrollLeft <= 1;
    right.disabled = wrap.scrollLeft >= max - 1;
    left.style.visibility = can ? "visible" : "hidden";
    right.style.visibility = can ? "visible" : "hidden";
  }

  function closeDetails(el) {
    if (el && el.open) el.open = false;
  }

  function bindPopoverDismiss() {
    const metric = $("metric-filter");
    const dataset = $("dataset-profile-toggle");
    const backdrop = $("dataset-profile-backdrop");

    // Click dimmed backdrop → close dataset modal.
    backdrop?.addEventListener("click", (ev) => {
      if (ev.target === backdrop) closeDetails(dataset);
    });

    // Escape closes whichever is open.
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      closeDetails(metric);
      closeDetails(dataset);
    });

    // Click outside Metrics dropdown → close it.
    // Click outside Dataset details control (but not its modal panel) handled via backdrop.
    document.addEventListener(
      "pointerdown",
      (ev) => {
        const t = ev.target;
        if (metric?.open && !metric.contains(t)) closeDetails(metric);
        if (
          dataset?.open &&
          !dataset.querySelector(".dataset-profile-panel")?.contains(t) &&
          !dataset.querySelector("summary")?.contains(t)
        ) {
          closeDetails(dataset);
        }
      },
      true
    );

    // Opening one closes the other.
    metric?.addEventListener("toggle", () => {
      if (metric.open) closeDetails(dataset);
    });
    dataset?.addEventListener("toggle", () => {
      if (dataset.open) closeDetails(metric);
    });
  }

  function bindTableScroll() {
    const wrap = $("lb-table-wrap");
    const left = $("lb-scroll-left");
    const right = $("lb-scroll-right");
    if (!wrap || wrap.dataset.scrollBound === "1") return;
    wrap.dataset.scrollBound = "1";
    const step = () => Math.max(220, Math.floor(wrap.clientWidth * 0.6));
    left?.addEventListener("click", (ev) => {
      ev.preventDefault();
      wrap.scrollLeft = Math.max(0, wrap.scrollLeft - step());
      syncTableScrollUi();
    });
    right?.addEventListener("click", (ev) => {
      ev.preventDefault();
      wrap.scrollLeft = Math.min(
        wrap.scrollWidth - wrap.clientWidth,
        wrap.scrollLeft + step()
      );
      syncTableScrollUi();
    });
    wrap.addEventListener("scroll", syncTableScrollUi, { passive: true });
    // Map vertical wheel to horizontal when table overflows.
    wrap.addEventListener(
      "wheel",
      (ev) => {
        if (wrap.scrollWidth <= wrap.clientWidth + 2) return;
        if (Math.abs(ev.deltaX) > Math.abs(ev.deltaY)) return;
        wrap.scrollLeft += ev.deltaY;
        ev.preventDefault();
        syncTableScrollUi();
      },
      { passive: false }
    );
    window.addEventListener("resize", syncTableScrollUi);
  }

  function downloadCsv(filename, header, lines) {
    const body = [header.join(","), ...lines].join("\n");
    const blob = new Blob([body], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function lbCsv() {
    const list = filteredRows();
    const keys = columnKeys(list);
    const header = ["rank", "algorithm", "task", "dataset", "step", ...keys];
    const lines = list.map((r, i) =>
      [
        i + 1,
        r.algorithm,
        state.task,
        r.dataset,
        rowStep(r),
        ...keys.map((k) => {
          if (k === "image") {
            const ex = r.execution || {};
            return JSON.stringify(ex.docker_image || ex.image || "");
          }
          if (k === "status") return r.status || "";
          if (k === "method_group") return r.method_group || "";
          const v = metricValue(r, k);
          return v == null ? "" : v;
        }),
      ].join(",")
    );
    downloadCsv(
      `et-tomo-${state.task.replace(/\s+/g, "_")}-${state.dataset}-step${state.step}.csv`,
      header,
      lines
    );
  }

  function sampleConditionHtml(family) {
    const conds = family.conditions || [];
    const isAligned = family.id === "aligned_model";
    if (isAligned) {
      const wedgeSeen = new Set();
      const wedgeRows = [];
      conds
        .filter(
          (d) =>
            Number(d.angular_step_deg) === 1 || d.angular_step_deg == null
        )
        .forEach((d) => {
          const id =
            d.dataset ||
            (d.tilt_max != null ? `SM_${Math.abs(d.tilt_max)}` : d.id);
          if (wedgeSeen.has(id)) return;
          wedgeSeen.add(id);
          wedgeRows.push({ id, d });
        });
      const sparseSeen = new Set();
      const sparseRows = [];
      conds
        .filter(
          (d) =>
            (d.dataset === "SM_70" || Math.abs(Number(d.tilt_max)) === 70) &&
            d.angular_step_deg != null
        )
        .forEach((d) => {
          const key = String(d.angular_step_deg);
          if (sparseSeen.has(key)) return;
          sparseSeen.add(key);
          sparseRows.push(d);
        });
      return `
        <div class="condition-block">
          <h4>Missing-wedge conditions · 1° step</h4>
          <div class="condition-chips">
            ${wedgeRows
              .map(({ id, d }) => {
                const tilt = Math.abs(Number(d.tilt_max));
                const wedge =
                  d.missing_wedge_deg != null
                    ? Number(d.missing_wedge_deg).toFixed(0)
                    : String(180 - 2 * tilt);
                return `<span class="condition-chip" title="${d.num_projections || "—"} projections"><strong>${id}</strong> ±${tilt}° · wedge ${wedge}°</span>`;
              })
              .join("")}
          </div>
        </div>
        <div class="condition-block">
          <h4>Sparse-view conditions · SM_70</h4>
          <div class="condition-chips">
            ${sparseRows
              .map((d) => {
                const step = d.angular_step_deg;
                return `<span class="condition-chip" title="${d.num_projections || "—"} projections"><strong>${step}°</strong> step · ${d.num_projections != null ? d.num_projections + " proj." : "—"}</span>`;
              })
              .join("")}
          </div>
        </div>`;
    }
    return `
      <div class="condition-block">
        <h4>Registered series</h4>
        <div class="condition-chips">
          ${conds
            .map((d) => {
              const tilt =
                d.tilt_min != null && d.tilt_max != null
                  ? `${d.tilt_min}°…${d.tilt_max}°`
                  : "tilt —";
              const step =
                d.angular_step_deg != null
                  ? ` · ~${Number(d.angular_step_deg).toFixed(2)}° step`
                  : "";
              const n =
                d.num_projections != null ? ` · ${d.num_projections} proj.` : "";
              return `<span class="condition-chip"><strong>${d.dataset || d.id}</strong> ${tilt}${step}${n}</span>`;
            })
            .join("")}
        </div>
      </div>`;
  }

  function sampleDetailHtml(family) {
    const conds = family.conditions || [];
    const gt = family.gt_stats || {};
    const shape = Array.isArray(gt.shape) ? gt.shape.join(" × ") : null;
    const porosity =
      gt.morphology && gt.morphology.porosity_in_sphere != null
        ? (100 * gt.morphology.porosity_in_sphere).toFixed(1) + "%"
        : null;
    const metaBits = [];
    if (shape) metaBits.push(`<dt>Volume</dt><dd>${shape}</dd>`);
    if (porosity) metaBits.push(`<dt>Porosity (in sphere)</dt><dd>${porosity}</dd>`);
    if (family.analysis_figure) {
      metaBits.push(
        `<dt>Analysis</dt><dd><a href="${family.analysis_figure}" target="_blank" rel="noopener">full GT figure</a></dd>`
      );
    }
    if (conds[0] && conds[0].path) {
      metaBits.push(`<dt>Path</dt><dd><code>${conds[0].path}</code></dd>`);
    }
    return `
      <p class="sample-blurb">${family.blurb || ""}</p>
      ${metaBits.length ? `<dl class="sample-meta">${metaBits.join("")}</dl>` : ""}
      ${sampleConditionHtml(family)}`;
  }

  function openSampleDetail(family) {
    const backdrop = $("sample-detail-backdrop");
    const title = $("sample-detail-title");
    const body = $("sample-detail-body");
    if (!backdrop || !title || !body) return;
    title.textContent = family.title || family.id || "Sample";
    body.innerHTML = sampleDetailHtml(family);
    backdrop.hidden = false;
  }

  function closeSampleDetail() {
    const backdrop = $("sample-detail-backdrop");
    if (backdrop) backdrop.hidden = true;
  }

  function renderSampleCard(family) {
    const card = document.createElement("article");
    card.className = "card sample-card";
    const preview =
      family.preview || "assets/samples/aligned_model_volume.png";
    const caption = family.preview_caption || "Volume preview";
    card.innerHTML = `
      <div class="sample-visual">
        <img src="${preview}" alt="${family.title}" loading="lazy" />
        <span class="sample-visual-caption">${caption}</span>
      </div>
      <div class="sample-card-foot">
        <div class="sample-card-head">
          <h3>${family.title}</h3>
          <span class="pill">${family.type || "sample"}${
            family.has_ground_truth ? " · GT yes" : " · no GT"
          }</span>
        </div>
        <button type="button" class="btn btn-ghost btn-small sample-details-btn">Details</button>
      </div>`;
    card
      .querySelector(".sample-details-btn")
      ?.addEventListener("click", () => openSampleDetail(family));
    return card;
  }

  function renderDatasets() {
    const simHost = $("dataset-grid");
    const expHost = $("dataset-grid-experimental");
    if (!simHost) return;
    simHost.innerHTML = "";
    if (expHost) expHost.innerHTML = "";

    let families = (state.data && state.data.sample_families) || [];
    if (!families.length) {
      simHost.innerHTML = `<p class="empty">No sample families in cohorts.json — re-export with datasets root.</p>`;
      return;
    }

    const sim = families.filter((f) => (f.type || "simulated") === "simulated");
    const exp = families.filter((f) => f.type === "experimental");
    if (!sim.length) {
      simHost.innerHTML = `<p class="empty">No simulated samples yet.</p>`;
    } else {
      sim.forEach((f) => simHost.appendChild(renderSampleCard(f)));
    }
    if (expHost) {
      if (!exp.length) {
        expHost.innerHTML = `<p class="empty" style="text-align:left">No experimental samples registered yet.</p>`;
      } else {
        exp.forEach((f) => expHost.appendChild(renderSampleCard(f)));
      }
    }
  }

  function axisWPoints(metric) {
    const order = [80, 70, 60, 50, 40];
    const out = [];
    rows().forEach((r) => {
      if (rowStep(r) !== 1) return;
      const tilt = Number(r.tilt_abs) || Number(String(r.dataset || "").replace("SM_", ""));
      if (!order.includes(tilt)) return;
      const v = metricValue(r, metric);
      if (typeof v !== "number") return;
      out.push({
        xLabel: `±${tilt}`,
        x: order.indexOf(tilt),
        y: v,
        algorithm: r.algorithm,
      });
    });
    return out.filter((p) => p.x >= 0);
  }

  function axisSPoints(metric) {
    const order = [1, 2, 4];
    const out = [];
    rows()
      .filter((r) => r.dataset === "SM_70")
      .forEach((r) => {
        const step = rowStep(r);
        if (!order.includes(step)) return;
        const v = metricValue(r, metric);
        if (typeof v !== "number") return;
        out.push({
          xLabel: `${step}°`,
          x: order.indexOf(step),
          y: v,
          algorithm: r.algorithm,
        });
      });
    return out;
  }

  function drawLineChart(host, points, xLabels) {
    host.innerHTML = "";
    if (!points.length) {
      host.innerHTML = `<p class="empty">No points for this axis in the current cohort yet.</p>`;
      return;
    }
    const w = 520;
    const h = 240;
    const pad = { l: 48, r: 14, t: 18, b: 38 };
    const ys = points.map((p) => p.y);
    let ymin = Math.min(...ys);
    let ymax = Math.max(...ys);
    if (ymin === ymax) {
      ymin -= 0.05;
      ymax += 0.05;
    }
    const xMax = Math.max(xLabels.length - 1, 1);
    const xScale = (x) => pad.l + (x / xMax) * (w - pad.l - pad.r);
    const yScale = (y) =>
      pad.t + ((ymax - y) / (ymax - ymin)) * (h - pad.t - pad.b);
    const byAlg = {};
    points.forEach((p) => {
      (byAlg[p.algorithm] || (byAlg[p.algorithm] = [])).push(p);
    });
    let paths = "";
    Object.entries(byAlg).forEach(([alg, pts]) => {
      pts.sort((a, b) => a.x - b.x);
      const d = pts
        .map((p, i) => `${i ? "L" : "M"}${xScale(p.x)},${yScale(p.y)}`)
        .join(" ");
      const c = colorFor(alg);
      paths += `<path d="${d}" fill="none" stroke="${c}" stroke-width="2.5" />`;
      pts.forEach((p) => {
        paths += `<circle cx="${xScale(p.x)}" cy="${yScale(p.y)}" r="3.5" fill="${c}"><title>${alg}: ${fmt(p.y)}</title></circle>`;
      });
    });
    const xticks = xLabels
      .map(
        (lab, i) =>
          `<text x="${xScale(i)}" y="${h - 12}" text-anchor="middle" fill="currentColor" font-size="11">${lab}</text>`
      )
      .join("");
    const yticks = [ymin, (ymin + ymax) / 2, ymax]
      .map((yv) => {
        const y = yScale(yv);
        return `<text x="6" y="${y + 3}" fill="currentColor" font-size="10">${fmt(yv)}</text>
          <line x1="${pad.l}" y1="${y}" x2="${w - pad.r}" y2="${y}" stroke="currentColor" stroke-opacity="0.14" />`;
      })
      .join("");
    host.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img">${yticks}${paths}${xticks}</svg>`;
  }

  function drawPareto(host, dataset, metric) {
    host.innerHTML = "";
    const pts = rows()
      .filter((r) => r.dataset === dataset && rowStep(r) === 1)
      .map((r) => ({
        algorithm: r.algorithm,
        x: metricValue(r, "runtime_s"),
        y: metricValue(r, metric),
      }))
      .filter((p) => typeof p.x === "number" && typeof p.y === "number");
    if (!pts.length) {
      host.innerHTML = `<p class="empty">Need runtime and ${labelMetric(metric)} on ${dataset}.</p>`;
      return;
    }
    const w = 520;
    const h = 240;
    const pad = { l: 48, r: 14, t: 18, b: 38 };
    const xs = pts.map((p) => p.x);
    const ys = pts.map((p) => p.y);
    let xmin = Math.min(...xs);
    let xmax = Math.max(...xs);
    let ymin = Math.min(...ys);
    let ymax = Math.max(...ys);
    if (xmin === xmax) {
      xmin -= 1;
      xmax += 1;
    }
    if (ymin === ymax) {
      ymin -= 0.05;
      ymax += 0.05;
    }
    const xScale = (x) =>
      pad.l + ((x - xmin) / (xmax - xmin)) * (w - pad.l - pad.r);
    const yScale = (y) =>
      pad.t + ((ymax - y) / (ymax - ymin)) * (h - pad.t - pad.b);
    const dots = pts
      .map((p) => {
        const c = colorFor(p.algorithm);
        return `<circle cx="${xScale(p.x)}" cy="${yScale(p.y)}" r="5" fill="${c}"><title>${p.algorithm}</title></circle>
          <text x="${xScale(p.x) + 7}" y="${yScale(p.y) + 3}" fill="currentColor" font-size="10">${p.algorithm}</text>`;
      })
      .join("");
    host.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img">${dots}</svg>`;
  }

  function renderExplorer() {
    renderTaskTabs("explorer-task-tabs", state.explorerTask, (id) => {
      state.explorerTask = id;
      renderExplorer();
    });
    renderDatasetSelects();

    const preferred = primary()[state.explorerTask] || DEFAULT_PRIMARY.general;
    const claim = CLAIM_BY_TASK[state.explorerTask] || CLAIM_BY_TASK.general;
    const hasAnyProtocol = hasProtocolMetrics(rows());
    const opts = [
      ...(hasAnyProtocol ? claim : []),
      ...(hasAnyProtocol ? preferred : []),
      "ssim",
      "dice",
      "psnr",
      "r2",
      "runtime_s",
    ];
    const uniq = [];
    opts.forEach((k) => {
      if (!uniq.includes(k)) uniq.push(k);
    });
    const sel = $("explorer-metric");
    sel.innerHTML = "";
    uniq.forEach((k) => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = labelMetric(k);
      sel.appendChild(opt);
    });
    if (!uniq.includes(state.explorerMetric)) {
      state.explorerMetric = hasAnyProtocol
        ? claim.find((k) => uniq.includes(k)) || uniq[0]
        : uniq.includes("ssim")
          ? "ssim"
          : uniq[0];
    }
    sel.value = state.explorerMetric;
    sel.onchange = () => {
      state.explorerMetric = sel.value;
      renderExplorer();
    };

    const metric = state.explorerMetric;
    $("chart-w-title").textContent = `${labelMetric(metric)} vs tilt range`;
    $("chart-s-title").textContent = `${labelMetric(metric)} vs sparse step`;

    const showW =
      state.explorerTask === "missing wedge" || state.explorerTask === "general";
    const showS =
      state.explorerTask === "sparse view" || state.explorerTask === "general";
    $("chart-axis-w").parentElement.style.display = showW ? "" : "none";
    $("chart-axis-s").parentElement.style.display = showS ? "" : "none";

    if (showW) {
      drawLineChart($("chart-axis-w"), axisWPoints(metric), [
        "±80",
        "±70",
        "±60",
        "±50",
        "±40",
      ]);
    }
    if (showS) {
      drawLineChart($("chart-axis-s"), axisSPoints(metric), ["1°", "2°", "4°"]);
    }
    drawPareto($("chart-pareto"), state.explorerDataset, metric);
  }

  function exCsv() {
    const metric = state.explorerMetric;
    const pts = [
      ...axisWPoints(metric).map((p) => ({
        axis: "W",
        x: p.xLabel,
        algorithm: p.algorithm,
        metric,
        value: p.y,
      })),
      ...axisSPoints(metric).map((p) => ({
        axis: "S",
        x: p.xLabel,
        algorithm: p.algorithm,
        metric,
        value: p.y,
      })),
    ];
    downloadCsv(
      `et-tomo-results-${metric}.csv`,
      ["axis", "x", "algorithm", "metric", "value"],
      pts.map((p) => [p.axis, p.x, p.algorithm, p.metric, p.value].join(","))
    );
  }

  async function boot() {
    initTheme();
    initNavSpy();
    parseHash();
    $("lb-download-csv").addEventListener("click", lbCsv);
    $("ex-download-csv").addEventListener("click", exCsv);
    const flashCopied = (btn) => {
      if (!btn) return;
      const prev = btn.textContent;
      btn.textContent = "Copied";
      setTimeout(() => {
        btn.textContent = prev;
      }, 1200);
    };
    $("lb-copy-link").addEventListener("click", () => {
      writeHash();
      navigator.clipboard?.writeText(location.href);
      flashCopied($("lb-copy-link"));
    });
    $("ex-copy-link").addEventListener("click", () => {
      writeHash();
      navigator.clipboard?.writeText(location.href);
      flashCopied($("ex-copy-link"));
    });
    $("metric-filter-all")?.addEventListener("click", () => {
      state.visibleMetrics = new Set(availableMetricKeys(filteredRows()));
      renderLeaderboard();
      writeHash();
    });
    $("metric-filter-defaults")?.addEventListener("click", () => {
      state.visibleMetrics = null; // claim defaults
      renderLeaderboard();
      writeHash();
    });
    bindPopoverDismiss();
    bindTableScroll();
    $("sample-detail-close")?.addEventListener("click", closeSampleDetail);
    $("sample-detail-backdrop")?.addEventListener("click", (ev) => {
      if (ev.target === $("sample-detail-backdrop")) closeSampleDetail();
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") closeSampleDetail();
    });

    try {
      const res = await fetch("data/cohorts.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.data = await res.json();
    } catch (err) {
      $("lb-banner").hidden = false;
      $("lb-banner-text").textContent =
        "Could not load data/cohorts.json. Serve this folder over HTTP.";
      state.data = {
        tasks: TASKS,
        primary_by_task: DEFAULT_PRIMARY,
        conditions: [],
        dataset_menu: [{ id: "SM_70", tilt_abs: 70, label: "SM_70" }],
        rows: [],
        datasets: [],
      };
    }

    renderLeaderboard();
    renderExplorer();
    renderDatasets();
    writeHash();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
