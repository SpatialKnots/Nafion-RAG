(() => {
  "use strict";
  const host = window.ariadneTermsGraph, review = host.data.review;
  if (!review?.online || review.workflow_mode !== "automatic") return;
  const sid = review.snapshot_id, base = "/ui/terms-review";
  const make = (tag, text, attrs = {}) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const style = make("style", `
    #terms-auto-bar{padding:16px;margin-bottom:18px;border:1px solid var(--line);border-radius:14px;background:var(--panel)}
    .terms-auto-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
    .terms-auto-controls label{font-size:12px;display:flex;align-items:center;gap:8px}
    .terms-auto-note{color:var(--muted);font-size:12px;overflow-wrap:anywhere}
    #terms-diagnostics-list{display:flex;gap:7px;flex-wrap:wrap;max-height:190px;overflow:auto}
    #terms-diagnostics-list button{font-size:12px;max-width:300px;text-align:left}
    #terms-auto-status{font-size:12px;white-space:pre-wrap}.terms-auto-error{color:#f2b3a7}
  `);
  document.head.append(style);
  const bar = make("section", undefined, {id: "terms-auto-bar"});
  bar.append(make("h2", "Автоматическая классификация Terms"), make("p",
    "Subsets вычисляются по правилам и точным контекстам. Неизвестные и неоднозначные случаи сохраняются с диагностикой. Ручное разрешение отключено.",
    {class: "terms-auto-note"}));
  const controls = make("div", undefined, {class: "terms-auto-controls"});
  const axis = make("select", undefined, {id: "terms-diagnostic-axis"});
  for (const [value, label] of Object.entries({type: "Тип", role: "Роль", origin: "Происхождение"}))
    axis.append(make("option", label, {value}));
  const kind = make("select", undefined, {id: "terms-diagnostic-kind"});
  for (const [value, label] of Object.entries({conflicts: "Неоднозначные", unknown: "Без поддержанного правила"}))
    kind.append(make("option", label, {value}));
  const label = make("label", "Диагностика"); label.append(axis, kind);
  controls.append(label, make("a", "Архив прежних решений ↗", {href: `${base}/export?snapshot=${sid}`, target: "_blank"}));
  bar.append(controls);
  const details = make("details"), count = make("summary", "Диагностика алгоритма");
  const list = make("div", undefined, {id: "terms-diagnostics-list"});
  details.append(count, list); bar.append(details);
  const status = make("p", review.problems.join(" "), {id: "terms-auto-status"});
  if (review.problems.length) {status.className = "terms-auto-error"; status.setAttribute("role", "alert");}
  bar.append(status);
  document.querySelector(".workspace").before(bar);
  let requestVersion = 0;
  async function diagnostics() {
    const version = ++requestVersion;
    try {
      const params = new URLSearchParams({snapshot: sid, axis: axis.value, queue: kind.value});
      const response = await fetch(`${base}/state?${params}`), data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
      if (version !== requestVersion) return;
      count.textContent = `Диагностика алгоритма · ${data.queue.length} Terms`;
      list.replaceChildren();
      for (const item of data.queue) {
        const button = make("button", `${item.label} · ${item.title}`, {type: "button"});
        button.addEventListener("click", () => {host.state.mode = axis.value; host.state.kind = null; host.chooseTerm(item.term_id);});
        list.append(button);
      }
    } catch (error) {if (version === requestVersion) {status.textContent = String(error); status.className = "terms-auto-error";}}
  }
  axis.addEventListener("change", diagnostics); kind.addEventListener("change", diagnostics);
  diagnostics();
})();
