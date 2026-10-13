(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("graph-data").textContent);
  const $ = id => document.getElementById(id);
  const names = {T: "Title", A: "Abstract", C: "Conclusions"};
  const colors = {T: "var(--t)", A: "var(--a)", C: "var(--c)"};
  const ns = "http://www.w3.org/2000/svg";
  const articles = new Map(data.articles.map(a => [a.article_id, a]));
  const state = {article: null, kind: null, term: null, mode: "articles", sort: "rank", query: "", x: 0, y: 0, zoom: 1};
  const termArticle = new Map(data.articles.flatMap(a => a.terms.map(t => [t.term_id, a.article_id])));
  const indexes = new Map(data.articles.map(a => [a.article_id, {
    terms: new Map(a.terms.map(t => [t.term_id, t])),
    uses: new Map(a.uses.map(u => [u.use_id, u])),
    mentions: new Map(a.mentions.map(m => [m.mention_id, m])),
    contexts: new Map(a.contexts.map(c => [c.context_id, c]))
  }]));
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const svgEl = (tag, attrs = {}, text) => {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const action = (text, handler, cls) => {
    const b = el("button", text, cls); b.type = "button"; b.addEventListener("click", handler); return b;
  };
  const link = (text, href) => {
    const a = el("a", text); a.href = href; a.target = "_blank"; a.rel = "noopener"; return a;
  };
  const short = (value, n) => [...value].length > n ? [...value].slice(0, n - 1).join("") + "…" : value;
  const current = () => articles.get(state.article);
  const scope = () => current() ? [current()] : data.articles;
  const membership = term => state.mode === "TAC" ? term.groups : (term.memberships?.[state.mode] || []);
  const groupName = kind => state.mode === "TAC" ? names[kind] : data.taxonomy.categories[state.mode][kind];
  const groupColor = kind => state.mode === "TAC" ? colors[kind] : kind === "unclassified" ? "var(--muted)" : kind === "unresolved" ? "var(--c)" : "var(--accent)";
  function viewGroups() {
    if (state.mode === "articles") return [];
    const rows = scope();
    const keys = state.mode === "TAC" ? ["T", "A", "C"] : Object.keys(data.taxonomy.categories[state.mode]);
    return keys.map(kind => {
      const termIds = new Set(), useIds = new Set(), contextIds = [];
      for (const a of rows) {
        if (state.mode === "TAC") {
          const g = a.groups.find(g => g.kind === kind);
          g.term_ids.forEach(id => termIds.add(id)); contextIds.push(...g.context_ids);
          a.uses.filter(u => g.context_ids.includes(u.context_id)).forEach(u => useIds.add(u.use_id));
        } else {
          const g = a.category_groups[state.mode].find(g => g.category === kind);
          g.term_ids.forEach(id => termIds.add(id)); g.use_ids.forEach(id => useIds.add(id));
        }
      }
      return {id: `${state.mode}:${state.article || "all"}:${kind}`, kind, count: termIds.size, term_ids: [...termIds],
        use_ids: [...useIds], context_ids: contextIds, title: groupName(kind), label: groupName(kind),
        section_status: state.mode === "TAC" && rows.length === 1 ? rows[0].groups.find(g => g.kind === kind).section_status : null};
    });
  }
  const resetView = () => {state.x = state.y = 0; state.zoom = 1; transform();};
  const transform = () => $("scene").setAttribute("transform", `translate(${state.x} ${state.y}) scale(${state.zoom})`);
  const hideTooltip = () => {$("graph-tooltip").hidden = true;};

  function showTooltip(text, event) {
    const box = $("graph-wrap").getBoundingClientRect();
    const tip = $("graph-tooltip"); tip.textContent = text; tip.hidden = false;
    const x = event.clientX === undefined ? box.width / 2 : event.clientX - box.left;
    const y = event.clientY === undefined ? 20 : event.clientY - box.top;
    tip.style.left = Math.max(8, Math.min(x + 15, box.width - tip.offsetWidth - 8)) + "px";
    tip.style.top = Math.max(8, Math.min(y + 15, box.height - tip.offsetHeight - 8)) + "px";
  }

  function bubble(parent, node, handler, color) {
    const g = svgEl("g", {class: "bubble", role: "button", tabindex: "0",
      transform: `translate(${node.x} ${node.y})`, "data-group-id": node.id, "data-count": node.count,
      "aria-label": `${node.title}: ${node.count} уникальных terms`});
    const circle = svgEl("circle", {r: node.r, "data-size-count": node.count});
    if (color) {circle.style.fill = color; circle.style.stroke = color;}
    g.append(svgEl("rect", {class: "node-hit", x: -22, y: -22, width: 44, height: 44, fill: "transparent", stroke: "none"}), circle);
    const small = node.r < 35;
    g.append(svgEl("text", {class: "node-number", y: small ? -4 : -17}, node.code));
    g.append(svgEl("text", {class: "node-count", y: small ? 15 : 8}, node.count));
    if (node.r >= 48) g.append(svgEl("text", {class: "node-label", y: 29}, short(node.label, Math.floor(node.r / 3.8))));
    g.append(svgEl("title", {}, `${node.title}\n${node.count} уникальных terms`));
    g.addEventListener("click", () => {hideTooltip(); handler();});
    g.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {event.preventDefault(); handler();}
    });
    g.addEventListener("pointermove", event => showTooltip(`${node.title}\n${node.count} уникальных terms`, event));
    g.addEventListener("pointerleave", hideTooltip);
    g.addEventListener("focus", event => showTooltip(`${node.title}\n${node.count} уникальных terms`, event));
    g.addEventListener("blur", hideTooltip);
    parent.append(g); return g;
  }

  // Deterministic packing. Position carries no scientific meaning. All radii share
  // one scale factor, so area/count is constant, including after fitting/zooming.
  function pack(nodes, width, height) {
    const placed = [];
    for (const node of [...nodes].sort((a, b) => b.count - a.count || a.id.localeCompare(b.id))) {
      const r = Math.sqrt(node.count) * 6;
      let x = 0, y = 0;
      for (let i = 0; i < 40000; i++) {
        const distance = 4 * Math.sqrt(i), angle = i * 2.399963229728653;
        x = distance * Math.cos(angle); y = distance * Math.sin(angle);
        if (placed.every(p => Math.hypot(p.x - x, p.y - y) >= p.r + r + 9)) break;
        if (i === 39999) throw new Error("Terms graph layout could not place all circles");
      }
      placed.push({...node, x, y, r});
    }
    const left = Math.min(...placed.map(p => p.x - p.r)), right = Math.max(...placed.map(p => p.x + p.r));
    const top = Math.min(...placed.map(p => p.y - p.r)), bottom = Math.max(...placed.map(p => p.y + p.r));
    const scale = Math.min((width - 44) / (right - left), (height - 44) / (bottom - top));
    return placed.map(p => ({...p, r: p.r * scale,
      x: width / 2 + (p.x - (left + right) / 2) * scale,
      y: height / 2 + (p.y - (top + bottom) / 2) * scale}));
  }

  function draw() {
    hideTooltip();
    const width = $("graph-wrap").clientWidth, height = $("graph-wrap").clientHeight;
    $("graph").setAttribute("viewBox", `0 0 ${width} ${height}`);
    const scene = $("scene"); scene.replaceChildren();
    const a = current();
    if (state.mode === "articles") {
      const positive = data.articles.filter(row => row.count > 0);
      const nodes = pack(positive.map(row => ({id: `article:${row.article_id}`, count: row.count,
        title: row.title, code: `A${String(row.number).padStart(2, "0")}`, label: row.title, article: row})), width, height);
      for (const node of nodes) bubble(scene, node, () => chooseArticle(node.article.article_id));
    } else {
      const term = a && indexes.get(a.article_id).terms.get(state.term);
      const groups = viewGroups().filter(g => g.count);
      const max = Math.max(1, ...groups.map(g => g.count));
      const orbit = Math.min(width, height) * .32;
      const maxRadius = state.mode === "TAC" ? Math.min(width * .19, height * .19) :
        Math.min(orbit * (groups.length < 3 ? .46 : Math.sin(Math.PI / groups.length) * .76), width * .18);
      const radiusScale = maxRadius / Math.sqrt(max);
      const center = {x: width / 2, y: height / 2};
      const orbitX = Math.min(width * .29, width / 2 - maxRadius - 22);
      const orbitY = height * .30;
      const layoutGroups = state.mode === "TAC" ? viewGroups() : groups;
      const positions = layoutGroups.map((g, i) => {
        const angle = (-90 + 360 / layoutGroups.length * i) * Math.PI / 180;
        return {...g, code: state.mode === "TAC" ? g.kind : `G${i + 1}`, r: radiusScale * Math.sqrt(g.count),
          x: center.x + (state.mode === "TAC" ? orbitX : orbit) * Math.cos(angle),
          y: center.y + (state.mode === "TAC" ? orbitY : orbit) * Math.sin(angle)};
      });
      for (const node of positions) {
        const member = term && membership(term).includes(node.kind);
        if (member) {
          const dx = node.x - center.x, dy = node.y - center.y, length = Math.hypot(dx, dy);
          scene.append(svgEl("line", {class: "membership", x1: center.x + dx / length * 30,
            y1: center.y + dy / length * 30, x2: node.x - dx / length * node.r,
            y2: node.y - dy / length * node.r, "data-membership-kind": node.kind}));
        }
        if (node.count) {
          const group = bubble(scene, node, () => chooseGroup(node.kind), groupColor(node.kind));
          if (member || state.kind === node.kind) group.classList.add("active");
          if (term && !member) group.classList.add("dim");
          group.setAttribute("aria-pressed", String(state.kind === node.kind));
        } else {
          scene.append(svgEl("text", {class: "zero-label", x: node.x, y: node.y}, `${groupName(node.kind)} · 0`));
        }
      }
      const centerNode = svgEl("g", {class: "term-node", transform: `translate(${center.x} ${center.y})`});
      centerNode.append(svgEl("circle", {r: 28}));
      centerNode.append(svgEl("text", {x: 0, y: 5, "text-anchor": "middle"}, term ? "term" : state.mode === "TAC" ? "TAC" : "Terms"));
      centerNode.append(svgEl("title", {}, term ? term.label : a ? a.title : "Все статьи; локальные IDs сохранены"));
      scene.append(centerNode);
      scene.append(svgEl("text", {class: "node-label", x: center.x, y: center.y - 48, "text-anchor": "middle",
        fill: "var(--text)"}, term ? short(term.label, Math.min(Math.floor(width / 9), state.mode === "TAC" ? 100 : 14)) : `${scope().reduce((n, a) => n + a.count, 0)} terms`));
    }
    transform();
  }

  function chooseArticle(id) {
    state.article = id; state.kind = state.term = null; state.query = ""; $("search").value = "";
    if (!id) state.mode = "articles";
    else if (state.mode === "articles") state.mode = "TAC";
    resetView(); render(); $("list").scrollTop = 0;
  }
  function chooseGroup(kind) {
    state.kind = kind; state.query = ""; $("search").value = "";
    const a = current(), t = a && indexes.get(a.article_id).terms.get(state.term);
    if (t && kind && !membership(t).includes(kind)) state.term = null;
    render(); $("list").scrollTop = 0;
  }
  function chooseTerm(id) {
    state.article = termArticle.get(id);
    const a = current(), term = indexes.get(a.article_id).terms.get(id);
    if (!term) throw new Error("Terms graph term ID missing");
    if (state.kind && !membership(term).includes(state.kind)) state.kind = null;
    const restoreFocus = document.activeElement?.dataset.termId === id;
    state.term = id; render();
    if (restoreFocus) $("list").querySelector(`[data-term-id="${id}"]`).focus({preventScroll: true});
  }

  function renderList() {
    const a = current(), list = $("list"), termView = state.mode !== "articles"; list.replaceChildren();
    const query = state.query.toLocaleLowerCase();
    const source = termView ? scope().flatMap(article => article.terms.map((t, rank) => ({...t, article_id: article.article_id,
      article_title: article.title, article_number: article.number, rank}))).filter(t => !state.kind || membership(t).includes(state.kind)) : data.articles;
    const rows = source.filter(row => (termView ? row.label : row.title).toLocaleLowerCase().includes(query));
    const compare = (one, two) => {
      const x = Array.from(one), y = Array.from(two);
      for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i].codePointAt(0) - y[i].codePointAt(0);
      return x.length - y.length;
    };
    const useFilter = state.kind && new Set(viewGroups().find(g => g.kind === state.kind).use_ids);
    function sourceKey(term) {
      const index = indexes.get(term.article_id);
      const positions = term.use_ids.filter(id => !useFilter || useFilter.has(id)).map(id => {
        const m = index.mentions.get(index.uses.get(id).mention_id).source; return [m.page_number, m.start, id];
      });
      positions.sort((x, y) => x[0] - y[0] || x[1] - y[1] || compare(x[2], y[2]));
      return positions[0];
    }
    if (termView && state.sort === "alphabetical") rows.sort((x, y) => compare(x.sort_key || x.label.toLowerCase(), y.sort_key || y.label.toLowerCase()) || compare(x.term_id, y.term_id));
    if (termView && state.sort === "source") rows.sort((x, y) => {
      const one = sourceKey(x), two = sourceKey(y);
      return x.article_number - y.article_number || one[0] - two[0] || one[1] - two[1] || compare(one[2], two[2]) || compare(x.term_id, y.term_id);
    });
    $("list-heading").textContent = termView ? (state.kind ? `Terms · ${groupName(state.kind)}` : a ? "Все terms статьи" : "Все локальные terms") : "Выбрать статью";
    $("list-count").textContent = `${rows.length} / ${source.length}`;
    $("search").placeholder = termView ? "Поиск term…" : "Название статьи…";
    for (const row of rows) {
      const button = action("", () => termView ? chooseTerm(row.term_id) : chooseArticle(row.article_id), "list-item");
      if (termView) {
        button.dataset.termId = row.term_id; button.setAttribute("aria-pressed", String(state.term === row.term_id));
        button.append(el("span", row.label, "label"));
        const meta = el("span", undefined, "meta");
        if (state.mode === "TAC") for (const kind of row.groups) meta.append(el("span", kind, "kind-badge"));
        meta.append(document.createTextNode(a ? `${row.use_ids.length} привязок к контексту` : row.article_title)); button.append(meta);
      } else {
        button.dataset.articleId = row.article_id;
        button.append(el("span", row.title, "label"), el("span", `A${String(row.number).padStart(2, "0")} · ${row.count} terms`, "meta"));
      }
      list.append(button);
    }
    $("list-status").textContent = query ? `Найдено: ${rows.length}. Размеры кругов отражают полный состав групп.` :
      (termView ? "Пересечения сохранены. Неизвестные назначения остаются в отдельных группах." : "Локальные term IDs разных статей сохранены раздельно.");
    if (!rows.length) {
      const group = termView && viewGroups().find(g => g.kind === state.kind);
      const message = !query && group && state.mode === "TAC" ?
        `Terms отсутствуют в сохранённых контекстах. Контекстов: ${group.context_ids.length}. Статус раздела: ${group.section_status ?? "не записан"}.` :
        "Нет совпадений в текущей области. Категории — предложения; отсутствие совпадений не доказывает отсутствие понятия в статье.";
      list.append(el("p", message, "article-empty"));
    }
  }

  function sourceDiagnostics(source, extra = {}) {
    const details = el("details"); details.append(el("summary", "Источник и диагностика"));
    const dl = el("dl");
    for (const [key, value] of Object.entries({...extra, ...source})) {
      if (["quote", "original_href", "layer_href"].includes(key)) continue;
      dl.append(el("dt", key), el("dd", typeof value === "object" ? JSON.stringify(value) : String(value)));
    }
    details.append(dl); return details;
  }

  function contextView(context, uses, index) {
    const section = el("section", undefined, "detail-context"); section.dataset.contextId = context.context_id;
    const s = context.source, heading = el("h3");
    heading.append(el("span", context.kind, "kind-badge"), document.createTextNode(`${names[context.kind]} · стр. ${s.page_number}`));
    section.append(heading, el("p", `${s.text_layer} · границы: ${context.boundary_status}`, "source-meta"));
    const links = el("div", undefined, "source-links");
    links.append(link("Исходный PDF ↗", s.original_href));
    if (s.layer_pdf_sha256 !== s.original_pdf_sha256) links.append(link("PDF текстового слоя ↗", s.layer_href));
    section.append(links);
    for (const u of uses) {
      const m = index.mentions.get(u.mention_id), fragment = el("div", undefined, "mention");
      fragment.dataset.useId = u.use_id; fragment.dataset.mentionId = u.mention_id;
      fragment.append(el("div", `Точное вхождение · [${m.source.start}, ${m.source.end})`, "coords"));
      fragment.append(el("pre", m.source.quote, "mention-quote"));
      fragment.append(sourceDiagnostics(m.source, {mention_id: m.mention_id, use_id: u.use_id, term_id: u.term_id}));
      section.append(fragment);
    }
    const details = el("details"), pre = el("pre", undefined, "context-quote");
    details.append(el("summary", `Полный контекст · [${s.start}, ${s.end})`));
    // Python offsets count Unicode code points. JS string indices count UTF-16;
    // Array.from preserves the source contract even when a quote contains emoji.
    const points = Array.from(s.quote);
    const spans = uses.map(u => index.mentions.get(u.mention_id).source).map(m => ({start: m.start - s.start, end: m.end - s.start}))
      .sort((a, b) => a.start - b.start || a.end - b.end);
    const merged = [];
    for (const span of spans) {
      if (span.start < 0 || span.end > points.length) throw new Error("Term quote outside frozen context");
      const previous = merged.at(-1);
      if (previous && span.start <= previous.end) previous.end = Math.max(previous.end, span.end);
      else merged.push({...span});
    }
    let position = 0;
    for (const span of merged) {
      pre.append(document.createTextNode(points.slice(position, span.start).join("")), el("mark", points.slice(span.start, span.end).join("")));
      position = span.end;
    }
    pre.append(document.createTextNode(points.slice(position).join(""))); details.append(pre); section.append(details);
    section.append(sourceDiagnostics(s, {context_id: context.context_id, method: context.method,
      boundary_status: context.boundary_status, scope: context.scope}));
    return section;
  }

  function renderDetail() {
    const detail = $("detail"), a = current(); detail.replaceChildren();
    const index = a && indexes.get(a.article_id), term = index && index.terms.get(state.term);
    if (!term) {
      const empty = el("div", undefined, "empty-detail");
      empty.append(el("span", "↗", "empty-symbol"), el("p", a ? "Выберите term в списке." : "Выберите статью на карте или в списке."));
      if (a) {
        empty.append(el("p", a.title, "muted"), link("Исходный PDF ↗", a.original_href));
        const diagnostics = el("details"); diagnostics.append(el("summary", "Диагностика статьи"), el("pre", a.diagnostics.join("\n") || "Нет сообщений в frozen Terms contexts."));
        empty.append(diagnostics);
      } else empty.append(el("p", "Здесь появятся точное вхождение, полный контекст, страницы и исходный PDF.", "muted"));
      detail.append(empty); return;
    }
    detail.append(el("h3", term.label, "term-title"));
    detail.append(el("p", `${term.groups.map(k => names[k]).join(" + ")} · ${term.use_ids.length} привязок\nКандидат; научное подтверждение отсутствует.`, "term-summary"));
    if (a.assignments) {
      const panel = el("details", undefined, "classification-evidence");
      panel.append(el("summary", "Классификация: предложения и основания"));
      const labels = {type: "Тип", role: "Роль", origin: "Происхождение"};
      const states = {proposed: "Предложено", unclassified: "Не определено", unresolved: "Конфликт"};
      for (const assignment of a.assignments.filter(x => x.term_id === term.term_id)) {
        const item = el("details", undefined, "assignment"); item.dataset.assignmentId = assignment.assignment_id;
        const m = index.mentions.get(assignment.mention_id).source;
        const context = index.contexts.get(assignment.context_id);
        item.append(el("summary", `${labels[assignment.axis]} · ${states[assignment.state]} · ${context.kind} / стр. ${m.page_number} [${m.start}, ${m.end})`));
        item.append(el("p", assignment.diagnostics.join(" "), "source-meta"));
        for (const proposal of assignment.proposals) {
          item.append(el("p", `${data.taxonomy.categories[assignment.axis][proposal.category]} · ${proposal.producer}`));
          for (const basis of proposal.basis) {
            item.append(el("p", `${basis.rule_id} · [${basis.start}, ${basis.end})`, "source-meta"));
            const quote = el("pre", basis.quote, "basis-quote"); quote.dataset.ruleId = basis.rule_id;
            item.append(quote, el("p", basis.rationale, "source-meta"));
          }
          if (proposal.declared_reviewer) item.append(el("p", `Заявленный reviewer: ${proposal.declared_reviewer}. Научная приёмка не выполнена.`, "source-meta"));
        }
        panel.append(item);
      }
      detail.append(panel);
    }
    const byContext = new Map();
    for (const id of term.use_ids) {
      const use = index.uses.get(id);
      if (!byContext.has(use.context_id)) byContext.set(use.context_id, []);
      byContext.get(use.context_id).push(use);
    }
    const entries = [...byContext].sort(([one], [two]) => {
      const x = index.contexts.get(one), y = index.contexts.get(two);
      return x.source.page_number - y.source.page_number || x.source.start - y.source.start || x.kind.localeCompare(y.kind);
    });
    for (const [id, uses] of entries) detail.append(contextView(index.contexts.get(id), uses, index));
    const related = new Map();
    for (const edge of a.containment) {
      const outer = index.uses.get(edge.outer_use_id), inner = index.uses.get(edge.inner_use_id);
      if (outer.term_id === term.term_id) related.set(`inside:${inner.term_id}`, {id: inner.term_id, prefix: "Включает"});
      if (inner.term_id === term.term_id) related.set(`outer:${outer.term_id}`, {id: outer.term_id, prefix: "Внутри"});
    }
    if (related.size) {
      const section = el("details", undefined, "lexical"); section.append(el("summary", `Лексические вложения · ${related.size}`));
      section.append(el("p", "Вложение точных текстовых spans в одном контексте. Научная связь не утверждается.", "source-meta"));
      const buttons = el("div", undefined, "relation-list");
      for (const relation of related.values()) {
        const target = index.terms.get(relation.id), b = action(`${relation.prefix}: ${target.label}`, () => {
          state.query = ""; $("search").value = ""; chooseTerm(target.term_id);
        });
        b.dataset.relatedTermId = target.term_id; buttons.append(b);
      }
      section.append(buttons); detail.append(section);
    }
    document.dispatchEvent(new CustomEvent("ariadne:term", {detail: {article: a, term}}));
  }

  function render() {
    const a = current();
    $("breadcrumb").textContent = a ? ` / ${a.title}` : ` / ${data.totals.articles} документа в frozen scope`;
    const modes = {articles: "Множества статей", TAC: "Подмножества TAC", type: "Предложенные типы", role: "Роли в контексте", origin: "Происхождение в контексте"};
    $("mode").value = state.mode; $("sort").value = state.sort;
    $("map-heading").textContent = modes[state.mode];
    $("map-caption").textContent = "Площадь круга = число уникальных локальных term IDs. Пересечения сохранены.";
    $("map-note").textContent = state.mode === "articles" || state.mode === "TAC" ?
      "Группы по источникам. Terms — кандидаты. Положение кругов не означает сходство." :
      "Черновая таксономия. Категории предложены по конкретным употреблениям; неизвестные и конфликты сохранены. Научная приёмка не выполнена.";
    $("save-view").disabled = state.mode === "articles";
    const groups = $("groups"); groups.replaceChildren();
    if (state.mode !== "articles") {
      const count = scope().reduce((n, a) => n + a.count, 0);
      const all = action(`Все · ${count}`, () => chooseGroup(null)); all.setAttribute("aria-pressed", String(state.kind === null)); groups.append(all);
      for (const g of viewGroups()) {
        const b = action("", () => chooseGroup(g.kind)); b.dataset.kind = g.kind; b.setAttribute("aria-pressed", String(state.kind === g.kind));
        const dot = el("span", undefined, "dot"); dot.style.background = groupColor(g.kind);
        const number = state.mode !== "TAC" && g.count ? `G${viewGroups().filter(g => g.count).findIndex(p => p.kind === g.kind) + 1} · ` : "";
        b.append(dot, document.createTextNode(`${number}${groupName(g.kind)} · ${g.count}${state.mode === "TAC" && !g.context_ids.length ? " · нет контекста" : ""}`)); groups.append(b);
      }
    }
    renderList(); renderDetail(); draw();
  }

  $("search").addEventListener("input", event => {state.query = event.target.value; renderList();});
  $("sort").addEventListener("change", event => {state.sort = event.target.value; renderList();});
  $("mode").addEventListener("change", event => {
    const mode = event.target.value;
    if (mode === "articles") {chooseArticle(null); return;}
    state.mode = mode; state.kind = null; state.query = ""; $("search").value = ""; resetView(); render(); $("list").scrollTop = 0;
  });
  $("save-view").addEventListener("click", () => {
    const view = {schema: "tac_terms_view_v0.1", input_sha256: data.provenance.input_sha256,
      taxonomy_state: data.taxonomy?.state || "not_attached", axis: state.mode, article_id: state.article,
      filters: state.kind ? {[state.mode]: state.kind} : {}, query: state.query, sort: state.sort,
      review_revision_cutoff: data.review?.revision_cutoff || 0, state: data.review ? "local_review_overlay" : "frozen_proposals_only",
      term_ids: [...$("list").querySelectorAll("[data-term-id]")].map(n => n.dataset.termId)};
    const blob = new Blob([JSON.stringify(view, null, 2)], {type: "application/json"}), url = URL.createObjectURL(blob);
    const a = el("a"); a.href = url; a.download = "ariadne_terms_subset.json"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $("home").addEventListener("click", () => chooseArticle(null));
  $("fit").addEventListener("click", resetView);
  function zoom(factor, x, y) {
    const before = state.zoom, after = Math.max(.5, Math.min(4, before * factor));
    state.x = x - (x - state.x) * after / before;
    state.y = y - (y - state.y) * after / before;
    state.zoom = after; hideTooltip(); transform();
  }
  $("zoom-in").addEventListener("click", () => zoom(1.25, $("graph-wrap").clientWidth / 2, $("graph-wrap").clientHeight / 2));
  $("zoom-out").addEventListener("click", () => zoom(.8, $("graph-wrap").clientWidth / 2, $("graph-wrap").clientHeight / 2));
  $("graph").addEventListener("wheel", event => {
    event.preventDefault(); const rect = $("graph").getBoundingClientRect();
    zoom(event.deltaY < 0 ? 1.1 : 1 / 1.1, event.clientX - rect.left, event.clientY - rect.top);
  }, {passive: false});
  let drag = null;
  $("graph").addEventListener("pointerdown", event => {
    if (event.target.closest(".bubble")) return;
    drag = {x: event.clientX, y: event.clientY, originX: state.x, originY: state.y};
    $("graph").setPointerCapture(event.pointerId); hideTooltip();
  });
  $("graph").addEventListener("pointermove", event => {
    if (!drag) return;
    state.x = drag.originX + event.clientX - drag.x; state.y = drag.originY + event.clientY - drag.y; transform();
  });
  for (const event of ["pointerup", "pointercancel", "lostpointercapture"]) $("graph").addEventListener(event, () => {drag = null;});
  $("provenance-toggle").addEventListener("click", () => {
    const panel = $("provenance"), open = panel.hidden;
    panel.hidden = !open; $("provenance-toggle").setAttribute("aria-expanded", String(open));
    if (!panel.childNodes.length) panel.append(el("h2", data.schema), el("pre", JSON.stringify(data.provenance, null, 2)));
  });
  const totals = $("totals");
  totals.append(el("strong", `${data.totals.terms.toLocaleString("ru")} terms`), document.createTextNode(`\n${data.totals.articles} статьи · ${data.totals.contexts} контекстов`));
  if (!data.taxonomy) for (const option of $("mode").options) if (!["articles", "TAC"].includes(option.value)) option.disabled = true;
  render();
  window.ariadneTermsGraph = {data, state, chooseTerm, render};
  new ResizeObserver(() => {resetView(); draw();}).observe($("graph-wrap"));
})();
