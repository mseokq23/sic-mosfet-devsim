/* Interactive results page: small SVG chart kit + one renderer per figure, in English or Korean (html lang).
   Data come from site/data/*.js (window.SITE), written by scripts/make_site.py from the committed result files. */
(() => {
  "use strict";
  const KO = document.documentElement.lang === "ko";
  const t = (en, ko) => (KO ? ko : en);
  const D = window.SITE || {};
  const C = D.core, SUR = D.surrogate;
  if (!C) {
    document.body.prepend(document.createTextNode(t("The data file (site/data/core.js) was not found.", "데이터 파일(site/data/core.js)을 찾지 못했습니다.")));
    return;
  }
  const REPO = C.meta.repo, COMMIT = C.meta.commit;
  const NS = "http://www.w3.org/2000/svg";
  const VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2", "mu_channel_scale"];
  const TGT = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"];
  const SYM = { wjfet_scale: "W_{JFET}", npwell_scale: "N_{pw}", qit_eff_cm2: "Q_{it,eff}", mu_channel_scale: "s_{μ}" };
  const NAME = KO ? { wjfet_scale: "JFET 폭", npwell_scale: "P-well 도핑", qit_eff_cm2: "유효 계면전하", mu_channel_scale: "채널 이동도 배율" }
    : { wjfet_scale: "JFET width", npwell_scale: "P-well doping", qit_eff_cm2: "Interface charge", mu_channel_scale: "Channel-mobility scale" };
  const UNIT = { wjfet_scale: "µm", npwell_scale: "×10^{17} cm^{-3}", qit_eff_cm2: "×10^{12} cm^{-2}", mu_channel_scale: "" };
  const MINUS = "−";
  const MAE = KO ? "평균 MAE_{norm}" : "Mean MAE_{norm}";

  // ------------------------------------------------------------------------------------------- dom helpers
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k === "rich") rich(e, v);
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  }
  function sv(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }
  const $ = (id) => document.getElementById(id);
  const clamp = (a, b, v) => Math.round(Math.max(a, Math.min(b, v)));

  // "V_{GS}", "10^{-12}" -> sub/sup
  function parseRich(str) {
    const out = [], re = /([_^])\{([^}]*)\}/g;
    let m, last = 0;
    str = String(str);
    while ((m = re.exec(str))) {
      if (m.index > last) out.push({ t: str.slice(last, m.index) });
      out.push({ t: m[2].replace(/-/g, MINUS), k: m[1] === "_" ? "sub" : "sup" });
      last = re.lastIndex;
    }
    if (last < str.length) out.push({ t: str.slice(last) });
    return out;
  }
  function rich(el, str) {
    el.textContent = "";
    for (const p of parseRich(str)) el.append(p.k ? h(p.k, { text: p.t }) : document.createTextNode(p.t));
    return el;
  }
  function richSVG(t_, str, base = 12) {
    t_.textContent = "";
    let shift = 0;
    for (const p of parseRich(str)) {
      const ts = sv("tspan", {}, t_);
      ts.textContent = p.t;
      const want = p.k === "sub" ? base * 0.32 : p.k === "sup" ? -base * 0.42 : 0;
      if (want !== shift) ts.setAttribute("dy", (want - shift).toFixed(2));
      if (p.k) ts.setAttribute("font-size", (base * 0.74).toFixed(1));
      shift = want;
    }
    return t_;
  }
  const plainLen = (str) => parseRich(str).reduce((n, p) => n + p.t.length * (p.k ? 0.74 : 1), 0);

  // ------------------------------------------------------------------------------------------- number formats
  const neg = (s) => s.replace(/^-/, MINUS);
  const fx = (v, d = 3) => (v == null || !isFinite(v) ? "–" : neg((+v).toFixed(d)));
  const sgn = (v, d = 1) => {
    if (v == null || !isFinite(v)) return "–";
    const a = Math.abs(v).toFixed(d);
    return +a === 0 ? (0).toFixed(d) : (v > 0 ? "+" : MINUS) + a;
  };
  const pct = (v, d = 1) => sgn(v * 100, d) + " %";
  function sci(v, d = 2) {               // "1.23×10^{-5}" markup
    if (v == null || !isFinite(v) || v === 0) return "–";
    const e = Math.floor(Math.log10(Math.abs(v))), m = v / Math.pow(10, e);
    return `${neg(m.toFixed(d))}×10^{${e}}`;
  }
  function physVal(v, u) {               // normalized u -> physical display value
    const b = C.design.bounds[v];
    const x = b.low + u * (b.high - b.low);
    if (v === "wjfet_scale") return 2.4 * x;
    if (v === "npwell_scale") return x;
    if (v === "qit_eff_cm2") return x / 1e12;
    return x;
  }
  const physDomain = (v) => [physVal(v, 0), physVal(v, 1)].sort((a, b) => a - b);
  const physFmt = (v, x) => fx(x, 2);
  const axisLabel = (v) => `${NAME[v]} ${SYM[v]}${UNIT[v] ? " (" + UNIT[v] + ")" : ""}`;
  const locale = KO ? "ko-KR" : "en-US";

  // ------------------------------------------------------------------------------------------- lazy data
  const loading = {};
  function need(name) {
    if (D[name]) return Promise.resolve(D[name]);
    if (!loading[name]) {
      loading[name] = new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = `data/${name}.js`;
        s.onload = () => (D[name] ? res(D[name]) : rej(new Error(name)));
        s.onerror = () => rej(new Error(name));
        document.head.append(s);
      });
    }
    return loading[name];
  }
  function whenNear(el, fn, margin = "600px") {
    if (!("IntersectionObserver" in window)) return fn();
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { io.disconnect(); fn(); }
    }, { rootMargin: margin });
    io.observe(el);
  }

  // ------------------------------------------------------------------------------------------- scales
  function lin(d0, d1, r0, r1) {
    const k = (r1 - r0) / ((d1 - d0) || 1);
    const f = (v) => r0 + (v - d0) * k;
    f.inv = (p) => d0 + (p - r0) / k;
    return f;
  }
  function niceStep(span, n) {
    const raw = span / Math.max(1, n), mag = Math.pow(10, Math.floor(Math.log10(raw))), e = raw / mag;
    return mag * (e >= 7.5 ? 10 : e >= 3.5 ? 5 : e >= 1.5 ? 2 : 1);
  }
  function ticks(a, b, n) {
    const st = niceStep(b - a, n), out = [];
    for (let v = Math.ceil(a / st - 1e-9) * st; v <= b + st * 1e-9; v += st) out.push(+(Math.abs(v) < st * 1e-9 ? 0 : v).toPrecision(12));
    return out;
  }
  function niceDomain(a, b, n) {
    if (a === b) { a -= 1; b += 1; }
    const st = niceStep(b - a, n);
    return [Math.floor(a / st + 1e-9) * st, Math.ceil(b / st - 1e-9) * st];
  }
  const decimalsFor = (ts) => { const st = ts.length > 1 ? Math.abs(ts[1] - ts[0]) : 1; return Math.max(0, Math.min(4, -Math.floor(Math.log10(st) + 1e-9))); };

  // ------------------------------------------------------------------------------------------- markers
  function marker(g, shape, cx, cy, r, color) {
    if (shape === "x") {
      const d = r * 0.85;
      return sv("path", { d: `M${cx - d},${cy - d}L${cx + d},${cy + d}M${cx - d},${cy + d}L${cx + d},${cy - d}`, stroke: color, "stroke-width": 2.6, fill: "none" }, g);
    }
    if (shape === "diamond") {
      const d = r * 1.25;
      return sv("path", { d: `M${cx},${cy - d}L${cx + d},${cy}L${cx},${cy + d}L${cx - d},${cy}Z`, fill: color, stroke: "var(--frame)", "stroke-width": 0.8 }, g);
    }
    if (shape === "ring") return sv("circle", { cx, cy, r, fill: "none", stroke: color, "stroke-width": 2 }, g);
    return sv("circle", { cx, cy, r, class: "dot", fill: color, stroke: "var(--frame)", "stroke-width": 0.8 }, g);
  }
  function swatchSVG(shape, color) {
    const s = sv("svg", { width: 14, height: 14, viewBox: "0 0 14 14", "aria-hidden": "true" });
    marker(s, shape, 7, 7, shape === "ring" ? 5 : 4.6, color);
    return s;
  }

  // ------------------------------------------------------------------------------------------- chart base
  const ro = "ResizeObserver" in window ? new ResizeObserver((es) => {
    for (const e of es) {
      const c = e.target.__chart;
      if (c && Math.abs(e.contentRect.width - c._w) > 2) c.render();
    }
  }) : null;

  class Chart {
    constructor(host, o) {
      this.host = typeof host === "string" ? $(host) : host;
      this.o = o;
      this.host.textContent = "";
      this.hidden = new Set(o.hidden || []);
      if (o.legend !== false) { this.leg = h("ul", { class: "legend" }); this.host.append(this.leg); }
      this.wrap = h("div", { class: "chart" });
      this.host.append(this.wrap);
      this.svg = sv("svg", { role: "img", "aria-label": o.aria || "" });
      this.wrap.append(this.svg);
      this.tip = h("div", { class: "tip", hidden: true });
      this.wrap.append(this.tip);
      this.wrap.__chart = this;
      this._w = 0;
      if (ro) ro.observe(this.wrap);
      this.svg.addEventListener("pointermove", (ev) => this._move(ev));
      this.svg.addEventListener("pointerdown", (ev) => this._move(ev));
      this.svg.addEventListener("pointerleave", (ev) => { if (ev.pointerType === "mouse") this._hide(); });
      this.svg.addEventListener("click", (ev) => this._click && this._click(ev));
      this.svg.setAttribute("tabindex", "0");
      this.svg.addEventListener("keydown", (ev) => this._key && this._key(ev));
      this.svg.addEventListener("blur", () => this._hide());
      this.render();
    }
    set(o) { Object.assign(this.o, o); this.render(); }
    _move() {}
    dims() {
      const w = Math.max(240, Math.round(this.wrap.clientWidth || this.host.clientWidth || 600));
      const o = this.o;
      const hgt = typeof o.height === "function" ? o.height(w) : o.height || Math.round(Math.max(220, Math.min(360, w * 0.58)));
      return { w, h: hgt };
    }
    _pt(ev) {
      const r = this.svg.getBoundingClientRect();
      const k = this._vw / r.width;
      return [(ev.clientX - r.left) * k, (ev.clientY - r.top) * k];
    }
    _hide() { this.tip.hidden = true; if (this.cross) this.cross.setAttribute("visibility", "hidden"); }
    showTip(px, py, rows, head) {
      const tp = this.tip;
      tp.textContent = "";
      if (head) tp.append(h("div", { class: "t-h", rich: head }));
      for (const r of rows) {
        const sw = h("span", { class: "sw" });
        sw.style.borderTopColor = r.color || "transparent";
        if (r.dash) sw.style.borderTopStyle = "dashed";
        tp.append(h("div", { class: "t-r" }, sw, h("b", { rich: r.value }), h("span", { rich: r.label || "" })));
      }
      tp.hidden = false;
      const W = this.wrap.clientWidth, r = this.svg.getBoundingClientRect(), k = r.width / this._vw;
      let x = px * k + 14, y = py * k - 10;
      const tw = tp.offsetWidth, th = tp.offsetHeight;
      if (x + tw > W) x = px * k - tw - 14;
      if (x < 0) x = Math.max(0, Math.min(W - tw, px * k - tw / 2));
      y = Math.max(0, Math.min(y, r.height - th));
      tp.style.left = `${x}px`;
      tp.style.top = `${y}px`;
    }
    begin() {
      const { w, h: H } = this.dims();
      this._w = this.wrap.clientWidth;
      this._vw = w;
      const svg = this.svg;
      svg.textContent = "";
      svg.setAttribute("viewBox", `0 0 ${w} ${H}`);
      svg.setAttribute("width", w);
      svg.setAttribute("height", H);
      return { w, H };
    }
    axes({ x, y, xt, yt, xfmt, yfmt, xl, yl, m, w, H }) {
      const g = sv("g", { class: "grid" }, this.svg);
      for (const tk_ of yt) sv("line", { x1: m.l, x2: w - m.r, y1: y(tk_), y2: y(tk_) }, g);
      for (const tk_ of xt) sv("line", { x1: x(tk_), x2: x(tk_), y1: m.t, y2: H - m.b }, g);
      const tk = sv("g", { class: "tick" }, this.svg);
      for (const tk_ of xt) {
        sv("line", { x1: x(tk_), x2: x(tk_), y1: H - m.b, y2: H - m.b + 5 }, tk);
        richSVG(sv("text", { x: x(tk_), y: H - m.b + 19, "text-anchor": "middle" }, tk), xfmt(tk_), 12.5);
      }
      for (const tk_ of yt) {
        sv("line", { x1: m.l - 5, x2: m.l, y1: y(tk_), y2: y(tk_) }, tk);
        richSVG(sv("text", { x: m.l - 8, y: y(tk_) + 4.5, "text-anchor": "end" }, tk), yfmt(tk_), 12.5);
      }
      if (xl) richSVG(sv("text", { x: (m.l + w - m.r) / 2, y: H - 5, "text-anchor": "middle", class: "ax-title" }, this.svg), xl, 13);
      if (yl) richSVG(sv("text", { x: 1, y: 14, "text-anchor": "start", class: "ax-title" }, this.svg), yl, 13);
      this._box = { x: m.l, y: m.t, width: Math.max(0, w - m.l - m.r), height: Math.max(0, H - m.t - m.b) };
    }
    frame() { if (this._box) sv("rect", Object.assign({ class: "frame" }, this._box), this.svg); }
    legend(items) {
      if (!this.leg) return;
      this.leg.textContent = "";
      this.leg.hidden = !items || !items.length;
      if (!items) return;
      for (const it of items) {
        let sw;
        if (it.shape === "x" || it.shape === "diamond" || it.shape === "ring") sw = h("span", { class: "sw-svg" }, swatchSVG(it.shape, it.color));
        else {
          sw = h("span", { class: "sw " + (it.shape || (it.dash ? "dash" : "")) });
          if (it.shape === "rect" || it.shape === "circle") sw.style.background = it.color; else sw.style.borderTopColor = it.color;
          if (it.shape === "circle hollow") { sw.className = "sw circle hollow"; sw.style.borderColor = it.color; }
        }
        if (it.toggle === false) {
          this.leg.append(h("li", {}, h("span", { class: "static" }, sw, h("span", { rich: it.label }))));
          continue;
        }
        const b = h("button", { type: "button", "aria-pressed": String(!this.hidden.has(it.key)) }, sw, h("span", { rich: it.label }));
        b.addEventListener("click", () => {
          if (this.hidden.has(it.key)) this.hidden.delete(it.key); else this.hidden.add(it.key);
          this.render();
          this.o.onToggle && this.o.onToggle(this.hidden);
        });
        this.leg.append(h("li", {}, b));
      }
    }
  }

  // -------------------------------------------------------------- line chart (crosshair + one tooltip for every series)
  class LineChart extends Chart {
    render() {
      const o = this.o, { w, H } = this.begin();
      const series = o.series.filter((s) => !this.hidden.has(s.key));
      const allX = [], allY = [];
      for (const s of series) for (const p of s.pts) if (p[1] != null) { allX.push(p[0]); allY.push(p[1]); if (p[2] != null) { allY.push(p[2], p[3]); } }
      for (const r of o.refs || []) if (r.y != null) allY.push(r.y);
      const xd = o.x.domain || (allX.length ? [Math.min(...allX), Math.max(...allX)] : [0, 1]);
      const yd = o.y.domain || (allY.length ? niceDomain(Math.min(...allY), Math.max(...allY), 5) : [0, 1]);
      const xt = o.x.ticks || ticks(xd[0], xd[1], Math.max(3, Math.min(8, w / 85)));
      const yt = o.y.ticks || ticks(yd[0], yd[1], Math.max(3, Math.min(7, H / 48)));
      const xdec = decimalsFor(xt), ydec = decimalsFor(yt);
      const xfmt = o.x.fmt || ((v) => fx(v, xdec)), yfmt = o.y.fmt || ((v) => fx(v, ydec));
      const ml = 17 + Math.max(1, ...yt.map((tk) => plainLen(yfmt(tk)))) * 7.2;
      const m = { l: ml, r: o.mr || 16, t: o.y.label ? 30 : 12, b: o.x.label ? 46 : 28 };
      const x = lin(xd[0], xd[1], m.l, w - m.r), y = lin(yd[0], yd[1], H - m.b, m.t);
      this.axes({ x, y, xt, yt, xfmt, yfmt, xl: o.x.label, yl: o.y.label, m, w, H });
      for (const b of o.bands || []) sv("rect", { class: "band", x: m.l, width: w - m.l - m.r, y: y(b[1]), height: Math.max(0, y(b[0]) - y(b[1])) }, this.svg);
      const rg = sv("g", { class: "ref" }, this.svg);
      for (const r of o.refs || []) {
        if (r.y == null || r.y < yd[0] || r.y > yd[1]) continue;
        sv("line", { x1: m.l, x2: w - m.r, y1: y(r.y), y2: y(r.y), "stroke-dasharray": r.dash || null }, rg);
        if (r.at === "left") richSVG(sv("text", { x: m.l + 4, y: y(r.y) + 14, "text-anchor": "start" }, rg), r.label, 11);
        else richSVG(sv("text", { x: w - m.r - 2, y: y(r.y) - 4, "text-anchor": "end" }, rg), r.label, 11);
      }
      const clip = `c${Math.random().toString(36).slice(2)}`;
      const cp = sv("clipPath", { id: clip }, this.svg);
      sv("rect", { x: m.l, y: m.t - 2, width: w - m.l - m.r, height: H - m.t - m.b + 4 }, cp);
      const sg = sv("g", { class: "series", "clip-path": `url(#${clip})` }, this.svg);
      for (const s of series) {
        if (s.line !== false) {
          let d = "", pen = false;
          for (const p of s.pts) {
            if (p[1] == null || !isFinite(p[1])) { pen = false; continue; }
            d += (pen ? "L" : "M") + x(p[0]).toFixed(1) + "," + y(Math.max(yd[0] - 1, Math.min(yd[1] + 1, p[1]))).toFixed(1);
            pen = true;
          }
          sv("path", { d, class: "ln" + (s.thin ? " thin" : "") + (s.faint ? " faint" : ""), stroke: s.color,
            "stroke-dasharray": s.dash || null, "stroke-width": s.width || null }, sg);
        }
        if (s.err) for (const p of s.pts) if (p[2] != null) {
          const eg = sv("g", { class: "err" }, sg);
          sv("line", { x1: x(p[0]), x2: x(p[0]), y1: y(p[2]), y2: y(p[3]), stroke: s.color }, eg);
          for (const yy of [p[2], p[3]]) sv("line", { x1: x(p[0]) - 4, x2: x(p[0]) + 4, y1: y(yy), y2: y(yy), stroke: s.color }, eg);
        }
        if (s.markers) for (const p of s.pts) if (p[1] != null && p[1] >= yd[0] && p[1] <= yd[1]) {
          if (s.shape) marker(sg, s.shape, x(p[0]), y(p[1]), s.r || 4, s.color);
          else sv("circle", { cx: x(p[0]), cy: y(p[1]), r: s.r || 3.5, class: s.hollow ? "ring" : "dot", fill: s.hollow ? null : s.color, stroke: s.hollow ? s.color : null }, sg);
        }
      }
      if (o.endLabels) {
        const lab = series.filter((s) => s.endLabel).map((s) => {
          const last = [...s.pts].reverse().find((p) => p[1] != null);
          return last ? { s, yv: y(last[1]), xv: o.endLabelsAtFrame ? w - m.r - 3 : x(last[0]) } : null;
        }).filter(Boolean).sort((a, b) => a.yv - b.yv);
        for (let i = 1; i < lab.length; i++) if (lab[i].yv - lab[i - 1].yv < 14) lab[i].yv = lab[i - 1].yv + 14;
        for (const l of lab) richSVG(sv("text", { x: l.xv + 9, y: l.yv + 4, class: "lbl", style: `fill:${l.s.labelColor || l.s.color}`, "font-weight": 600 }, this.svg), l.s.endLabel, 12.5);
      }
      this.frame();
      this.cross = sv("line", { class: "cross", y1: m.t, y2: H - m.b, visibility: "hidden" }, this.svg);
      const xs = [...new Set(series.flatMap((s) => s.pts.filter((p) => p[1] != null).map((p) => p[0])))].sort((a, b) => a - b);
      this.sc = { x, y, m, w, H, series, xs, xd };
      this.legend(o.legendItems || o.series.filter((s) => s.legend !== false).map((s) => ({ key: s.key, label: s.label, color: s.color, dash: s.dash,
        shape: s.legendShape })));
      if (this._ki != null) this._showAt(this.sc.xs[this._ki]);
    }
    _showAt(xv) {
      const { x, series, m } = this.sc;
      if (xv == null) return;
      const rows = [];
      for (const s of series) {
        if (s.tip === false) continue;
        let best = null, bd = Infinity;
        for (const p of s.pts) { const d = Math.abs(p[0] - xv); if (p[1] != null && d < bd) { bd = d; best = p; } }
        const tol = this.o.tipTol != null ? this.o.tipTol : (this.sc.xd[1] - this.sc.xd[0]) / 40;
        if (best && bd <= tol) rows.push({ color: s.color, dash: s.dash, value: (this.o.y.tip || this.o.y.fmt || ((v) => fx(v, 3)))(best[1], s, best), label: s.label, yv: best[1] });
      }
      if (!rows.length) return this._hide();
      if (this.o.sortTip !== false) rows.sort((a, b) => b.yv - a.yv);
      this.cross.setAttribute("x1", x(xv)); this.cross.setAttribute("x2", x(xv));
      this.cross.setAttribute("visibility", "visible");
      this.showTip(x(xv), m.t + 4, rows, (this.o.x.tip || ((v) => fx(v, 2)))(xv));
    }
    _move(ev) {
      if (!this.sc || !this.sc.xs.length) return;
      const [px] = this._pt(ev);
      const xv = this.sc.x.inv(px);
      let best = 0;
      for (let i = 1; i < this.sc.xs.length; i++) if (Math.abs(this.sc.xs[i] - xv) < Math.abs(this.sc.xs[best] - xv)) best = i;
      this._ki = best;
      this._showAt(this.sc.xs[best]);
    }
    _key(ev) {
      if (!this.sc || !this.sc.xs.length) return;
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault();
      this._ki = Math.max(0, Math.min(this.sc.xs.length - 1, (this._ki == null ? 0 : this._ki) + (ev.key === "ArrowRight" ? 1 : -1)));
      this._showAt(this.sc.xs[this._ki]);
    }
  }

  // -------------------------------------------------------------- scatter (nearest-point hover, tap to pick)
  class Scatter extends Chart {
    render() {
      const o = this.o, { w, H } = this.begin();
      const groups = o.groups.filter((g) => !this.hidden.has(g.key));
      const xs = [], ys = [];
      for (const g of o.groups) for (const p of g.pts) if (p.x != null && p.y != null) { xs.push(p.x); ys.push(p.y); }
      if (!xs.length) { xs.push(0, 1); ys.push(0, 1); }
      const xd = o.x.domain || niceDomain(Math.min(...xs), Math.max(...xs), 5);
      const yd = o.y.domain || niceDomain(Math.min(...ys), Math.max(...ys), 5);
      const xt = o.x.ticks || ticks(xd[0], xd[1], Math.max(3, Math.min(7, w / 90)));
      const yt = o.y.ticks || ticks(yd[0], yd[1], Math.max(3, Math.min(7, H / 50)));
      const xfmt = o.x.fmt || ((v) => fx(v, decimalsFor(xt))), yfmt = o.y.fmt || ((v) => fx(v, decimalsFor(yt)));
      const m = { l: 17 + Math.max(1, ...yt.map((tk) => plainLen(yfmt(tk)))) * 7.2, r: 16, t: o.y.label ? 30 : 12, b: o.x.label ? 46 : 28 };
      const x = lin(xd[0], xd[1], m.l, w - m.r), y = lin(yd[0], yd[1], H - m.b, m.t);
      this.axes({ x, y, xt, yt, xfmt, yfmt, xl: o.x.label, yl: o.y.label, m, w, H });
      for (const v of o.vlines || []) {
        const g = sv("g", { class: "ref" }, this.svg);
        sv("line", { x1: x(v.x), x2: x(v.x), y1: m.t, y2: H - m.b, "stroke-dasharray": "3 3" }, g);
        if (v.label) richSVG(sv("text", { x: x(v.x) + 4, y: m.t + 10 }, g), v.label, 11);
      }
      const sg = sv("g", { class: "series" }, this.svg);
      const pts = [];
      for (const g of groups) {
        for (const p of g.pts) {
          const cx = x(p.x), cy = y(p.y), r = p.r || g.r || 4;
          const hollow = p.hollow != null ? p.hollow : g.hollow;
          sv("circle", { cx: cx.toFixed(1), cy: cy.toFixed(1), r, class: hollow ? "ring" : "dot", fill: hollow ? null : (p.color || g.color),
            stroke: hollow ? (p.color || g.color) : null, opacity: g.opacity || null }, sg);
          pts.push({ cx, cy, p, g });
        }
      }
      this.frame();
      if (o.highlight) {
        const hl = pts.filter((q) => q.p.id === o.highlight);
        for (const q of hl) sv("circle", { cx: q.cx, cy: q.cy, r: (q.p.r || q.g.r || 4) + 4, fill: "none", stroke: "var(--ink)", "stroke-width": 2 }, sg);
      }
      this.lift = sv("circle", { r: 0, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5, visibility: "hidden" }, this.svg);
      this.sc = { x, y, pts, m, w, H };
      this.legend(o.legendItems || o.groups.filter((g) => g.legend !== false).map((g) => ({ key: g.key, label: g.label, color: g.color,
        shape: g.hollow ? "circle hollow" : "circle", toggle: g.toggle })));
    }
    _nearest(ev) {
      if (!this.sc) return null;
      const [px, py] = this._pt(ev);
      let best = null, bd = 24 * 24;
      for (const q of this.sc.pts) { const d = (q.cx - px) ** 2 + (q.cy - py) ** 2; if (d < bd) { bd = d; best = q; } }
      return best;
    }
    _move(ev) {
      const q = this._nearest(ev);
      if (!q) return this._hide();
      this.lift.setAttribute("cx", q.cx); this.lift.setAttribute("cy", q.cy);
      this.lift.setAttribute("r", (q.p.r || q.g.r || 4) + 3); this.lift.setAttribute("visibility", "visible");
      const tp = this.o.tip ? this.o.tip(q.p, q.g) : { head: q.p.id, rows: [] };
      this.showTip(q.cx, q.cy, tp.rows, tp.head);
    }
    _hide() { super._hide(); if (this.lift) this.lift.setAttribute("visibility", "hidden"); }
    _click(ev) { const q = this._nearest(ev); if (q && this.o.onPick) this.o.onPick(q.p, q.g); }
  }

  // -------------------------------------------------------------- grouped bars with confidence intervals
  class Bars extends Chart {
    render() {
      const o = this.o, { w, H } = this.begin();
      const series = o.series.filter((s) => !this.hidden.has(s.key));
      let mx = 0;
      for (const s of series) s.vals.forEach((v, i) => { mx = Math.max(mx, v, s.hi ? s.hi[i] : v); });
      for (const r of o.refs || []) mx = Math.max(mx, r.y);
      const yd = o.y.domain || [0, niceDomain(0, mx * (o.notes || o.valueLabels ? 1.16 : 1.05), 5)[1]];
      const yt = ticks(yd[0], yd[1], Math.max(3, Math.min(6, H / 50)));
      const yfmt = o.y.fmt || ((v) => fx(v, decimalsFor(yt)));
      const m = { l: 17 + Math.max(1, ...yt.map((tk) => plainLen(yfmt(tk)))) * 7.2, r: 16, t: o.y.label ? 30 : 12, b: 34 };
      const y = lin(yd[0], yd[1], H - m.b, m.t);
      const n = o.cats.length, band = (w - m.l - m.r) / n;
      const ns = Math.max(1, series.length), bw = Math.min(o.barMax || 28, (band * 0.72 - (ns - 1) * 2) / ns);
      const x = (i) => m.l + band * (i + 0.5);
      this.axes({ x, y, xt: [], yt, xfmt: () => "", yfmt, yl: o.y.label, m, w, H });
      const tk = sv("g", { class: "tick" }, this.svg);
      o.cats.forEach((c, i) => richSVG(sv("text", { x: x(i), y: H - m.b + 20, "text-anchor": "middle" }, tk), c, 13));
      const rg = sv("g", { class: "ref" }, this.svg);
      for (const r of o.refs || []) {
        sv("line", { x1: m.l, x2: w - m.r, y1: y(r.y), y2: y(r.y), "stroke-dasharray": r.dash || "4 3", style: r.color ? `stroke:${r.color}` : null }, rg);
        richSVG(sv("text", { x: w - m.r - 4, y: y(r.y) - 5, "text-anchor": "end", style: r.color ? `fill:${r.color}` : null }, rg), r.label, 12);
      }
      const g = sv("g", { class: "series" }, this.svg);
      this.bars = [];
      o.cats.forEach((c, i) => {
        let top = 0;
        series.forEach((s, j) => {
          const v = s.vals[i];
          if (v == null) return;
          const x0 = x(i) - (ns * bw + (ns - 1) * 2) / 2 + j * (bw + 2), x1 = x0 + bw, yb = y(0), yt_ = y(v);
          const p = sv("rect", { x: x0.toFixed(1), y: Math.min(yb, yt_).toFixed(1), width: bw.toFixed(1), height: Math.abs(yb - yt_).toFixed(1),
            fill: s.colors ? s.colors[i] : s.color, class: "bar", stroke: o.outline ? "var(--frame)" : null, "stroke-width": o.outline ? 0.8 : null }, g);
          if (s.lo && s.hi) {
            const eg = sv("g", { class: "err", stroke: "var(--frame)" }, g), cx = (x0 + x1) / 2;
            sv("line", { x1: cx, x2: cx, y1: y(s.lo[i]), y2: y(s.hi[i]) }, eg);
            sv("line", { x1: cx - 3, x2: cx + 3, y1: y(s.lo[i]), y2: y(s.lo[i]) }, eg);
            sv("line", { x1: cx - 3, x2: cx + 3, y1: y(s.hi[i]), y2: y(s.hi[i]) }, eg);
          }
          if (o.valueLabels) sv("text", { x: (x0 + x1) / 2, y: yt_ - 6, "text-anchor": "middle", class: "val" }, g).textContent = fx(v, 2);
          top = Math.max(top, s.hi ? s.hi[i] : v);
          this.bars.push({ x0: x0 - 1, x1: x1 + 1, p, i, s, cx: (x0 + x1) / 2, cy: yt_ });
        });
        const note = o.notes && o.notes[i];
        if (note) sv("text", { x: x(i), y: y(top) - 9, "text-anchor": "middle", class: "val", style: note.color ? `fill:${note.color}` : null }, g).textContent = note.text;
      });
      this.frame();
      this.sc = { m, H };
      this.legend(o.series.map((s) => ({ key: s.key, label: s.label, color: s.color, shape: "rect" })));
    }
    _move(ev) {
      if (!this.bars) return;
      const [px] = this._pt(ev);
      const b = this.bars.find((q) => px >= q.x0 && px <= q.x1);
      for (const q of this.bars) q.p.classList.toggle("lift", q === b);
      if (!b) return this._hide();
      const s = b.s, i = b.i;
      const ci = s.lo ? ` [${fx(s.lo[i], 3)}, ${fx(s.hi[i], 3)}]` : "";
      this.showTip(b.cx, b.cy, [{ color: s.colors ? s.colors[i] : s.color, value: fx(s.vals[i], this.o.tipDigits || 3) + ci, label: s.label }], this.o.cats[i]);
    }
    _hide() { super._hide(); if (this.bars) for (const q of this.bars) q.p.classList.remove("lift"); }
  }

  // -------------------------------------------------------------- horizontal dot plot (log x), several marker shapes
  class DotRows extends Chart {
    render() {
      const o = this.o;
      const rowH = 42;
      this.o.height = () => o.rows.length * rowH + 78;
      const { w, H } = this.begin();
      const series = o.series.filter((s) => !this.hidden.has(s.key));
      const lx = (v) => Math.log10(v);
      const narrow = w < 560;
      const labW = narrow ? 0 : 170;
      const m = { l: 10 + labW, r: 16, t: 34, b: 48 };
      const x = lin(lx(o.x.min), lx(o.x.max), m.l, w - m.r);
      const g = sv("g", { class: "grid" }, this.svg);
      const tk = sv("g", { class: "tick" }, this.svg);
      for (const tv of o.x.ticks) {
        sv("line", { x1: x(lx(tv)), x2: x(lx(tv)), y1: m.t - 8, y2: H - m.b }, g);
        sv("line", { x1: x(lx(tv)), x2: x(lx(tv)), y1: H - m.b, y2: H - m.b + 5 }, tk);
        sv("text", { x: x(lx(tv)), y: H - m.b + 19, "text-anchor": "middle" }, tk).textContent = String(tv);
      }
      richSVG(sv("text", { x: (m.l + w - m.r) / 2, y: H - 5, "text-anchor": "middle", class: "ax-title" }, this.svg), o.x.label, 13);
      const rg = sv("g", { class: "ref" }, this.svg);
      for (const r of o.refs || []) {
        sv("line", { x1: x(lx(r.x)), x2: x(lx(r.x)), y1: m.t - 8, y2: H - m.b, "stroke-dasharray": r.dash || "4 3", style: r.color ? `stroke:${r.color}` : null }, rg);
        richSVG(sv("text", { x: x(lx(r.x)) + (r.anchor === "end" ? -4 : 4), y: m.t - 13, "text-anchor": r.anchor || "start", style: r.color ? `fill:${r.color}` : null }, rg), r.label, 12);
      }
      const yrow = (i) => m.t + rowH * i + rowH / 2;
      const sg = sv("g", { class: "series" }, this.svg);
      this.marks = [];
      o.rows.forEach((row, i) => {
        if (narrow) richSVG(sv("text", { x: m.l + 4, y: yrow(i) - 9, class: "lbl" }, this.svg), row.label, 13);
        else richSVG(sv("text", { x: m.l - 10, y: yrow(i) + 4.5, "text-anchor": "end", class: "lbl" }, this.svg), row.label, 13);
        series.forEach((s, j) => {
          const v = s.vals[row.key];
          if (v == null) return;
          const cy = yrow(i) + (narrow ? 4 : 0) + (j - (series.length - 1) / 2) * 7;
          const cx = x(lx(Math.max(o.x.min, Math.min(o.x.max, v))));
          marker(sg, s.shape || "circle", cx, cy, 5.5, s.color);
          if (s.labels && !(narrow && s.labels === "left")) {
            const left = s.labels === "left" || (s.labels === "right" && cx > w - m.r - 44);
            sv("text", { x: left ? cx - 10 : cx + 10, y: cy + 4.5, "text-anchor": left ? "end" : "start", class: "lbl", style: `fill:${s.ink || s.color};font-size:12.5px` }, sg).textContent = fx(v, 3);
          }
          this.marks.push({ cx, cy, s, row, v });
        });
      });
      this._box = { x: m.l, y: m.t - 8, width: w - m.l - m.r, height: H - m.b - m.t + 8 };
      this.frame();
      this.sc = { m };
      this.legend(o.series.map((s) => ({ key: s.key, label: s.label, color: s.color, shape: s.shape || "circle" })));
    }
    _move(ev) {
      if (!this.marks) return;
      const [px, py] = this._pt(ev);
      let best = null, bd = 24 * 24;
      for (const q of this.marks) { const d = (q.cx - px) ** 2 + (q.cy - py) ** 2; if (d < bd) { bd = d; best = q; } }
      if (!best) return this._hide();
      this.showTip(best.cx, best.cy, [{ color: best.s.color, value: fx(best.v, 3), label: best.s.label }], best.row.label);
    }
  }

  // -------------------------------------------------------------- forest plot (paired differences)
  class Forest extends Chart {
    render() {
      const o = this.o, rowH = 34;
      const narrow = (this.wrap.clientWidth || 600) < 600;
      this.o.height = () => o.rows.length * (narrow ? rowH + 18 : rowH) + 60;
      const { w, H } = this.begin();
      const labW = narrow ? 0 : 210, valW = narrow ? 0 : 190;
      const m = { l: 10 + labW, r: 10 + valW, t: 14, b: 46 };
      const vals = o.rows.flatMap((r) => [r.lo, r.hi]);
      const xd = niceDomain(Math.min(...vals, -o.band), Math.max(...vals, o.band), 6);
      const x = lin(xd[0], xd[1], m.l, w - m.r);
      const xt = ticks(xd[0], xd[1], 6);
      const g = sv("g", { class: "grid" }, this.svg);
      for (const tv of xt) sv("line", { x1: x(tv), x2: x(tv), y1: m.t, y2: H - m.b }, g);
      sv("rect", { class: "band", x: x(-o.band), width: x(o.band) - x(-o.band), y: m.t, height: H - m.t - m.b }, this.svg);
      sv("line", { x1: x(0), x2: x(0), y1: m.t, y2: H - m.b, stroke: "var(--axis)" }, this.svg);
      const tk = sv("g", { class: "tick" }, this.svg);
      for (const tv of xt) {
        sv("line", { x1: x(tv), x2: x(tv), y1: H - m.b, y2: H - m.b + 5 }, tk);
        sv("text", { x: x(tv), y: H - m.b + 19, "text-anchor": "middle" }, tk).textContent = sgn(tv, decimalsFor(xt));
      }
      richSVG(sv("text", { x: (m.l + w - m.r) / 2, y: H - 5, "text-anchor": "middle", class: "ax-title" }, this.svg), narrow && o.xlabelShort ? o.xlabelShort : o.xlabel, 13);
      const per = narrow ? rowH + 18 : rowH;
      this.marks = [];
      o.rows.forEach((r, i) => {
        const cy = m.t + per * i + per / 2 + (narrow ? 6 : 0);
        const lab = narrow ? sv("text", { x: m.l + 5, y: cy - 11, class: "lbl" }, this.svg) : sv("text", { x: m.l - 10, y: cy + 4.5, "text-anchor": "end", class: "lbl" }, this.svg);
        richSVG(lab, r.label, 13);
        sv("line", { x1: x(r.lo), x2: x(r.hi), y1: cy, y2: cy, stroke: r.color, "stroke-width": 2, "stroke-linecap": "butt" }, this.svg);
        for (const xv of [r.lo, r.hi]) sv("line", { x1: x(xv), x2: x(xv), y1: cy - 4, y2: cy + 4, stroke: r.color, "stroke-width": 2 }, this.svg);
        sv("circle", { cx: x(r.delta), cy, r: 4.5, class: "dot", fill: r.color }, this.svg);
        const txt = `${sgn(r.delta, 1)} [${sgn(r.lo, 1)}, ${sgn(r.hi, 1)}], ${r.wins}/${r.n}`;
        if (!narrow) sv("text", { x: w - m.r + 12, y: cy + 4, class: "lbl" }, this.svg).textContent = txt;
        else sv("text", { x: w - m.r - 5, y: cy - 11, "text-anchor": "end", class: "lbl" }, this.svg).textContent = txt;
        this.marks.push({ cy, r });
      });
      this._box = { x: m.l, y: m.t, width: w - m.l - m.r, height: H - m.t - m.b };
      this.frame();
      this.sc = { x };
      this.legend([]);
    }
    _move(ev) {
      if (!this.marks) return;
      const [, py] = this._pt(ev);
      const b = this.marks.reduce((a, q) => (Math.abs(q.cy - py) < Math.abs(a.cy - py) ? q : a), this.marks[0]);
      if (!b || Math.abs(b.cy - py) > 20) return this._hide();
      const r = b.r;
      this.showTip(this.sc.x(r.delta), b.cy, [
        { color: r.color, value: `${sgn(r.delta, 2)} ×10^{-3}`, label: t("mean difference", "평균 차이") },
        { value: `[${sgn(r.lo, 2)}, ${sgn(r.hi, 2)}]`, label: t("95 % interval", "95 % 구간") },
        { value: `${r.wins}/${r.n}`, label: t("seeds where the first is lower", "앞 정책이 낮은 시드") }], r.label);
    }
  }

  // -------------------------------------------------------------- waterfall: S1 -> repeat -> S1x2 -> 423 K-specific -> S2
  class Waterfall extends Chart {
    render() {
      const o = this.o, { w, H } = this.begin();
      const vals = o.steps.flatMap((s) => (s.kind === "bar" ? [s.v] : [s.from, s.to]));
      const top = Math.max(0.01, ...vals);
      const yd = [0, niceDomain(0, top * 1.3, 5)[1]];
      const yt = ticks(yd[0], yd[1], Math.max(3, Math.min(6, H / 55)));
      const yfmt = (v) => fx(v, decimalsFor(yt));
      const m = { l: 17 + Math.max(1, ...yt.map((tk) => plainLen(yfmt(tk)))) * 7.2, r: 12, t: 30, b: 48 };
      const n = o.steps.length, band = (w - m.l - m.r) / n;
      const narrow = band < 96;
      const x = (i) => m.l + band * (i + 0.5);
      const y = lin(yd[0], yd[1], H - m.b, m.t);
      this.axes({ x, y, xt: [], yt, xfmt: () => "", yfmt, yl: o.y.label, m, w, H });
      const bw = Math.min(70, band * 0.6);
      const g = sv("g", { class: "series" }, this.svg);
      const tk = sv("g", { class: "tick" }, this.svg);
      const fs = narrow ? 11.5 : 13;
      this.marks = [];
      let prev = null;
      o.steps.forEach((s, i) => {
        const cx = x(i), x0 = cx - bw / 2;
        (narrow && s.short ? s.short : s.lines).forEach((ln, k) => richSVG(sv("text", { x: cx, y: H - m.b + 17 + k * 15, "text-anchor": "middle", class: k ? "sub" : null }, tk), ln, k ? fs - 1 : fs));
        const start = s.kind === "bar" ? s.v : s.from, end = s.kind === "bar" ? s.v : s.to;
        if (prev != null) {             // dotted connector at the level shared with the previous column
          sv("line", { x1: x(i - 1) + bw / 2, x2: x0, y1: y(start), y2: y(start), stroke: "var(--axis)", "stroke-dasharray": "2 3" }, g);
        }
        if (s.kind === "bar") {
          sv("rect", { x: x0, y: y(s.v), width: bw, height: y(0) - y(s.v), fill: s.color, stroke: "var(--frame)", "stroke-width": 0.8 }, g);
          sv("text", { x: cx, y: y(s.v) - 7, "text-anchor": "middle", class: "val" }, g).textContent = fx(s.v, 3);
          this.marks.push({ x0, x1: x0 + bw, cx, cy: y(s.v), s });
        } else {
          const a = Math.max(s.from, s.to), b = Math.min(s.from, s.to);
          sv("rect", { x: x0, y: y(a), width: bw, height: Math.max(1.5, y(b) - y(a)), fill: s.dash ? "none" : s.color,
            stroke: s.color, "stroke-width": s.dash ? 1.8 : 0.8, "stroke-dasharray": s.dash ? "5 3" : null }, g);
          sv("text", { x: cx, y: y(a) - 7, "text-anchor": "middle", class: "val", style: `fill:${s.ink || s.color}` }, g).textContent = sgn(s.to - s.from, 3);
          if (s.share != null) {
            const txt = narrow ? `${Math.round(s.share * 100)} %` : t(`${Math.round(s.share * 100)} % of the reduction`, `감소분의 ${Math.round(s.share * 100)} %`);
            sv("text", { x: cx, y: y(a) - 24, "text-anchor": "middle", class: "note", style: `fill:${s.ink || s.color}` }, g).textContent = txt;
          }
          this.marks.push({ x0, x1: x0 + bw, cx, cy: y(a), s });
        }
        prev = end;
      });
      this.frame();
      this.legend([]);
    }
    _move(ev) {
      if (!this.marks) return;
      const [px] = this._pt(ev);
      const b = this.marks.find((q) => px >= q.x0 - 6 && px <= q.x1 + 6);
      if (!b) return this._hide();
      const s = b.s, head = s.lines.join(" ");
      if (s.kind === "bar") return this.showTip(b.cx, b.cy, [{ color: s.color, value: fx(s.v, 4), label: MAE }], head);
      const rows = [{ color: s.color, value: sgn(s.to - s.from, 4), label: t("change", "변화") }];
      if (s.ci) rows.push({ value: `[${fx(s.ci[0], 4)}, ${fx(s.ci[1], 4)}]`, label: t("95 % interval", "95 % 구간") });
      if (s.share != null) rows.push({ value: `${Math.round(s.share * 100)} %`, label: t("of S1 → S2", "S1 → S2 대비") });
      this.showTip(b.cx, b.cy, rows, head);
    }
  }

  // -------------------------------------------------------------- slope chart: one value at 300 K and one at 423 K per series
  class Slope extends Chart {
    render() {
      const o = this.o, { w, H } = this.begin();
      const series = o.series.filter((s) => !this.hidden.has(s.key));
      const vals = series.flatMap((s) => s.v);
      const yd = niceDomain(Math.min(0, ...vals), Math.max(0, ...vals), 5);
      const labW = Math.min(132, Math.max(92, w * 0.27));
      const m = { l: labW, r: labW, t: 14, b: 34 };
      const xa = m.l, xb = w - m.r;
      const y = lin(yd[0], yd[1], H - m.b, m.t);
      sv("line", { x1: xa - 16, x2: xb + 16, y1: y(0), y2: y(0), class: "zero" }, this.svg);
      sv("text", { x: xa, y: H - 10, "text-anchor": "middle", class: "col-lab" }, this.svg).textContent = "300 K";
      sv("text", { x: xb, y: H - 10, "text-anchor": "middle", class: "col-lab" }, this.svg).textContent = "423 K";
      const g = sv("g", { class: "series" }, this.svg);
      for (const s of series) {
        sv("line", { x1: xa, x2: xb, y1: y(s.v[0]), y2: y(s.v[1]), stroke: s.color, "stroke-width": 2.4 }, g);
        for (const [xx, v] of [[xa, s.v[0]], [xb, s.v[1]]]) sv("circle", { cx: xx, cy: y(v), r: 5, fill: s.color, stroke: "var(--frame)", "stroke-width": 0.8 }, g);
      }
      const place = (side) => {                    // labels on one side, pushed apart vertically
        const L = series.map((s) => ({ s, yv: y(s.v[side]) })).sort((a, b) => a.yv - b.yv);
        for (let i = 1; i < L.length; i++) if (L[i].yv - L[i - 1].yv < 16) L[i].yv = L[i - 1].yv + 16;
        for (const l of L) {
          const txt = side === 0 ? `${l.s.label}  ${o.fmt(l.s.v[0])}` : o.fmt(l.s.v[1]);
          richSVG(sv("text", { x: side === 0 ? xa - 12 : xb + 12, y: l.yv + 4.5, "text-anchor": side === 0 ? "end" : "start", class: "lbl",
            style: `fill:${l.s.ink || l.s.color}`, "font-weight": 600 }, g), txt, 13);
        }
      };
      place(0);
      place(1);
      this.legend(o.series.map((s) => ({ key: s.key, label: s.label, color: s.color, shape: "rect" })));
    }
  }

  // -------------------------------------------------------------- paired dots on a linear axis (LLM overlap, poster Fig. 8)
  class DotPairs extends Chart {
    render() {
      const o = this.o, rowH = 36;
      const narrow = (this.wrap.clientWidth || 600) < 560;
      this.o.height = () => o.rows.length * (narrow ? rowH + 14 : rowH) + 74 + (o.rows.some((r) => r.note) && !narrow ? 12 : 0);
      const { w, H } = this.begin();
      const labW = narrow ? 0 : 160;
      const m = { l: 10 + labW, r: 18, t: 28, b: 46 };
      const x = lin(o.x.min, o.x.max, m.l, w - m.r);
      const xt = ticks(o.x.min, o.x.max, narrow ? 4 : 6);
      const g = sv("g", { class: "grid" }, this.svg);
      const tk = sv("g", { class: "tick" }, this.svg);
      for (const tv of xt) {
        sv("line", { x1: x(tv), x2: x(tv), y1: m.t, y2: H - m.b }, g);
        sv("line", { x1: x(tv), x2: x(tv), y1: H - m.b, y2: H - m.b + 5 }, tk);
        sv("text", { x: x(tv), y: H - m.b + 19, "text-anchor": "middle" }, tk).textContent = fx(tv, 2);
      }
      richSVG(sv("text", { x: (m.l + w - m.r) / 2, y: H - 5, "text-anchor": "middle", class: "ax-title" }, this.svg), o.x.label, 13);
      const rg = sv("g", { class: "ref" }, this.svg);
      sv("line", { x1: x(o.ref), x2: x(o.ref), y1: m.t, y2: H - m.b, "stroke-dasharray": "2 3" }, rg);
      sv("text", { x: x(o.ref) - 5, y: m.t - 8, "text-anchor": "end" }, rg).textContent = o.refLabel;
      const id = "a" + Math.random().toString(36).slice(2);
      const defs = sv("defs", {}, this.svg);
      const mk = sv("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
      sv("path", { d: "M0,0L10,5L0,10Z", fill: o.arrow }, mk);
      const per = narrow ? rowH + 14 : rowH;
      this.marks = [];
      o.rows.forEach((r, i) => {
        const cy = m.t + per * i + per / 2 + (narrow ? 7 : 0);
        if (narrow) richSVG(sv("text", { x: m.l + 4, y: cy - 13, class: "lbl" }, this.svg), r.label, 12.5);
        else richSVG(sv("text", { x: m.l - 10, y: cy + 4.5, "text-anchor": "end", class: "lbl" }, this.svg), r.label, 13);
        const xa = x(r.a), xb = x(r.b), apart = Math.abs(xa - xb) > 10;
        if (apart) {
          sv("line", { x1: xa + (xb > xa ? 8 : -8), x2: xb + (xb > xa ? -11 : 11), y1: cy, y2: cy, stroke: o.arrow, "stroke-width": 1.8, "marker-end": `url(#${id})` }, this.svg);
          if (r.note && !narrow) sv("text", { x: (xa + xb) / 2, y: cy + 16, "text-anchor": "middle", class: "note", style: `fill:${o.arrow}` }, this.svg).textContent = r.note;
        }
        marker(this.svg, "ring", xb, cy, 8, o.colorB);
        marker(this.svg, "circle", xa, cy, 5, o.colorA);
        if (apart) {
          const la = sv("text", { x: Math.min(xa, xb) === xa ? xa - 12 : xa + 12, y: cy + 4.5, "text-anchor": xa < xb ? "end" : "start", class: "val", style: `fill:${o.inkA}` }, this.svg);
          la.textContent = fx(r.a, 2);
          sv("text", { x: xb + (xb > xa ? 14 : -14), y: cy + 4.5, "text-anchor": xb > xa ? "start" : "end", class: "val", style: `fill:${o.inkB}` }, this.svg).textContent = fx(r.b, 2);
        } else {
          sv("text", { x: Math.max(xa, xb) + 14, y: cy + 4.5, "text-anchor": "start", class: "val" }, this.svg).textContent = fx(r.a, 2);
        }
        this.marks.push({ cy, r, cx: Math.max(xa, xb) });
      });
      this._box = { x: m.l, y: m.t, width: w - m.l - m.r, height: H - m.t - m.b };
      this.frame();
      this.legend(o.legendItems);
    }
    _move(ev) {
      if (!this.marks) return;
      const [, py] = this._pt(ev);
      const b = this.marks.reduce((a, q) => (Math.abs(q.cy - py) < Math.abs(a.cy - py) ? q : a), this.marks[0]);
      if (!b || Math.abs(b.cy - py) > 18) return this._hide();
      this.showTip(b.cx, b.cy, b.r.tip, b.r.label);
    }
  }

  // ------------------------------------------------------------------------------------------- figure helpers
  const ghUrl = (p) => `${REPO}/${/\.[a-z0-9]+$/i.test(p) ? "blob" : "tree"}/${COMMIT}/${p}`;
  function figActions() {
    for (const box of document.querySelectorAll(".fig-actions")) {
      const srcs = (box.dataset.src || "").split(/\s+/).filter(Boolean);
      if (srcs.length) {
        const sp = h("span", {}, t("Data ", "원자료 "));
        srcs.forEach((p, i) => {
          if (i) sp.append(", ");
          sp.append(h("a", { href: ghUrl(p), target: "_blank", rel: "noopener" }, p + (/\.[a-z0-9]+$/i.test(p) ? "" : "/")));
        });
        box.append(sp);
      }
      if (box.dataset.code) box.append(h("span", {}, t("Code ", "코드 "), h("a", { href: ghUrl(box.dataset.code), target: "_blank", rel: "noopener" }, box.dataset.code)));
    }
  }
  function tableToggle(figId, getTable) {
    const fig = $(figId), box = fig.querySelector(".fig-actions");
    const wrap = h("div", { class: "table-wrap table-scroll", hidden: true });
    const label = (open) => (open ? t("Hide table", "표 닫기") : t("Show as a table", "표로 보기"));
    const b = h("button", { type: "button", class: "linkbtn", "aria-expanded": "false" }, label(false));
    b.addEventListener("click", () => {
      const open = wrap.hidden;
      wrap.hidden = !open;
      b.setAttribute("aria-expanded", String(open));
      b.textContent = label(open);
      if (open) draw();
    });
    function draw() {
      const tb_ = getTable();
      wrap.textContent = "";
      const tb = h("table", { class: "data" });
      tb.append(h("thead", {}, h("tr", {}, tb_.cols.map((c) => h("th", { rich: c })))));
      tb.append(h("tbody", {}, tb_.rows.map((r) => h("tr", {}, r.map((c) => h("td", { rich: c == null ? "–" : String(c) }))))));
      wrap.append(tb);
    }
    box.append(b);
    box.after(wrap);
    return { refresh: () => { if (!wrap.hidden) draw(); } };
  }
  function seg(host, label, options, value, onChange) {
    const g = h("div", { class: "seg", role: "group", "aria-label": label });
    const set = (v) => { for (const b of g.children) b.setAttribute("aria-pressed", String(b.dataset.v === String(v))); };
    for (const [v, text] of options) {
      const b = h("button", { type: "button", "data-v": String(v), rich: text });
      b.addEventListener("click", () => { set(v); onChange(v); });
      g.append(b);
    }
    set(value);
    const wrap = h("span", {}, h("span", { class: "ctl-label", rich: label + " " }), g);
    host.append(wrap);
    g.setValue = set;
    return g;
  }
  function select(host, label, options, value, onChange) {
    const id = "s" + Math.random().toString(36).slice(2);
    const s = h("select", { class: "sel", id });
    for (const [v, text] of options) s.append(h("option", { value: v, text }));
    s.value = value;
    s.addEventListener("change", () => onChange(s.value));
    host.append(h("span", {}, h("label", { class: "ctl-label", for: id }, label + " "), s));
    return s;
  }
  const NOISE = [["nominal", t("nominal", "기준")], ["high", "2×"]];
  const RHOS = [["0", "0"], ["0.5", "0.5"], ["0.9", "0.9"]];
  const MODELS = [["gp", "GP"], ["ridge", "Ridge"]];

  // ------------------------------------------------------------------------------------------- shared device state
  const shared = { dev: { set: "test", id: C.design.points.test.id[0] }, listeners: [] };
  function pickDevice(set, id, from) {
    shared.dev = { set, id };
    for (const f of shared.listeners) f(from);
  }
  const designU = {};
  for (const set of ["pool", "test"]) C.design.points[set].id.forEach((id, i) => { designU[id] = C.design.points[set].u[i]; });
  const featIndex = {};
  for (const set of ["pool", "test"]) C.features[set].id.forEach((id, i) => { featIndex[id] = { set, i }; });

  // =========================================================================================== I. lab (surrogate I-V)
  function gpPredict(model, U, u) {
    const { amp, ls, alpha, ymu, ysd, mean, comp } = model;
    const k = alpha[0].length, z = new Float64Array(k);
    for (let i = 0; i < U.length; i++) {
      let s = 0;
      for (let d = 0; d < 4; d++) { const q = (u[d] - U[i][d]) / ls[d]; s += q * q; }
      const kv = amp * Math.exp(-0.5 * s), a = alpha[i];
      for (let j = 0; j < k; j++) z[j] += kv * a[j];
    }
    const y = mean.slice();
    for (let j = 0; j < k; j++) {
      const zj = z[j] * ysd[j] + ymu[j], c = comp[j];
      for (let q = 0; q < y.length; q++) y[q] += zj * c[q];
    }
    return y;
  }
  function surrogate(u) {
    const out = {};
    for (const key of Object.keys(SUR.models)) out[key] = gpPredict(SUR.models[key], SUR.train_u, u);
    return out;
  }
  window.__surrogate = surrogate;   // used by the page check

  function deviceDrawing(host) {
    const g0 = C.design.geometry;
    const xh = g0.x_pw_um + 0.5 * g0.wjfet_um;                      // fixed half-pitch
    const td = g0.t_drift_um, ts = g0.t_sub_um;
    const Y = (y) => (y <= 1.4 ? y : y <= td ? 1.4 + ((y - 1.4) / (td - 1.4)) * 0.6 : 2.0 + ((y - td) / ts) * 0.3);
    const S = 100, X = (x) => (x + 0.12) * S, YY = (y) => (y + 0.5) * S;
    const W = (2 * xh + 0.24) * S, Hh = (Y(td + ts) + 0.5 + 0.42) * S;
    const svg = sv("svg", { viewBox: `0 0 ${W.toFixed(0)} ${Hh.toFixed(0)}`, role: "img", "aria-label": t("Planar MOSFET cell cross-section", "평판형 MOSFET 셀 단면") });
    host.append(svg);
    const L = sv("g", {}, svg);
    const OUT = { stroke: "var(--dev-line)", "stroke-width": 1 };
    const rect = (x0, x1, y0, y1, fill, extra) => sv("rect", Object.assign({ x: X(Math.min(x0, x1)), y: YY(Y(y0)), width: Math.abs(x1 - x0) * S, height: (Y(y1) - Y(y0)) * S, fill }, OUT, extra || {}), L);
    const mirror = (x) => 2 * xh - x;
    rect(0, 2 * xh, 0, td, "var(--dev-n)");
    rect(0, 2 * xh, td, td + ts, "var(--dev-sub)");
    sv("rect", { x: X(0), y: YY(Y(td + ts)), width: 2 * xh * S, height: 8, fill: "var(--dev-metal)" }, L);
    const dyn = sv("g", {}, svg);
    // the computed half cell is the left half; the mirrored right half is drawn under a light veil
    sv("rect", { x: X(xh), y: YY(-0.3), width: xh * S + 2, height: YY(Y(td + ts)) + 9 - YY(-0.3), fill: "#ffffff", "fill-opacity": 0.5 }, svg);
    sv("line", { x1: X(xh), x2: X(xh), y1: YY(-0.3), y2: YY(Y(td + ts)) + 9, stroke: "var(--dev-line)", "stroke-width": 1, "stroke-dasharray": "6 4" }, svg);
    const dynT = sv("g", {}, svg);
    const txt = (x, y, s, cls, anchor = "middle", size = 22) => richSVG(sv("text", { x, y, "text-anchor": anchor, "font-size": size, fill: "var(--ink-2)", class: cls || null }, svg), s, size);
    txt(X(xh / 2), YY(Y(5.5)) + 12, t("n^{−} drift (10 µm, 10^{16} cm^{−3})", "n^{−} 드리프트 (10 µm, 10^{16} cm^{−3})"), null, "middle", 19);
    txt(X(xh / 2), YY(Y(td + 0.5)) + 8, t("n^{+} substrate", "n^{+} 기판"), null, "middle", 20);
    txt(X(xh), YY(Y(td + ts)) + 38, "Drain", null, "middle", 20);
    const actv = {};
    function draw(u) {
      dyn.textContent = "";
      dynT.textContent = "";
      const s = C.design.bounds.wjfet_scale.low + u[0] * (C.design.bounds.wjfet_scale.high - C.design.bounds.wjfet_scale.low);
      const shift = 0.5 * (g0.wjfet_um * s - g0.wjfet_um);
      const xpw = g0.x_pw_um - shift, xns1 = g0.x_ns1_um - shift;
      const npw = u[1], q = 1.5 - u[2] * 1.0, mu = 0.8 + u[3] * 0.4;
      const R = (x0, x1, y0, y1, fill, extra) => {
        for (const [a, b] of [[x0, x1], [mirror(x1), mirror(x0)]]) sv("rect", Object.assign({ x: X(a), y: YY(Y(y0)), width: (b - a) * S, height: (Y(y1) - Y(y0)) * S, fill }, OUT, extra || {}), dyn);
      };
      sv("rect", { x: X(xpw), y: YY(0), width: (mirror(xpw) - xpw) * S, height: (Y(g0.d_jfet_um)) * S, fill: "var(--dev-jfet)",
        stroke: actv.k === 0 ? "var(--ink)" : "var(--dev-line)", "stroke-width": actv.k === 0 ? 2.5 : 1 }, dyn);
      R(0, xpw, 0, g0.d_pw_um, "var(--dev-p)", { "fill-opacity": (0.45 + 0.55 * npw).toFixed(2), stroke: actv.k === 1 ? "var(--ink)" : "var(--dev-line)", "stroke-width": actv.k === 1 ? 2.5 : 1 });
      R(0, g0.x_pp_um, 0, g0.d_pp_um, "var(--dev-pplus)");
      R(g0.x_ns0_um, xns1, 0, g0.d_ns_um, "var(--dev-nplus)");
      R(g0.x_ox_start_um, xh, -0.08, 0, "var(--dev-ox)");
      sv("rect", Object.assign({ x: X(g0.x_ox_start_um), y: YY(-0.27), width: (mirror(g0.x_ox_start_um) - g0.x_ox_start_um) * S, height: 0.19 * S, fill: "var(--dev-gate)" }, OUT), dyn);
      R(0, g0.x_src_contact_um, -0.19, 0, "var(--dev-metal)");
      // interface charge: marks along the oxide interface, density follows |Q_it,eff|
      const n = Math.round(6 + q * 10), x0 = g0.x_ox_start_um + 0.05, x1 = mirror(g0.x_ox_start_um) - 0.05;
      for (let i = 0; i < n; i++) {
        const xx = x0 + ((x1 - x0) * (i + 0.5)) / n;
        sv("line", { x1: X(xx) - 5, x2: X(xx) + 5, y1: YY(0) + 6, y2: YY(0) + 6, stroke: "var(--dev-qit)", "stroke-width": actv.k === 2 ? 3.4 : 2.4 }, dyn);
      }
      // channel: electron path under the gate, width follows s_mu
      for (const [a, b] of [[xns1, xpw], [mirror(xns1), mirror(xpw)]]) {
        sv("line", { x1: X(a), x2: X(b), y1: YY(0) + 13, y2: YY(0) + 13, stroke: "var(--c300)", "stroke-width": (2 + mu * 4).toFixed(1),
          "stroke-linecap": "round", opacity: actv.k === 3 ? 1 : 0.75 }, dyn);
      }
      const yd = YY(Y(g0.d_jfet_um)) + 18;
      sv("line", { x1: X(xpw), x2: X(mirror(xpw)), y1: yd, y2: yd, stroke: "var(--ink)", "stroke-width": 1.5 }, dynT);
      for (const xx of [xpw, mirror(xpw)]) sv("line", { x1: X(xx), x2: X(xx), y1: yd - 7, y2: yd + 7, stroke: "var(--ink)", "stroke-width": 1.5 }, dynT);
      const wl = sv("text", { x: X(xh), y: yd + 27, "text-anchor": "middle", "font-size": 21, fill: "var(--ink)", stroke: "#ffffff", "stroke-width": 5,
        "paint-order": "stroke", "stroke-linejoin": "round" }, dynT);
      richSVG(wl, `W_{JFET} = ${fx(g0.wjfet_um * s, 2)} µm`, 21);
      const lab = (x, y, s_, size = 20, fill = "var(--ink)") => richSVG(sv("text", { x, y, "text-anchor": "middle", "font-size": size, fill }, dynT), s_, size);
      lab(X(xpw / 2 + 0.25), YY(Y(0.52)), "P-well");
      lab(X(mirror(xpw / 2 + 0.25)), YY(Y(0.52)), "P-well");
      lab(X(xh - 0.5), YY(Y(0.58)), "JFET");
      lab(X((g0.x_ns0_um + xns1) / 2), YY(Y(0.16)), "n^{+}", 17);
      lab(X(g0.x_pp_um / 2), YY(Y(0.2)), "p^{+}", 17);
      lab(X(g0.x_src_contact_um / 2), YY(-0.27), "Source", 19, "var(--ink-2)");
      lab(X(g0.x_ox_start_um + 0.55), YY(-0.33), "Gate", 19, "var(--ink-2)");
    }
    return { draw, active(k) { actv.k = k; } };
  }

  function initLab() {
    const dev = deviceDrawing($("device"));
    const u = SUR.nominal_u.slice();
    let curve = "t";
    const vgs = C.stage_a.vgs, vds = C.stage_a.vds;
    const sl = $("sliders");
    const vals = [];
    const fmtVar = (v, uu) => {
      const x = physVal(v, uu);
      if (v === "wjfet_scale") return `${fx(x, 2)} µm`;
      if (v === "npwell_scale") return `${fx(x, 2)}×10^{17} cm^{-3}`;
      if (v === "qit_eff_cm2") return `${fx(x, 2)}×10^{12} cm^{-2}`;
      return fx(x, 2);
    };
    VARS.forEach((v, k) => {
      const id = "sl-" + v;
      const val = h("b");
      const inp = h("input", { type: "range", id, min: 0, max: 1, step: 0.005, value: u[k], "aria-describedby": id + "-v" });
      val.id = id + "-v";
      inp.addEventListener("input", () => { u[k] = +inp.value; update(); });
      inp.addEventListener("focus", () => { dev.active(k); update(); });
      inp.addEventListener("pointerdown", () => { dev.active(k); });
      inp.addEventListener("blur", () => { dev.active(null); update(); });
      const lab = h("label", { for: id }, h("span", {}, h("span", { rich: `${NAME[v]} ${SYM[v]}` }),
        v === "mu_channel_scale" ? h("span", { class: "role" }, t("nuisance", "교란 변수")) : null), val);
      sl.append(h("div", { class: "slider" }, lab, inp));
      vals.push({ val, inp });
    });
    const chart = new LineChart("lab-chart", { series: [], x: {}, y: {}, height: (w) => clamp(250, 370, w * 0.72), legend: true, aria: t("Surrogate I–V curves", "근사 모델의 I–V 특성") });
    const rd = $("readout");
    rd.setAttribute("aria-label", t("Features computed by the surrogate", "근사 모델이 계산한 특징값"));
    const allIds = [...C.features.pool.id, ...C.features.test.id];
    function nearest() {
      let best = null, bd = Infinity;
      for (const id of allIds) {
        const q = designU[id]; if (!q) continue;
        let d = 0; for (let k = 0; k < 4; k++) d += (q[k] - u[k]) ** 2;
        if (d < bd) { bd = d; best = id; }
      }
      return { id: best, d: Math.sqrt(bd) };
    }
    function update() {
      const p = surrogate(u);
      vals.forEach((o, k) => { rich(o.val, fmtVar(VARS[k], u[k])); o.inp.value = u[k]; });
      dev.draw(u);
      const nn = nearest(), fi = featIndex[nn.id], F = C.features[fi.set];
      const fl = SUR.log_floor + 0.05;
      const series = [];
      for (const T of [300, 423]) {
        const col = T === 300 ? "var(--c300)" : "var(--c423)", dash = T === 423 ? "6 4" : null;
        if (curve === "t") {
          series.push({ key: "s" + T, label: t(`${T} K surrogate`, `${T} K 근사`), color: col, dash, pts: vgs.map((x, i) => [x, p["t" + T][i] > fl ? p["t" + T][i] : null]) });
          const lg = F[String(T)].logid[fi.i];
          series.push({ key: "d" + T, label: `${T} K ${nn.id} DEVSIM`, color: col, line: false, markers: true, r: 4, legend: false,
            pts: C.features.feature_vgs.map((x, i) => [x, lg[i]]) });
        } else {
          series.push({ key: "s" + T, label: t(`${T} K surrogate`, `${T} K 근사`), color: col, dash, pts: vds.map((x, i) => [x, p["o" + T][i] * 1e3]) });
        }
      }
      if (curve === "t") {
        chart.set({ series, x: { domain: [0, 10], ticks: [0, 2, 4, 6, 8, 10], label: "V_{GS} (V),  V_{DS} = 0.1 V", tip: (v) => `V_{GS} = ${fx(v, 2)} V` },
          y: { domain: [-12, -1], ticks: [-12, -10, -8, -6, -4, -2], fmt: (v) => `10^{${v}}`, label: "I_{D} (A/cm)",
            tip: (v) => sci(Math.pow(10, v)) + " A/cm" }, tipTol: 0.3,
          legendItems: [{ label: "300 K", color: "var(--c300)", toggle: false }, { label: "423 K", color: "var(--c423)", dash: true, toggle: false },
            { label: t(`dots: DEVSIM of ${nn.id}`, `점: ${nn.id}의 DEVSIM 값`), color: "var(--ink-2)", shape: "circle", toggle: false }] });
      } else {
        chart.set({ series, x: { domain: [0, 5], ticks: [0, 1, 2, 3, 4, 5], label: "V_{DS} (V),  V_{GS} = 18 V", tip: (v) => `V_{DS} = ${fx(v, 1)} V` },
          y: { domain: null, ticks: null, fmt: null, label: "I_{D} (mA/cm)", tip: (v) => fx(v, 1) + " mA/cm" }, tipTol: 0.3,
          legendItems: [{ label: "300 K", color: "var(--c300)", toggle: false }, { label: "423 K", color: "var(--c423)", dash: true, toggle: false }] });
      }
      const f3 = p.f300, f4 = p.f423;
      rd.textContent = "";
      rd.append(h("thead", {}, h("tr", {}, h("th", { text: t("Feature (surrogate)", "특징값 (근사 모델)") }),
        h("th", {}, h("span", { class: "key", style: "border-top-color:var(--c300)" }), "300 K"),
        h("th", {}, h("span", { class: "key dash", style: "border-top-color:var(--c423)" }), "423 K"))));
      const rows = [["V_{th} (V)", fx(f3[0], 3), fx(f4[0], 3)], ["SS (mV/dec)", fx(f3[1], 1), fx(f4[1], 1)],
        ["g_{m,max} (mS/cm)", fx(Math.pow(10, f3[2]) * 1e3, 2), fx(Math.pow(10, f4[2]) * 1e3, 2)],
        ["R_{on,sp} (mΩ·cm^{2})", fx(Math.pow(10, f3[3]), 3), fx(Math.pow(10, f4[3]), 3)]];
      rd.append(h("tbody", {}, rows.map((r) => h("tr", {}, h("td", { rich: r[0] }), h("td", { text: r[1] }), h("td", { text: r[2] })))));
      const v3 = fx(SUR.validation["300"].vth_mV_median, 1), v4 = fx(SUR.validation["423"].vth_mV_median, 1);
      rich($("lab-note"), t(
        `(a) Solid 300 K, dashed 423 K. Curves: Gaussian-process surrogate trained on the DEVSIM results of ${SUR.n_train} pool devices; dots: DEVSIM values of the nearest real device, ${nn.id}. Median V_{th} error on ${SUR.n_test} test devices: ${v3} mV (300 K), ${v4} mV (423 K). (b) Only the left half-cell is simulated; the right half is mirrored.`,
        `(a) 실선 300 K, 점선 423 K. 곡선은 후보 풀 ${SUR.n_train}개 소자의 DEVSIM 결과로 학습한 가우시안 과정 근사이고, 점은 설계값이 가장 가까운 실제 소자 ${nn.id}의 DEVSIM 값이다. 시험 소자 ${SUR.n_test}개에서 V_{th} 오차 중앙값은 ${v3} mV(300 K), ${v4} mV(423 K). (b) 왼쪽 반쪽 셀만 계산하고 오른쪽은 대칭으로 그렸다.`));
    }
    for (const b of document.querySelectorAll("[data-curve]")) {
      b.addEventListener("click", () => {
        curve = b.dataset.curve;
        for (const o of document.querySelectorAll("[data-curve]")) o.setAttribute("aria-pressed", String(o === b));
        update();
      });
    }
    $("lab-reset").addEventListener("click", () => { SUR.nominal_u.forEach((v, k) => (u[k] = v)); update(); });
    $("lab-random").addEventListener("click", () => { for (let k = 0; k < 4; k++) u[k] = Math.round(Math.random() * 200) / 200; update(); });
    update();
  }

  // =========================================================================================== I. sensitivity matrix (+20 %)
  const PARS = [["wjfet", "W_{JFET}"], ["npwell", "N_{pw}"], ["qit", "|Q_{it,eff}|"], ["mu", "s_{μ}"]];
  const delta20 = (T, p, f) => { const r = C.stage_a.deltas.find((d) => d.T === T && d.var === p && d.level === "+20pct"); return r ? r[f] : null; };
  function initSens() {
    const feats = [["vth_V", "V_{th}", (v) => sgn(v * 1e3, 0) + " mV", (v) => v * 1e3], ["ss_mV_dec", "SS", (v) => pct(v), (v) => v * 100],
      ["gm_max_S_per_cm", "g_{m,max}", (v) => pct(v), (v) => v * 100], ["ion_A_per_cm", "I_{on}", (v) => pct(v), (v) => v * 100],
      ["ron_mohm_cm2", "R_{on,sp}", (v) => pct(v), (v) => v * 100]];
    const host = $("sens");
    const legend = h("ul", { class: "legend" }, h("li", {}, h("span", { class: "static" }, h("span", { class: "sw rect", style: "background:var(--c300)" }), "300 K")),
      h("li", {}, h("span", { class: "static" }, h("span", { class: "sw rect", style: "background:var(--c423)" }), "423 K")));
    const ctlBox = h("div", { class: "controls" });
    const tableBox = h("div");
    host.append(ctlBox, legend, tableBox);
    let one = "wjfet", narrow = null;
    seg(ctlBox, t("Parameter", "변수"), PARS, one, (v) => { one = v; drawSens(true); });
    function drawSens(force) {
      const nw = host.clientWidth < 620;
      if (!force && nw === narrow) return;
      narrow = nw;
      ctlBox.hidden = !nw;
      const cols = nw ? PARS.filter(([p]) => p === one) : PARS;
      const tb = h("table", { class: "sens" + (nw ? " one" : "") });
      tb.append(h("thead", {}, h("tr", {}, h("th", { text: t("Feature (+20 %)", "특징 (+20 %)") }), cols.map(([, l]) => h("th", { rich: l })))));
      const body = h("tbody");
      for (const [f, lab, fmtv, scale] of feats) {
        const mx = Math.max(...PARS.flatMap(([p]) => [300, 423].map((T) => Math.abs(scale(delta20(T, p, f) || 0))))) || 1;
        const tr = h("tr", {}, h("th", { rich: lab }));
        for (const [p] of cols) {
          const cell = h("div", { class: "cell" });
          for (const T of [300, 423]) {
            const v = delta20(T, p, f), sv_ = scale(v || 0), frac = Math.min(1, Math.abs(sv_) / mx) * 50;
            const bar = h("span", { class: "b" });
            bar.style.background = T === 300 ? "var(--c300)" : "var(--c423)";
            bar.style.width = frac.toFixed(1) + "%";
            bar.style.left = (sv_ >= 0 ? 50 : 50 - frac).toFixed(1) + "%";
            const tr_ = h("span", { class: "track", title: `${T} K` }, h("span", { class: "mid" }), bar);
            cell.append(h("div", { class: "row" }, tr_, h("span", { class: "v", text: fmtv(v) })));
          }
          tr.append(h("td", {}, cell));
        }
        body.append(tr);
      }
      tb.append(body);
      tableBox.textContent = "";
      tableBox.append(tb);
    }
    drawSens(true);
    if (ro) new ResizeObserver(() => drawSens(false)).observe(host);
  }

  // =========================================================================================== II. design
  function initDesign() {
    const b = C.design.bounds;
    const tb = $("vars-table");
    tb.classList.add("left");
    tb.append(h("thead", {}, h("tr", {}, [t("Parameter", "변수"), t("Range", "범위"), t("Design centre", "설계 중심")].map((c) => h("th", { text: c })))));
    const rows = [
      [t("JFET width W_{JFET}", "JFET 폭 W_{JFET}"), `${fx(2.4 * b.wjfet_scale.low, 2)}–${fx(2.4 * b.wjfet_scale.high, 2)} µm ${t("(cell pitch fixed)", "(셀 피치 고정)")}`, "2.40 µm"],
      [t("P-well peak doping N_{pw}", "P-well 최대 도핑 N_{pw}"), `${fx(b.npwell_scale.low, 1)}–${fx(b.npwell_scale.high, 1)}×10^{17} cm^{-3}`, "1.0×10^{17} cm^{-3}"],
      [t("Effective interface charge Q_{it,eff}", "유효 계면전하 Q_{it,eff}"), `${fx(b.qit_eff_cm2.low / 1e12, 1)} ~ ${fx(b.qit_eff_cm2.high / 1e12, 1)}×10^{12} cm^{-2}`, `${fx(-1, 1)}×10^{12} cm^{-2}`],
      [t("Channel-mobility scale s_{μ} (nuisance, not estimated)", "채널 이동도 배율 s_{μ} (교란 변수, 추정하지 않음)"), `${fx(b.mu_channel_scale.low, 1)}–${fx(b.mu_channel_scale.high, 1)}`, "1.0"]];
    tb.append(h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c) => h("td", { rich: c }))))));

    // DOE scatter
    let xv = "wjfet_scale", yv = "npwell_scale";
    const ctl = $("doe-ctl");
    const opts = VARS.map((v) => [v, `${NAME[v]} (${SYM[v].replace(/[_{}]/g, "")})`]);
    const doe = new Scatter("doe-chart", { groups: [], x: {}, y: {}, aria: t("Design points", "설계점 분포"), height: (w) => clamp(240, 380, w * 0.62) });
    const setName = (s) => (s === "pool" ? t("pool", "후보 풀") : t("test", "시험"));
    function draw() {
      const grp = (set, key, label, color, hollow, r) => ({ key, label, color, hollow, r,
        pts: C.design.points[set].id.map((id, i) => ({ id, set, x: physVal(xv, C.design.points[set].u[i][VARS.indexOf(xv)]), y: physVal(yv, C.design.points[set].u[i][VARS.indexOf(yv)]) })) });
      doe.set({ groups: [grp("pool", "pool", t("candidate pool, 512 (Sobol)", "후보 풀 512개 (Sobol)"), "var(--axis)", false, 3.2),
        grp("test", "test", t("test devices, 128 (random)", "시험 소자 128개 (무작위)"), "var(--ink)", true, 3.4)],
        x: { label: axisLabel(xv), domain: physDomain(xv) }, y: { label: axisLabel(yv), domain: physDomain(yv) },
        highlight: shared.dev.id,
        tip: (p) => ({ head: `${p.id} (${setName(p.set)})`, rows: VARS.map((v) => ({ value: physFmt(v, physVal(v, designU[p.id][VARS.indexOf(v)])), label: SYM[v] + (UNIT[v] ? " " + UNIT[v] : "") })) }),
        onPick: (p) => pickDevice(p.set, p.id, "doe") });
    }
    select(ctl, t("x axis", "가로축"), opts, xv, (v) => { xv = v; draw(); });
    select(ctl, t("y axis", "세로축"), opts, yv, (v) => { yv = v; draw(); });
    shared.listeners.push(() => doe.set({ highlight: shared.dev.id }));
    draw();
    tableToggle("fig-doe", () => ({ cols: [t("Device", "소자"), t("Set", "구분"), ...VARS.map((v) => SYM[v] + (UNIT[v] ? ` (${UNIT[v]})` : ""))],
      rows: ["pool", "test"].flatMap((set) => C.design.points[set].id.map((id, i) => [id, setName(set),
        ...VARS.map((v, k) => physFmt(v, physVal(v, C.design.points[set].u[i][k])))])) }));

    // one-at-a-time
    const SA = C.stage_a;
    let par = "wjfet", temps = "both";
    const lv = [["-20pct", "−20 %", "var(--l-m20)"], ["-10pct", "−10 %", "var(--l-m10)"], ["base", t("design centre", "설계 중심"), "var(--ink)"],
      ["+10pct", "+10 %", "var(--l-p10)"], ["+20pct", "+20 %", "var(--l-p20)"]];
    const oc = $("oat-ctl");
    seg(oc, t("Parameter", "변수"), PARS, par, (v) => { par = v; drawOat(); });
    seg(oc, t("Temperature", "온도"), [["both", t("both", "둘 다")], ["300", "300 K"], ["423", "423 K"]], temps, (v) => { temps = v; drawOat(); });
    const ct = new LineChart("oat-t", { series: [], x: {}, y: {}, aria: t("Transfer curves, one parameter changed", "변수 하나를 바꾼 전달 특성"), tipTol: 0.13 });
    const co = new LineChart("oat-o", { series: [], x: {}, y: {}, aria: t("Output curves, one parameter changed", "변수 하나를 바꾼 출력 특성"), legend: false, tipTol: 0.03 });
    function drawOat() {
      const ss = [], so = [];
      for (const [lvl, lab, col] of lv) {
        for (const T of [300, 423]) {
          if (temps !== "both" && String(T) !== temps) continue;
          const r = SA.runs[`${lvl === "base" ? "base" : par + "_" + lvl}@${T}`];
          const dash = T === 423 ? "5 4" : null;
          ss.push({ key: lvl + T, label: `${lab}, ${T} K`, color: col, dash, pts: SA.vgs.map((x, i) => [x, r.t[i]]), legend: false });
          so.push({ key: lvl + T, label: `${lab}, ${T} K`, color: col, dash, pts: SA.vds.map((x, i) => [x, r.o[i] == null ? null : r.o[i] * 1e3]) });
        }
      }
      const leg = lv.map(([, lab, col]) => ({ label: lab, color: col, toggle: false }))
        .concat([{ label: "300 K", color: "var(--ink-2)", toggle: false }, { label: "423 K", color: "var(--ink-2)", dash: true, toggle: false }]);
      ct.set({ series: ss, legendItems: leg, x: { domain: [0, 10], ticks: [0, 2, 4, 6, 8, 10], label: t("V_{GS} (V), transfer", "V_{GS} (V), 전달 특성"), tip: (v) => `V_{GS} = ${fx(v, 2)} V` },
        y: { domain: [-12, -1], ticks: [-12, -10, -8, -6, -4, -2], fmt: (v) => `10^{${v}}`, label: "I_{D} (A/cm)", tip: (v) => sci(Math.pow(10, v)) } });
      co.set({ series: so, x: { domain: [0, 5], ticks: [0, 1, 2, 3, 4, 5], label: t("V_{DS} (V), output, V_{GS} = 18 V", "V_{DS} (V), 출력 특성 V_{GS} = 18 V"), tip: (v) => `V_{DS} = ${fx(v, 1)} V` },
        y: { label: "I_{D} (mA/cm)", tip: (v) => fx(v, 1) + " mA/cm" } });
    }
    drawOat();
    tableToggle("fig-oat", () => {
      const names = lv.map(([l]) => (l === "base" ? "base" : par + "_" + l));
      return { cols: [t("Setting", "설정"), "T (K)", "V_{th} (V)", "SS (mV/dec)", "R_{on,sp} (mΩ·cm^{2})"],
        rows: names.flatMap((n, i) => [300, 423].map((T) => { const r = SA.runs[`${n}@${T}`]; return [lv[i][1], T, fx(r.vth, 3), fx(r.ss, 1), fx(r.ron, 3)]; })) };
    });
  }

  // =========================================================================================== II. simulation data
  const VAR_LABEL = { gamma0: "γ = 0", gamma_m1: "γ = −1", qitT10: "r = 0.1", qitT30: "r = 0.3" };
  const VAR_COLOR = { gamma0: "var(--v-g0)", gamma_m1: "var(--v-gm1)", qitT10: "var(--v-q10)", qitT30: "var(--v-q30)" };
  function initData() {
    const ctl = $("iv-ctl");
    let curve = "t", showVar = false;
    const meta = $("iv-meta");
    let chart = null, ivData = null;
    const setSeg = seg(ctl, t("Set", "구분"), [["pool", t("pool", "후보 풀")], ["test", t("test", "시험")]], shared.dev.set, (v) => { const ids = C.design.points[v].id; pickDevice(v, ids[0], "iv"); });
    const devSel = h("select", { class: "sel", "aria-label": t("Device", "소자") });
    const fillSel = () => {
      devSel.textContent = "";
      for (const id of C.design.points[shared.dev.set].id) devSel.append(h("option", { value: id, text: id }));
      devSel.value = shared.dev.id;
    };
    devSel.addEventListener("change", () => pickDevice(shared.dev.set, devSel.value, "iv"));
    const step = (d) => { const ids = C.design.points[shared.dev.set].id; const i = ids.indexOf(shared.dev.id); pickDevice(shared.dev.set, ids[(i + d + ids.length) % ids.length], "iv"); };
    ctl.append(h("span", {}, h("span", { class: "ctl-label" }, t("Device ", "소자 ")), devSel),
      h("button", { type: "button", class: "btn small", onclick: () => step(-1), "aria-label": t("previous device", "이전 소자") }, t("Previous", "이전")),
      h("button", { type: "button", class: "btn small", onclick: () => step(1), "aria-label": t("next device", "다음 소자") }, t("Next", "다음")),
      h("button", { type: "button", class: "btn small", onclick: () => { const ids = C.design.points[shared.dev.set].id; pickDevice(shared.dev.set, ids[Math.floor(Math.random() * ids.length)], "iv"); } }, t("Random", "무작위")));
    seg(ctl, t("Curve", "곡선"), [["t", t("transfer", "전달")], ["tl", t("transfer (linear)", "전달(선형)")], ["o", t("output", "출력")]], curve, (v) => { curve = v; draw(); });
    const varBox = h("label", { class: "ctl-label", style: "display:inline-flex;gap:6px;align-items:center" },
      h("input", { type: "checkbox", onchange: (e) => { showVar = e.target.checked; draw(); } }), t("Overlay the four other 423 K physics", "423 K 물리 가정 4가지 겹쳐 보기"));
    ctl.append(varBox);
    function draw() {
      fillSel();
      setSeg.setValue(shared.dev.set);
      varBox.style.display = shared.dev.set === "test" ? "inline-flex" : "none";
      const id = shared.dev.id, u = designU[id], fi = featIndex[id];
      meta.textContent = "";
      meta.append(h("span", {}, h("b", { text: id })), ...VARS.map((v, k) => h("span", {}, h("span", { rich: SYM[v] + " " }), h("b", { text: physFmt(v, physVal(v, u[k])) }), UNIT[v] ? h("span", { rich: " " + UNIT[v] }) : null)));
      if (fi) {
        const F = C.features[fi.set];
        meta.append(h("span", {}, h("span", { rich: "V_{th} " }), h("b", { text: `${fx(F["300"].vth[fi.i], 3)} / ${fx(F["423"].vth[fi.i], 3)} V` })),
          h("span", {}, h("span", { rich: "R_{on,sp} " }), h("b", { text: `${fx(F["300"].ron[fi.i], 2)} / ${fx(F["423"].ron[fi.i], 2)}` }), h("span", { rich: " mΩ·cm^{2} (300 / 423 K)" })));
      }
      if (!ivData) return;
      const rec = ivData[shared.dev.set][id];
      const series = [];
      const add = (key, label, color, r, dash) => {
        if (!r) return;
        if (curve === "o") series.push({ key, label, color, dash, pts: ivData.vds.map((x, i) => [x, r.o[i] == null ? null : r.o[i] * 1e3]) });
        else if (curve === "tl") series.push({ key, label, color, dash, pts: ivData.vgs.map((x, i) => [x, r.t[i] == null ? null : Math.pow(10, r.t[i]) * 1e3]) });
        else series.push({ key, label, color, dash, pts: ivData.vgs.map((x, i) => [x, r.t[i]]) });
      };
      add("300", "300 K", "var(--c300)", rec["300"]);
      add("423", "423 K", "var(--c423)", rec["423"], "6 4");
      if (showVar && shared.dev.set === "test") for (const v of Object.keys(VAR_LABEL)) add(v, `423 K, ${VAR_LABEL[v]}`, VAR_COLOR[v], ivData.variants423[v][id], "2 3");
      const o = curve === "o" ? { x: { domain: [0, 5], ticks: [0, 1, 2, 3, 4, 5], label: "V_{DS} (V), V_{GS} = 18 V", tip: (v) => `V_{DS} = ${fx(v, 1)} V` }, y: { label: "I_{D} (mA/cm)", tip: (v) => fx(v, 1) + " mA/cm" }, tipTol: 0.03 }
        : curve === "tl" ? { x: { domain: [0, 20], ticks: [0, 5, 10, 15, 20], label: "V_{GS} (V), V_{DS} = 0.1 V", tip: (v) => `V_{GS} = ${fx(v, 2)} V` }, y: { label: "I_{D} (mA/cm)", tip: (v) => fx(v, 2) + " mA/cm" }, tipTol: 0.13 }
          : { x: { domain: [0, 10], ticks: [0, 2, 4, 6, 8, 10], label: "V_{GS} (V), V_{DS} = 0.1 V", tip: (v) => `V_{GS} = ${fx(v, 2)} V` }, y: { domain: [-12, -1], ticks: [-12, -10, -8, -6, -4, -2], fmt: (v) => `10^{${v}}`, label: "I_{D} (A/cm)", tip: (v) => sci(Math.pow(10, v)) + " A/cm" }, tipTol: 0.13 };
      if (!o.y.domain) { o.y.domain = null; o.y.ticks = null; o.y.fmt = null; }
      chart.set(Object.assign({ series, legendItems: null }, o));
      tbl.refresh();
    }
    const tbl = tableToggle("fig-iv", () => {
      if (!ivData) return { cols: [], rows: [] };
      const rec = ivData[shared.dev.set][shared.dev.id];
      if (curve === "o") return { cols: ["V_{DS} (V)", "300 K I_{D} (A/cm)", "423 K I_{D} (A/cm)"], rows: ivData.vds.map((x, i) => [fx(x, 1), rec["300"] && rec["300"].o[i] != null ? sci(rec["300"].o[i], 3) : null, rec["423"] && rec["423"].o[i] != null ? sci(rec["423"].o[i], 3) : null]) };
      return { cols: ["V_{GS} (V)", "300 K I_{D} (A/cm)", "423 K I_{D} (A/cm)"], rows: ivData.vgs.map((x, i) => [fx(x, 2), rec["300"] && rec["300"].t[i] != null ? sci(Math.pow(10, rec["300"].t[i]), 3) : null, rec["423"] && rec["423"].t[i] != null ? sci(Math.pow(10, rec["423"].t[i]), 3) : null]) };
    });
    shared.listeners.push(() => draw());
    const load = () => need("iv").then((d) => {
      ivData = d;
      $("iv-chart").textContent = "";
      chart = new LineChart("iv-chart", { series: [], x: {}, y: {}, aria: t("I–V of the selected device", "선택한 소자의 I–V 특성") });
      draw();
    }).catch(() => { $("iv-chart").textContent = t("The I–V data could not be loaded.", "I–V 데이터를 불러오지 못했습니다."); });
    whenNear($("fig-iv"), load);
    draw();

    // feature scatter
    let fv = "vth", pv = "npwell_scale";
    const FEAT = { vth: ["V_{th} (V)", 3], ss: ["SS (mV/dec)", 1], gm: ["g_{m,max} (mS/cm)", 2], ron: ["R_{on,sp} (mΩ·cm^{2})", 3], ion: ["I_{on} (mA/cm), V_{GS} = 18 V", 1] };
    const fc = $("feat-ctl");
    select(fc, t("Feature", "특징"), Object.entries(FEAT).map(([k, v]) => [k, v[0].replace(/[_{}^]/g, "")]), fv, (v) => { fv = v; drawF(); });
    select(fc, t("Process parameter", "공정 변수"), VARS.map((v) => [v, `${NAME[v]} (${SYM[v].replace(/[_{}]/g, "")})`]), pv, (v) => { pv = v; drawF(); });
    const sc = new Scatter("feat-chart", { groups: [], x: {}, y: {}, aria: t("Features vs. process parameters", "특징과 공정 변수"), height: (w) => clamp(240, 380, w * 0.62) });
    function drawF() {
      const groups = [300, 423].map((T) => ({ key: String(T), label: `${T} K`, color: T === 300 ? "var(--c300)" : "var(--c423)", r: 2.8,
        pts: ["pool", "test"].flatMap((set) => C.features[set].id.map((id, i) => ({ id, set, T, x: physVal(pv, designU[id][VARS.indexOf(pv)]), y: C.features[set][String(T)][fv][i] }))) }));
      sc.set({ groups, x: { label: axisLabel(pv), domain: physDomain(pv) }, y: { label: FEAT[fv][0], domain: null }, highlight: shared.dev.id,
        tip: (p) => ({ head: `${p.id}, ${p.T} K`, rows: [{ value: fx(p.y, FEAT[fv][1]), label: FEAT[fv][0] }, { value: physFmt(pv, p.x), label: SYM[pv] + (UNIT[pv] ? " " + UNIT[pv] : "") }] }),
        onPick: (p) => pickDevice(p.set, p.id, "feat") });
    }
    shared.listeners.push(() => sc.set({ highlight: shared.dev.id }));
    drawF();
    tableToggle("fig-feat", () => ({ cols: [t("Device", "소자"), SYM[pv], ...[300, 423].map((T) => `${FEAT[fv][0]}, ${T} K`)],
      rows: ["pool", "test"].flatMap((set) => C.features[set].id.map((id, i) => [id, physFmt(pv, physVal(pv, designU[id][VARS.indexOf(pv)])), fx(C.features[set]["300"][fv][i], FEAT[fv][1]), fx(C.features[set]["423"][fv][i], FEAT[fv][1])])) }));
  }

  // =========================================================================================== II. poster Fig. 3: sensitivity at 300/423 K and Cramer-Rao bounds
  function initMech() {
    const FEATS = [["vth_V", "V_{th}", "mV", (v) => v * 1e3], ["ss_mV_dec", "SS", "%", (v) => v * 100], ["gm_max_S_per_cm", "g_{m,max}", "%", (v) => v * 100],
      ["ion_A_per_cm", "I_{on}", "%", (v) => v * 100], ["ron_mohm_cm2", "R_{on,sp}", "%", (v) => v * 100]];
    const COL = { wjfet: ["var(--gain)", "var(--gain-ink)"], npwell: ["#009e73", "#007a59"], qit: ["#0072b2", "#0072b2"], mu: ["#7f7f7f", "#5c5c5c"] };
    const SHOW = { vth_V: ["npwell", "qit"], ion_A_per_cm: ["wjfet", "mu"] };       // the pair each feature cannot tell apart at 300 K
    let feat = "ion_A_per_cm";
    const slope = new Slope("slope-chart", { series: [], fmt: (v) => v, aria: t("Feature change at 300 K and 423 K", "300 K와 423 K의 특징 변화"), height: (w) => clamp(210, 290, w * 0.62) });
    function draw(reset) {
      const [f, , unit, sc_] = FEATS.find((q) => q[0] === feat);
      if (reset) slope.hidden = new Set(SHOW[feat] ? PARS.map((p) => p[0]).filter((p) => !SHOW[feat].includes(p)) : []);
      slope.set({ series: PARS.map(([p, l]) => ({ key: p, label: l, color: COL[p][0], ink: COL[p][1], v: [sc_(delta20(300, p, f)), sc_(delta20(423, p, f))] })),
        fmt: (v) => (unit === "mV" ? `${sgn(v, 0)} mV` : `${sgn(v, 1)} %`) });
    }
    seg($("slope-ctl"), t("Feature", "특징"), FEATS.map((q) => [q[0], q[1]]), feat, (v) => { feat = v; draw(true); });
    draw(true);

    let rho = "0";
    const crb = new Bars("crb-chart", { cats: TGT.map((v) => SYM[v]), series: [], y: { label: t("Bound ratio S2/S1", "하한 비 S2/S1"), domain: [0, 1.1] }, legend: false,
      valueLabels: true, outline: true, barMax: 64, tipDigits: 3, aria: t("Cramér–Rao bound ratio", "Cramér–Rao 하한 비"), height: (w) => clamp(210, 290, w * 0.62) });
    function drawC() {
      const r = C.rq1.crb.S2_over_S1[rho], ref = C.rq1.crb.S1x2_over_S1[rho].wjfet_scale;
      crb.set({ series: [{ key: "crb", label: "S2/S1", color: "var(--s1)", colors: ["var(--gain)", "var(--s1)", "var(--s1)"], vals: TGT.map((v) => r[v]) }],
        refs: [{ y: ref, label: t(`S1×2 (two averaged 300 K): ${fx(ref, 2)}`, `S1×2 (300 K 두 번 평균): ${fx(ref, 2)}`), color: "var(--s2)", dash: "6 4" }] });
    }
    seg($("crb-ctl"), t("Noise correlation ρ", "잡음 상관 ρ"), RHOS, rho, (v) => { rho = v; drawC(); });
    drawC();
  }

  // =========================================================================================== III-1. poster Fig. 4 and the noise realisations
  const SETS = [["S1", t("S1 (300 K ×1)", "S1 (300 K 1회)"), "var(--s1)"], ["S1x2", t("S1×2 (300 K ×2, averaged)", "S1×2 (300 K 2회 평균)"), "var(--s1x2)"],
    ["S2", "S2 (300 K + 423 K)", "var(--s2)"]];
  function initDecomp() {
    let lv = "nominal", rho = "0", model = "gp";
    const ctl = $("decomp-ctl");
    seg(ctl, t("Noise", "잡음"), NOISE, lv, (v) => { lv = v; draw(); });
    seg(ctl, t("Noise correlation ρ", "잡음 상관 ρ"), RHOS, rho, (v) => { rho = v; draw(); });
    seg(ctl, t("Model", "모델"), MODELS, model, (v) => { model = v; draw(); });
    const wf = new Waterfall("decomp-chart", { steps: [], y: { label: MAE }, legend: false, aria: t("Split of the 423 K gain", "423 K 이득 나누기"), height: (w) => clamp(250, 330, w * 0.5) });
    function draw() {
      const key = `${lv}|${rho}|${model}`, b = C.rq1.bars[key], c = C.rq1.contrasts[key];
      const m = (S) => b[S].mean[3];
      const s1 = m("S1"), s12 = m("S1x2"), s2 = m("S2"), tot = s2 - s1;
      const share = (d) => (tot < 0 ? d / tot : null);
      wf.set({ steps: [
        { kind: "bar", lines: ["S1", "300 K ×1"], short: ["S1"], v: s1, color: "var(--s1)" },
        { kind: "delta", lines: t(["Noise", "averaging"], ["잡음 평균", "효과"]), short: t(["Noise", "avg."], ["잡음", "평균"]), from: s1, to: s12,
          color: "var(--s2)", dash: true, share: share(s12 - s1), ci: [c["S1x2-S1"].mean.lo, c["S1x2-S1"].mean.hi] },
        { kind: "bar", lines: ["S1×2", "300 K ×2"], short: ["S1×2"], v: s12, color: "var(--s1x2)" },
        { kind: "delta", lines: t(["423 K-specific", "gain"], ["423 K", "고유 이득"]), short: t(["423 K", "specific"], ["423 K", "고유"]), from: s12, to: s2,
          color: "var(--gain)", ink: "var(--gain-ink)", share: share(s2 - s12), ci: [c["S2-S1x2"].mean.lo, c["S2-S1x2"].mean.hi] },
        { kind: "bar", lines: ["S2", "300 K + 423 K"], short: ["S2"], v: s2, color: "var(--s2)" }] });
      const ci = (r) => `${sgn(r.delta, 3)} [${fx(r.lo, 3)}, ${fx(r.hi, 3)}]`;
      const sh = (d) => (share(d) == null ? "" : ` (${Math.round(share(d) * 100)} %)`);
      const line = $("decomp-line");
      line.textContent = "";
      line.append(h("b", { text: "S1 → S2 " }), ci(c["S2-S1"].mean), " · ",
        h("b", { text: t("repeat 300 K ", "300 K 반복 ") }), ci(c["S1x2-S1"].mean) + sh(s12 - s1), " · ",
        h("b", { text: t("423 K-specific ", "423 K 고유 ") }), ci(c["S2-S1x2"].mean) + sh(s2 - s12));
    }
    draw();

    const dr = C.rq1.draws;
    new LineChart("draws-chart", { series: SETS.map(([S, lab, col]) => ({ key: S, label: lab, color: col, line: false, markers: true, r: 5, legendShape: "circle",
      pts: dr.map((d) => [d.k, d[S]]) })),
      x: { domain: [-0.5, 4.5], ticks: [0, 1, 2, 3, 4], fmt: (v) => (v === 0 ? t("0 (paper)", "0 (논문)") : String(v)), label: t("Noise realisation", "잡음 실현"),
        tip: (v) => t(`realisation ${v}`, `잡음 실현 ${v}`) },
      y: { domain: [0.06, 0.12], ticks: [0.06, 0.07, 0.08, 0.09, 0.1, 0.11, 0.12], label: MAE, tip: (v) => fx(v, 3) }, tipTol: 0.4,
      aria: t("Five noise realisations", "잡음 실현 5회"), height: (w) => clamp(200, 260, w * 0.42) });
    tableToggle("fig-draws", () => ({ cols: [t("Realisation", "잡음 실현"), "S1", "S1×2", "S2", t("share of repeat", "반복 측정 몫")],
      rows: dr.map((d) => [d.k, fx(d.S1, 4), fx(d.S1x2, 4), fx(d.S2, 4), `${Math.round(((d.S1x2 - d.S1) / (d.S2 - d.S1)) * 100)} %`]) }));
  }

  // =========================================================================================== III-1. per-device estimates, equal budget
  function initEstimate() {
    const ctl = $("one-ctl"), body = $("one-body"), meta = $("one-meta");
    let level = "nominal", draw_ = 0, E = null;
    const ids = C.design.points.test.id;
    let cur = shared.dev.set === "test" ? shared.dev.id : ids[0];
    const sel = h("select", { class: "sel", "aria-label": t("Test device", "시험 소자") });
    for (const id of ids) sel.append(h("option", { value: id, text: id }));
    sel.addEventListener("change", () => { cur = sel.value; render(); });
    const step = (d) => { const i = ids.indexOf(cur); cur = ids[(i + d + ids.length) % ids.length]; render(); };
    ctl.append(h("span", {}, h("span", { class: "ctl-label" }, t("Test device ", "시험 소자 ")), sel),
      h("button", { type: "button", class: "btn small", onclick: () => step(-1) }, t("Previous", "이전")),
      h("button", { type: "button", class: "btn small", onclick: () => step(1) }, t("Next", "다음")));
    seg(ctl, t("Noise", "잡음"), NOISE, level, (v) => { level = v; render(); });
    const drawSeg = seg(ctl, t("Noise realisation", "잡음 실현"), [[0, t("paper", "논문")], [1, "1"], [2, "2"], [3, "3"], [4, "4"]], draw_, (v) => { draw_ = +v; render(); });
    ctl.append(h("button", { type: "button", class: "btn small", onclick: () => { draw_ = (draw_ % 4) + 1; drawSeg.setValue(draw_); render(); } }, t("Draw the noise again", "잡음 다시 뽑기")));
    shared.listeners.push((from) => { if (shared.dev.set === "test" && from !== "est") { cur = shared.dev.id; render(); } });
    function render() {
      sel.value = cur;
      const u = designU[cur];
      meta.textContent = "";
      meta.append(h("span", {}, h("b", { text: cur })), h("span", { rich: t(`nuisance s_{μ} = ${fx(physVal("mu_channel_scale", u[3]), 2)}`, `교란 변수 s_{μ} = ${fx(physVal("mu_channel_scale", u[3]), 2)}`) }));
      if (!E) return;
      const i = E.ids.indexOf(cur), truth = E.truth[i];
      body.textContent = "";
      const strips = h("div", { class: "strips" });
      const errs = {};
      for (const [S] of SETS) errs[S] = E.est[`${level}|${draw_}|${S}`][i].map((v, k) => Math.abs(v - truth[k]));
      TGT.forEach((v, k) => {
        const st = h("div", { class: "strip" });
        st.append(h("h4", {}, h("span", { rich: `${NAME[v]} ${SYM[v]}${UNIT[v] ? " (" + UNIT[v] + ")" : ""}`, style: "color:var(--ink);font-weight:600;font-size:14px" }),
          h("span", { rich: t(`true ${physFmt(v, physVal(v, truth[k]))}`, `실제 ${physFmt(v, physVal(v, truth[k]))}`) })));
        const host = h("div");
        st.append(host);
        strips.append(st);
        const pts = SETS.map(([S, lab, col], j) => ({ S, lab, col, x: physVal(v, E.est[`${level}|${draw_}|${S}`][i][k]), row: j }));
        stripChart(host, v, physVal(v, truth[k]), pts);
      });
      body.append(strips);
      const tb = h("table", { class: "est-table" });
      tb.append(h("thead", {}, h("tr", {}, h("th", { rich: "MAE_{norm}" }), TGT.map((v) => h("th", { rich: SYM[v] })), h("th", { text: t("mean", "평균") }))));
      tb.append(h("tbody", {}, SETS.map(([S, lab, col]) => h("tr", {}, h("td", {}, h("span", { class: "key", style: `border-top-color:${col}` }), lab.replace(/ \(.*\)$/, "")),
        errs[S].map((e) => h("td", { text: fx(e, 3) })), h("td", { text: fx((errs[S][0] + errs[S][1] + errs[S][2]) / 3, 3) })))));
      body.append(tb);
      if (draw_) body.append(h("p", { class: "note", text: t(`Noise realisation ${draw_}: new noise added to the training and test features, then estimated again.`, `잡음 실현 ${draw_}: 학습·시험 특징에 새 잡음을 더해 다시 추정한 값.`) }));
    }
    function stripChart(host, v, truthX, pts) {
      const w = Math.max(260, host.clientWidth || body.clientWidth || 600), H = 80;
      const svg = sv("svg", { viewBox: `0 0 ${w} ${H}`, width: w, height: H, role: "img", "aria-label": t(`${NAME[v]} estimates`, `${NAME[v]} 추정값`) });
      host.append(svg);
      const [a, b] = physDomain(v), m = { l: 10, r: 14 };
      const x = lin(a, b, m.l, w - m.r);
      const g = sv("g", { class: "chart" }, svg);
      const tk = ticks(a, b, 4);
      for (const tv of tk) {
        sv("line", { x1: x(tv), x2: x(tv), y1: 6, y2: H - 22, stroke: "var(--grid)" }, g);
        sv("line", { x1: x(tv), x2: x(tv), y1: H - 22, y2: H - 17, stroke: "var(--frame)" }, g);
        sv("text", { x: x(tv), y: H - 3, "text-anchor": "middle", fill: "var(--ink-2)", "font-size": 12.5 }, g).textContent = fx(tv, decimalsFor(tk));
      }
      sv("line", { x1: m.l, x2: w - m.r, y1: H - 22, y2: H - 22, stroke: "var(--frame)" }, g);
      sv("line", { x1: x(truthX), x2: x(truthX), y1: 2, y2: H - 22, stroke: "var(--ink)", "stroke-width": 2 }, g);
      pts.forEach((p) => {
        const cy = 14 + p.row * 14;
        sv("line", { x1: x(truthX), x2: x(p.x), y1: cy, y2: cy, stroke: p.col, "stroke-width": 1.5 }, g);
        sv("circle", { cx: x(Math.max(a, Math.min(b, p.x))), cy, r: 5, fill: p.col, stroke: "var(--surface)", "stroke-width": 1 }, g);
      });
    }
    if (ro) new ResizeObserver(() => { if (E) render(); }).observe(body);
    whenNear($("fig-one"), () => need("estimates").then((d) => { E = d; render(); }).catch(() => { body.textContent = t("The estimates could not be loaded.", "추정 결과를 불러오지 못했습니다."); }));
    const leg = h("ul", { class: "legend" }, SETS.map(([, lab, col]) => h("li", {}, h("span", { class: "static" }, h("span", { class: "sw circle", style: `background:${col}` }), lab))),
      h("li", {}, h("span", { class: "static" }, h("span", { class: "sw", style: "border-top-color:var(--ink);width:2px;height:12px;border-top:0;border-left:2px solid var(--ink)" }), t("true value", "실제 값"))));
    ctl.after(leg);
    render();

    // equal budget
    const B = C.rq1.budget, budgets = Object.keys(B).map(Number).sort((a, b) => a - b);
    new LineChart("budget-chart", { series: SETS.map(([S, lab, col]) => ({ key: S, label: lab, color: col, markers: true, err: true,
      pts: budgets.map((b) => [b, B[b][S].mean, B[b][S].mean - B[b][S].sd, B[b][S].mean + B[b][S].sd]) })),
      x: { domain: [90, 510], ticks: budgets, label: t("DEVSIM runs used for training", "학습에 쓴 DEVSIM 실행 수"), fmt: (v) => String(v), tip: (v) => t(`${v} DEVSIM runs`, `DEVSIM ${v}회`) },
      y: { label: MAE, tip: (v) => fx(v, 3) }, tipTol: 30, aria: t("Equal number of runs", "같은 실행 수에서 비교"), height: (w) => clamp(220, 300, w * 0.5) });
    tableToggle("fig-budget", () => ({ cols: [t("DEVSIM runs", "DEVSIM 실행 수"), ...SETS.map(([, l]) => l)],
      rows: budgets.map((b) => [b, ...SETS.map(([S]) => `${fx(B[b][S].mean, 3)} ± ${fx(B[b][S].sd, 3)} (${t(`${B[b][S].points} devices`, `${B[b][S].points}개 소자`)})`)]) }));
  }

  // =========================================================================================== III-2. poster Fig. 5
  function initBars() {
    let lv = "nominal", model = "gp", rho = "0";
    const bc = $("bars-ctl");
    seg(bc, t("Noise", "잡음"), NOISE, lv, (v) => { lv = v; drawB(); });
    seg(bc, t("Model", "모델"), MODELS, model, (v) => { model = v; drawB(); });
    seg(bc, t("Noise correlation ρ", "잡음 상관 ρ"), RHOS, rho, (v) => { rho = v; drawB(); });
    const bars = new Bars("bars-chart", { cats: [], series: [], y: {}, aria: t("Error per parameter", "변수별 오차"), height: (w) => clamp(240, 330, w * 0.5) });
    const cats = ["W_{JFET}", "N_{pw}", "Q_{it,eff}", t("mean", "평균")];
    const keys = ["wjfet_scale", "npwell_scale", "qit_eff_cm2", "mean"];
    function drawB() {
      const key = `${lv}|${rho}|${model}`, rec = C.rq1.bars[key], con = C.rq1.contrasts[key]["S2-S1x2"];
      const notes = keys.map((k) => {
        const r = con[k];
        return r.hi < 0 || r.lo > 0 ? { text: pct(r.ratio - 1, 0).replace(" %", "%"), color: "var(--gain-ink)" } : { text: "n.s.", color: "var(--muted)" };
      });
      bars.set({ cats, notes, series: SETS.map(([S, lab, col]) => ({ key: S, label: lab, color: col, vals: rec[S].mean, lo: rec[S].lo, hi: rec[S].hi })),
        y: { label: MAE }, refs: [{ y: C.rq1.no_information, label: t("guessing the midpoint 0.25", "무정보 추정 0.25") }] });
      btab.refresh();
    }
    const btab = tableToggle("fig-bars", () => {
      const key = `${lv}|${rho}|${model}`, rec = C.rq1.bars[key], con = C.rq1.contrasts[key]["S2-S1x2"];
      return { cols: [t("Input", "특징 세트"), ...cats.map((c) => c + t(" [95 % interval]", " [95 % 구간]"))],
        rows: SETS.map(([S, lab]) => [lab, ...rec[S].mean.map((m, i) => `${fx(m, 3)} [${fx(rec[S].lo[i], 3)}, ${fx(rec[S].hi[i], 3)}]`)])
          .concat([[t("S2 − S1×2 (paired)", "S2 − S1×2 (짝지은 차이)"), ...keys.map((k) => `${sgn(con[k].delta, 3)} [${fx(con[k].lo, 3)}, ${fx(con[k].hi, 3)}]`)]]) };
    });
    drawB();
  }

  // =========================================================================================== III-3. poster Fig. 6a, 6b and series resistance
  function initRho() {
    let lv = "nominal", model = "gp";
    const ctl = $("rho-ctl");
    seg(ctl, t("Noise", "잡음"), NOISE, lv, (v) => { lv = v; draw(); });
    seg(ctl, t("Model", "모델"), MODELS, model, (v) => { model = v; draw(); });
    const S4 = [...SETS, ["S3", t("S3 (S2 + ΔT)", "S3 (S2 + ΔT 특징)"), "var(--s3)"]];
    const DX = { S1: -0.016, S1x2: -0.005, S2: 0.005, S3: 0.016 };
    const chart = new LineChart("rho-chart", { series: [], x: {}, y: {}, mr: 54, endLabels: true, endLabelsAtFrame: true, tipTol: 0.05, aria: t("Error vs. noise correlation", "잡음 상관에 따른 오차"),
      height: (w) => clamp(240, 330, w * 0.55) });
    function draw() {
      const series = S4.map(([S, lab, col]) => {
        const pts = ["0", "0.5", "0.9"].map((r) => { const b = C.rq1.bars[`${lv}|${r}|${model}`][S]; return [+r + DX[S], b.mean[3], b.lo[3], b.hi[3]]; });
        return { key: S, label: lab, color: col, pts, dash: S === "S1" ? "6 4" : S === "S3" ? "3 3" : null, markers: true, err: true, r: 4.2,
          shape: S === "S1" ? "ring" : S === "S2" ? "diamond" : null, hollow: false, endLabel: fx(pts[2][1], 3) };
      });
      chart.set({ series,
        x: { domain: [-0.08, 0.98], ticks: [0, 0.5, 0.9], fmt: (v) => (v === 0 ? t("0 (independent)", "0 (독립)") : v === 0.9 ? t("0.9 (common)", "0.9 (공통)") : "0.5"),
          label: t("Noise correlation ρ", "잡음 상관 ρ"), tip: (v) => `ρ = ${Math.round(v * 10) / 10}` },
        y: { label: MAE, tip: (v) => fx(v, 3) } });
      tab.refresh();
    }
    const tab = tableToggle("fig-rho", () => ({ cols: ["ρ", ...S4.map(([, l]) => l)], rows: ["0", "0.5", "0.9"].map((r) => [r, ...S4.map(([S]) => {
      const b = C.rq1.bars[`${lv}|${r}|${model}`][S]; return `${fx(b.mean[3], 3)} [${fx(b.lo[3], 3)}, ${fx(b.hi[3], 3)}]`;
    })]) }));
    draw();
  }

  function initPhys() {
    const SC = C.rq1.scenarios;
    const rows = [["base", t("Baseline (γ = +1, r = 0)", "기준 (γ = +1, r = 0)")], ["gamma0", "γ = 0"], ["gamma_m1", "γ = −1"], ["qitT10", "r = 0.1"], ["qitT30", "r = 0.3"]].map(([key, label]) => ({ key, label }));
    const ser = [["matched", t("Matched", "같은 물리로 학습"), "var(--s2)", "circle", "left", "var(--s2)"],
      ["nominal", t("Mismatched (trained on the base physics)", "불일치 (기준 물리로 학습)"), "#d55e00", "x", "right", "#c04f00"],
      ["mixed", t("Mixture of the five (post hoc)", "다섯 가정 혼합 학습 (사후 분석)"), "#009e73", "diamond", null, null]];
    const val = (r, k) => (SC[r][k] != null ? SC[r][k] : null);
    new DotRows("phys-chart", { rows, series: ser.map(([k, label, color, shape, labels, ink]) => ({ key: k, label, color, shape, labels, ink,
      vals: Object.fromEntries(rows.map((r) => [r.key, val(r.key, k)])) })),
    x: { min: 0.02, max: 1.2, ticks: [0.02, 0.05, 0.1, 0.2, 0.5, 1], label: t("S2 mean MAE_{norm} (log)", "S2의 평균 MAE_{norm} (로그 눈금)") },
    refs: [{ x: C.rq1.reference.S1x2, label: "S1×2", anchor: "end", color: "var(--s1x2)" }, { x: C.rq1.reference.S1, label: "S1", color: "#7f7f7f" },
      { x: 0.25, label: t("no info 0.25", "무정보 0.25"), dash: "2 3" }],
    aria: t("S2 error under each 423 K physics", "423 K 물리 가정별 S2 오차") });
    tableToggle("fig-phys", () => ({ cols: [t("423 K test data", "423 K 시험 데이터"), ...ser.map(([, l]) => l)], rows: rows.map((r) => [r.label, ...ser.map(([k]) => fx(val(r.key, k), 3))]) }));

    const SR = C.rq1.series;
    new Bars("series-chart", { cats: ["S1", "S1×2", "S2"], y: { label: MAE },
      series: [{ key: "plain", label: t("as simulated", "계산한 그대로"), color: "#a8b1ba", vals: ["S1", "S1x2", "S2"].map((s) => SR.plain[s]) },
        { key: "r", label: t("series resistance added", "직렬저항 추가"), color: "#d55e00", vals: ["S1", "S1x2", "S2"].map((s) => SR.series_r[s]) }],
      refs: [{ y: C.rq1.no_information, label: t("no info 0.25", "무정보 0.25") }],
      aria: t("Error with an untrained series resistance", "직렬저항이 더해진 시험 소자의 오차"), height: (w) => clamp(220, 300, w * 0.5) });
    tableToggle("fig-series", () => ({ cols: [t("Input", "특징 세트"), t("as simulated", "계산한 그대로"), t("series resistance added", "직렬저항 추가")],
      rows: ["S1", "S1x2", "S2"].map((s) => [s.replace("x2", "×2"), fx(SR.plain[s], 3), fx(SR.series_r[s], 3)]) }));
  }

  // =========================================================================================== III-4. selection (RQ2, RQ3)
  const POL = { random: [t("random", "무작위"), "var(--p-rand)", "2 4"], sobol: [t("Sobol order", "Sobol 순서"), "var(--p-sobol)"], uncertainty: [t("uncertainty", "불확실도"), "var(--p-unc)"],
    top20_random: [t("D: random 10 of the top 20", "D: 상위 20개 중 무작위"), "var(--p-d)"], A0: [t("LLM A0 (first run)", "LLM A0 (첫 실행)"), "var(--p-a0)", "6 3"],
    A: [t("LLM A (original format)", "LLM A (원래 형식)"), "var(--p-a)"], B: [t("LLM B (anonymized)", "LLM B (익명화)"), "var(--p-b)"], C: [t("LLM C (perturbed input)", "LLM C (입력 교란)"), "var(--p-c)"] };
  function initSelect() {
    const SEL = C.selection;
    let level = "nominal", seeds = "none";
    const ctl = $("curves-ctl");
    const hidden = new Set(["top20_random", "B", "C"]);
    seg(ctl, t("Noise", "잡음"), [["none", t("none", "없음")], ["nominal", t("nominal", "기준")], ["high", "2×"]], level, (v) => { level = v; draw(); });
    select(ctl, t("Per-seed curves", "시드별 곡선"), [["none", t("off", "보지 않음")], ...Object.entries(POL).map(([k, v]) => [k, v[0]])], seeds, (v) => { seeds = v; draw(); });
    const chart = new LineChart("curves-chart", { series: [], x: {}, y: {}, hidden: [...hidden], aria: t("Learning curves", "학습 곡선"), height: (w) => clamp(240, 380, w * 0.6) });
    const curvesFor = (k) => (level === "nominal" || !SEL.levels[level][k] ? (level === "nominal" ? SEL.curves[k] : null) : SEL.levels[level][k]);
    function draw() {
      const series = [];
      for (const [k, [label, color, dash]] of Object.entries(POL)) {
        const c = curvesFor(k);
        if (!c) continue;
        series.push({ key: k, label, color, dash, markers: true, r: 3.5, pts: c.n.map((n, i) => [n, c.mean[i]]) });
        if (seeds === k) c.seeds.forEach((row, j) => series.push({ key: k + "s" + j, label: t(`${label}, seed ${j}`, `${label}, 시드 ${j}`), color, thin: true, tip: false, legend: false, pts: c.n.map((n, i) => [n, row[i]]) }));
      }
      const rf = curvesFor("random"), last = rf.mean[rf.mean.length - 1];
      chart.set({ series, refs: [{ y: last, label: t(`random at 120 devices: ${fx(last, 4)}`, `무작위 120개 시점: ${fx(last, 4)}`), dash: "4 3", at: "left" }],
        x: { domain: [57, 123], ticks: [60, 70, 80, 90, 100, 110, 120], label: t("Devices chosen (each 300 K + 423 K)", "고른 소자 수 (각 300 K + 423 K)"), fmt: (v) => String(v), tip: (v) => t(`${v} devices`, `소자 ${v}개`) },
        y: { label: t("Test MAE_{norm}", "시험 소자 MAE_{norm}"), tip: (v) => fx(v, 4) }, tipTol: 3, onToggle: () => tab.refresh() });
      tab.refresh();
    }
    const tab = tableToggle("fig-curves", () => {
      const ks = Object.keys(POL).filter((k) => curvesFor(k));
      const n = curvesFor("random").n;
      return { cols: [t("Devices", "소자 수"), ...ks.map((k) => POL[k][0] + t(" (mean ± SD)", " (평균 ± 표준편차)"))], rows: n.map((nn, i) => [nn, ...ks.map((k) => `${fx(curvesFor(k).mean[i], 4)} ± ${fx(curvesFor(k).sd[i], 4)}`)]) };
    });
    draw();

    // forest (paper Table 3)
    const U = t("uncertainty", "불확실도");
    const lab = { "U-random": `${U} − ${t("random", "무작위")}`, "sobol-random": `Sobol − ${t("random", "무작위")}`, "U-sobol": `${U} − Sobol`, "D-U": `D − ${U}`,
      "A0-U": `LLM A0 − ${U}`, "A-U": `LLM A − ${U}`, "B-U": `LLM B − ${U}`, "C-U": `LLM C − ${U}` };
    new Forest("diff-chart", { rows: SEL.diffs.map((d) => ({ label: lab[d.key], delta: d.delta * 1e3, lo: d.lo * 1e3, hi: d.hi * 1e3, wins: d.wins, n: d.n, color: "var(--ink)" })),
      band: SEL.sesoi * 1e3, xlabel: t("Final error difference (×10^{-3}), 95 % interval, seeds where the first is lower", "최종 오차 차이 (×10^{-3}), 95 % 구간, 앞 정책이 낮은 시드 수"),
      xlabelShort: t("Final error difference (×10^{-3})", "최종 오차 차이 (×10^{-3})"), aria: t("Final-round differences", "마지막 라운드 오차 차이") });
    tableToggle("fig-diff", () => ({ cols: [t("Comparison", "비교"), t("Difference (×10^{-3})", "차이 (×10^{-3})"), t("95 % interval", "95 % 구간"), t("Seeds where the first is lower", "앞 정책이 낮은 시드")],
      rows: SEL.diffs.map((d) => [lab[d.key], sgn(d.delta * 1e3, 2), `[${sgn(d.lo * 1e3, 2)}, ${sgn(d.hi * 1e3, 2)}]`, `${d.wins}/${d.n}`]) }));

    // poster Fig. 8: overlap with the true and the displayed top 10
    const OV = SEL.overlap;
    const rowsO = [["A0", t("A0 first run", "A0 첫 실행")], ["A", t("A original format", "A 원래 형식")], ["B", t("B anonymized", "B 익명화")], ["C", t("C perturbed input", "C 입력 교란")]];
    new DotPairs("overlap-chart", { rows: rowsO.map(([k, label]) => ({ key: k, label, a: OV[k].true, b: OV[k].shown,
      note: k === "C" ? t("follows the falsely displayed top 10", "허위로 표시된 상위 10을 따라감") : null,
      tip: [{ color: "var(--s2)", value: fx(OV[k].true, 3), label: t("true top 10", "실제 상위 10") }, { color: "var(--llm)", value: fx(OV[k].shown, 3), label: t("displayed top 10", "보인 상위 10") },
        { value: t(`${OV[k].n} of ${OV[k].calls}`, `${OV[k].calls}회 중 ${OV[k].n}회`), label: t("calls that passed the check", "검증 통과 호출") }] })),
    x: { min: 0.45, max: 0.70, label: t("Overlap of the 10 LLM picks with the top-10 set", "LLM이 고른 10개와 상위 10개 집합의 겹침") },
    ref: SEL.random_overlap, refLabel: t(`random ${fx(SEL.random_overlap, 2)}`, `무작위 ${fx(SEL.random_overlap, 2)}`),
    colorA: "var(--s2)", colorB: "var(--llm)", inkA: "var(--s2)", inkB: "var(--llm-ink)", arrow: "#d55e00",
    legendItems: [{ label: t("true uncertainty top 10", "실제 불확실도 상위 10"), color: "var(--s2)", shape: "circle", toggle: false },
      { label: t("top 10 displayed to the LLM", "LLM에게 보인 상위 10"), color: "var(--llm)", shape: "ring", toggle: false }],
    aria: t("Overlap of the LLM picks", "LLM 선택의 겹침") });
    tableToggle("fig-overlap", () => ({ cols: [t("Condition", "조건"), t("true top 10", "실제 상위 10"), t("displayed top 10", "보인 상위 10"), t("calls (passed / all)", "호출 (통과 / 전체)")],
      rows: rowsO.map(([k, l]) => [l, fx(OV[k].true, 3), fx(OV[k].shown, 3), `${OV[k].n} / ${OV[k].calls}`]) }));

    initLLM();
  }

  function initLLM() {
    const ctl = $("llm-ctl"), body = $("llm-body");
    let L = null, cond = "A", seed = 0, rnd = 0, showTrue = false;
    seg(ctl, t("Condition", "조건"), [["A", t("A original", "A 원래 정보")], ["B", t("B anonymized", "B 이름 지움")], ["C", t("C perturbed", "C 정보 섞음")]], cond, (v) => { cond = v; render(); });
    select(ctl, t("Seed", "시드"), Array.from({ length: 10 }, (_, i) => [i, String(i)]), seed, (v) => { seed = +v; render(); });
    const rlab = h("b", { class: "nums" });
    ctl.append(h("span", { class: "stepper" }, h("span", { class: "ctl-label" }, t("Round", "라운드")),
      h("button", { type: "button", class: "btn small", onclick: () => { rnd = Math.max(0, rnd - 1); render(); }, "aria-label": t("previous round", "이전 라운드") }, t("Previous", "이전")), rlab,
      h("button", { type: "button", class: "btn small", onclick: () => { rnd = Math.min(5, rnd + 1); render(); }, "aria-label": t("next round", "다음 라운드") }, t("Next", "다음"))));
    const trueBox = h("label", { class: "ctl-label", style: "display:none;gap:6px;align-items:center" }, h("input", { type: "checkbox", onchange: (e) => { showTrue = e.target.checked; render(); } }),
      t("C: show the true values before shuffling", "C: 섞기 전 실제 값으로 보기"));
    ctl.append(trueBox);
    let mapChart = null, valChart = null, info = null, valHead = null;
    const rankOf = (list, key) => new Map([...list].sort((a, b) => key(b) - key(a)).map((c, j) => [c.id, j + 1]));
    function current() { return L ? L.conditions[cond].find((q) => q.seed === seed && q.round === rnd) : null; }
    function render() {
      rlab.textContent = `${rnd + 1} / 6`;
      trueBox.style.display = cond === "C" ? "inline-flex" : "none";
      const r = current();
      if (!r) return;
      const useTrue = cond === "C" && showTrue && r.true;
      const sel = new Set(r.selected || []);
      const train = [...L.init[seed]];
      for (const q of L.conditions[cond]) if (q.seed === seed && q.round < rnd && q.selected) train.push(...q.selected);
      const trainSet = new Set(train), candSet = new Set(r.cands.map((c) => c.id));
      const UU = L.pool_u;
      const P = (id, k) => physVal(VARS[k], UU[id][k]);
      const base = Object.keys(UU).filter((id) => !trainSet.has(id) && !candSet.has(id));
      const shown = rankOf(r.cands, (c) => c.unc);
      const truth = r.true ? rankOf(r.cands, (c) => r.true[c.id][0]) : shown;
      const miss = r.missing ? t(` (${r.missing} chosen by the fallback rule are not logged)`, ` (대체 규칙으로 고른 ${r.missing}개는 기록 없음)`) : "";
      const groups = [
        { key: "pool", label: t("rest of the pool", "나머지 후보 풀"), color: "#d0d7de", r: 2.4, toggle: false, pts: base.map((id) => ({ id, x: P(id, 0), y: P(id, 1) })) },
        { key: "train", label: t(`already chosen: ${train.length}`, `이미 고른 소자 ${train.length}개`) + miss, color: "var(--axis)", r: 3, toggle: false,
          pts: train.map((id) => ({ id, x: P(id, 0), y: P(id, 1) })) },
        { key: "cand", label: t("candidates shown to the LLM", "LLM에게 보인 후보"), color: "var(--ink)", hollow: true, r: 4.5, toggle: false, pts: r.cands.filter((c) => !sel.has(c.id)).map((c) => ({ id: c.id, x: P(c.id, 0), y: P(c.id, 1) })) }];
      if (sel.size) groups.push({ key: "sel", label: t("the 10 picked by the LLM", "LLM이 고른 10개"), color: "var(--p-a)", r: 5, toggle: false, pts: r.cands.filter((c) => sel.has(c.id)).map((c) => ({ id: c.id, x: P(c.id, 0), y: P(c.id, 1) })) });
      mapChart.set({ groups, x: { label: axisLabel("wjfet_scale"), domain: physDomain("wjfet_scale") }, y: { label: axisLabel("npwell_scale"), domain: physDomain("npwell_scale") },
        tip: (p, g) => ({ head: `${p.id}, ${g.label.replace(/ \(.*\)$/, "")}`, rows: [0, 1, 2, 3].map((k) => ({ value: physFmt(VARS[k], P(p.id, k)), label: SYM[VARS[k]] + (UNIT[VARS[k]] ? " " + UNIT[VARS[k]] : "") })) }) });
      const rank = useTrue ? truth : shown;
      const pts = r.cands.map((c) => (useTrue ? { id: c.id, x: r.true[c.id][0], y: r.true[c.id][1] } : { id: c.id, x: c.unc, y: c.dist }));
      const xs = pts.map((p) => p.x).sort((a, b) => b - a);
      valHead.textContent = useTrue ? t("True values before shuffling", "섞기 전 실제 값") : t("Candidate information shown to the LLM", "LLM에게 보인 후보 정보");
      const vg = [{ key: "cand", label: t("not picked", "선택 안 됨"), color: "var(--ink)", hollow: true, r: 5, toggle: false, pts: pts.filter((p) => !sel.has(p.id)) }];
      if (sel.size) vg.push({ key: "sel", label: t("the 10 picked by the LLM", "LLM이 고른 10개"), color: "var(--p-a)", r: 5.5, toggle: false, pts: pts.filter((p) => sel.has(p.id)) });
      valChart.set({ groups: vg, x: { label: useTrue ? t("true predicted uncertainty", "실제 예측 불확실도") : t("predicted uncertainty", "예측 불확실도") },
        y: { label: useTrue ? t("true distance to the training set", "실제 학습 소자까지 최소 거리") : t("distance to the training set", "학습 소자까지 최소 거리") },
        vlines: [{ x: (xs[9] + xs[10]) / 2, label: t("← top 10 by uncertainty", "← 불확실도 상위 10개") }],
        tip: (p) => ({ head: t(`${p.id}, uncertainty rank ${rank.get(p.id)}`, `${p.id}, 불확실도 ${rank.get(p.id)}위`), rows: [{ value: fx(p.x, 4), label: t("uncertainty", "불확실도") }, { value: fx(p.y, 4), label: t("distance", "거리") }] }) });
      const overlap = (rk) => [...sel].filter((id) => rk.get(id) <= 10).length;
      info.textContent = "";
      const C_ = cond === "C";
      const kv = h("dl", { class: "kv" },
        h("dt", { text: t("Training devices", "학습 소자") }), h("dd", { text: t(`${r.n_train}`, `${r.n_train}개`) }),
        h("dt", { text: C_ ? t("Cross-validation error shown to the LLM", "LLM에게 보인 교차검증 오차") : t("Cross-validation error", "교차검증 오차") }), h("dd", { rich: TGT.map((v) => `${SYM[v]} ${fx(r.cv[v], 3)}`).join(",  ") }),
        h("dt", { text: t("Worst parameter told to the LLM", "LLM에게 알린 최악 변수") }), h("dd", { rich: SYM[r.worst] + (C_ && r.true_worst ? t(` (true: ${SYM[r.true_worst]})`, ` (실제 ${SYM[r.true_worst]})`) : "") }));
      if (sel.size) kv.append(h("dt", { text: t("Overlap with the top 10 by uncertainty", "불확실도 상위 10개와 겹침") }),
        h("dd", { text: C_ && r.true ? t(`shown values ${overlap(shown)}/10, true values ${overlap(truth)}/10`, `보인 값 기준 ${overlap(shown)}/10, 실제 값 기준 ${overlap(truth)}/10`) : `${overlap(shown)}/10` }));
      kv.append(h("dt", { text: t("Response check", "응답 검증") }), h("dd", { text: r.status === "accepted" ? t("passed", "통과") : t(`rejected (${r.reject || "format"}); the uncertainty policy picked the 10`, `거절(${r.reject || "형식 오류"}), 대체 규칙(불확실도 정책)으로 10개 선택`) }),
        h("dt", { text: t("Tokens, latency", "토큰, 지연") }), h("dd", { text: t(`in ${r.tin.toLocaleString(locale)}, out ${r.tout.toLocaleString(locale)}, ${fx(r.latency, 1)} s`, `입력 ${r.tin.toLocaleString(locale)}, 출력 ${r.tout.toLocaleString(locale)}, ${fx(r.latency, 1)} s`) }));
      info.append(kv);
      if (r.reasons && r.reasons.length) info.append(h("p", { class: "sub-head", text: t("Reason codes returned by the LLM", "LLM이 고른 사유 코드") }), h("ul", { class: "chips" }, r.reasons.map((c) => h("li", { text: c }))));
      if (r.rationale) info.append(h("p", { class: "sub-head", text: t("Rationale in the LLM response (verbatim)", "LLM 응답의 근거 문장(원문)") }), h("blockquote", { class: "rationale", lang: "en", text: r.rationale }));
      tab.refresh();
    }
    const tab = tableToggle("fig-llm", () => {
      const r = current();
      if (!r) return { cols: [], rows: [] };
      const sel = new Set(r.selected || []);
      const shown = rankOf(r.cands, (c) => c.unc);
      const C_ = cond === "C" && r.true;
      return { cols: [t("Uncertainty rank", "불확실도 순위"), t("Candidate", "후보"), t("Uncertainty", "불확실도"), t("Distance", "거리"), t("Picked by the LLM", "LLM 선택"),
        ...(C_ ? [t("True uncertainty", "실제 불확실도"), t("True distance", "실제 거리")] : [])],
      rows: [...r.cands].sort((a, b) => shown.get(a.id) - shown.get(b.id)).map((c) => [shown.get(c.id), c.id, fx(c.unc, 4), fx(c.dist, 4), sel.has(c.id) ? t("yes", "예") : "",
        ...(C_ ? [fx(r.true[c.id][0], 4), fx(r.true[c.id][1], 4)] : [])]) };
    });
    whenNear($("fig-llm"), () => need("llm").then((d) => {
      L = d;
      body.textContent = "";
      const grid = h("div", { class: "llm-grid" });
      const a = h("div"), b = h("div");
      valHead = h("p", { class: "sub-head", text: t("Candidate information shown to the LLM", "LLM에게 보인 후보 정보") });
      grid.append(h("div", {}, h("p", { class: "sub-head", text: t("Candidates in the process-parameter space", "공정 변수 공간에서 후보 위치") }), a), h("div", {}, valHead, b));
      info = h("div");
      const prompt = h("details", { class: "code" }, h("summary", {}, t("System prompt given to the LLM", "LLM에 준 시스템 프롬프트"), h("span", { class: "count", text: "src/sicsim/llm.py" })),
        h("div", { class: "code-list" }, h("pre", { class: "src prompt", lang: "en", text: d.system_prompt })));
      body.append(grid, info, prompt);
      mapChart = new Scatter(a, { groups: [], x: {}, y: {}, aria: t("Candidates in the parameter space", "공정 변수 공간의 후보"), height: (w) => clamp(230, 330, w * 0.8) });
      valChart = new Scatter(b, { groups: [], x: {}, y: {}, aria: t("Uncertainty and distance of the candidates", "후보의 불확실도와 거리"), height: (w) => clamp(230, 330, w * 0.8) });
      render();
    }).catch(() => { body.textContent = t("The LLM calls could not be loaded.", "LLM 호출 기록을 불러오지 못했습니다."); }));
    render();
  }

  // =========================================================================================== code panels, links, language
  const CODE_COUNT = { design: 2, data: 3, estimate: 4, select: 3 };
  function initCode() {
    for (const det of document.querySelectorAll("details.code[data-section]")) {
      const secs = det.dataset.section.split(/\s+/);
      const n = secs.reduce((a, s) => a + (CODE_COUNT[s] || 0), 0);
      det.querySelector("summary .count").textContent = t(`${n} functions`, `함수 ${n}개`);
      det.addEventListener("toggle", () => {
        if (!det.open || det.dataset.done) return;
        det.dataset.done = "1";
        const list = det.querySelector(".code-list");
        list.append(h("p", { class: "loading", text: t("Loading the code.", "코드를 불러오는 중입니다.") }));
        need("code").then((d) => {
          list.textContent = "";
          for (const it of d.items.filter((x) => secs.includes(x.section))) {
            const pre = h("pre", { class: "src" });
            const code = h("code");
            code.innerHTML = it.html;            // escaped source of this repository with token spans (scripts/make_site.py)
            pre.append(code);
            list.append(h("div", { class: "code-item" }, h("header", {}, h("b", { rich: KO ? it.label : it.label_en || it.label }),
              h("a", { href: it.url, target: "_blank", rel: "noopener" }, t(`${it.file}, lines ${it.start}–${it.end}`, `${it.file}, ${it.start}–${it.end}행`))), pre));
          }
        }).catch(() => { list.textContent = t("The code could not be loaded.", "코드를 불러오지 못했습니다."); });
      });
    }
  }
  function initLinks() {
    const map = { repo: REPO, codespaces: "https://codespaces.new/mseokq23/sic-mosfet-devsim?quickstart=1", numbers: ghUrl("paper/numbers.csv") };
    for (const a of document.querySelectorAll("[data-href]")) { a.href = map[a.dataset.href]; a.target = "_blank"; a.rel = "noopener"; }
    const st = $("stamp");
    const mk = h("a", { href: `${REPO}/blob/main/scripts/make_site.py`, target: "_blank", rel: "noopener" }, "scripts/make_site.py");
    const cm = h("a", { href: `${REPO}/tree/${COMMIT}`, target: "_blank", rel: "noopener" }, C.meta.short);
    if (KO) st.append("이 페이지의 데이터는 ", mk, "가 커밋 ", cm, `(${C.meta.date})의 결과 파일에서 만들었다.`);
    else st.append("The data on this page were built by ", mk, " from the result files at commit ", cm, ` (${C.meta.date}).`);
  }
  function initLang() {
    const toc = document.querySelector(".toc");
    if (toc) toc.setAttribute("aria-label", t("Contents", "목차"));
    const links = document.querySelectorAll(".lang-switch a[data-lang]");
    const sync = () => { for (const a of links) a.setAttribute("href", `?lang=${a.dataset.lang}${location.hash}`); };
    for (const a of links) if (a.dataset.lang === document.documentElement.lang) a.setAttribute("aria-current", "true");
    sync();
    window.addEventListener("hashchange", sync);
  }
  function init() {
    initLang();
    initLinks();
    figActions();
    const parts = [initLab, initSens, initDesign, initData, initMech, initDecomp, initEstimate, initBars, initRho, initPhys, initSelect, initCode];
    for (const f of parts) {
      try { f(); } catch (e) { console.error(f.name, e); }
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
