(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const FAV_KEY = "paper-radar-favorites";
  const state = {
    papers: [],
    dirs: new Set(),
    tiers: new Set(),
    range: "7",
    favOnly: false,
    query: ""
  };

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function keyOf(p) { return p.doi || p.url || (p.title + "|" + p.journal); }

  function loadFavs() {
    try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]")); }
    catch (e) { return new Set(); }
  }
  function saveFavs(favs) { localStorage.setItem(FAV_KEY, JSON.stringify([...favs])); }
  let favs = loadFavs();

  function inRange(dateStr, range) {
    if (range === "all" || !dateStr) return true;
    const d = new Date(dateStr);
    if (isNaN(d)) return true;
    const days = (Date.now() - d.getTime()) / 86400000;
    if (this && this.date_precision === "month") {
      return days <= Number(range) + 34 && days >= -40;
    }
    return days <= Number(range) && days >= -7;
  }

  function matches(p) {
    if (state.favOnly && !favs.has(keyOf(p))) return false;
    if (!inRange.call(p, p.publication_date, state.range)) return false;
    if (state.tiers.size && !state.tiers.has(p.tier)) return false;
    if (state.dirs.size) {
      const hit = (p.directions || []).some((d) => state.dirs.has(d));
      if (!hit) return false;
    }
    const q = state.query.trim().toLowerCase();
    if (q) {
      const hay = [p.title, p.doi, p.abstract, (p.directions || []).join(" "), p.journal].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  function renderChips() {
    const box = $("direction-chips");
    const labels = [...new Set(state.papers.flatMap((p) => p.directions || []))].sort();
    box.innerHTML = "";
    labels.forEach((label) => {
      const c = document.createElement("span");
      c.className = "chip" + (state.dirs.has(label) ? " active" : "");
      c.textContent = label;
      c.onclick = () => {
        state.dirs.has(label) ? state.dirs.delete(label) : state.dirs.add(label);
        renderChips(); renderList();
      };
      box.appendChild(c);
    });
  }

  function exportPapers(papers, fmt) {
    if (!papers.length) { alert("当前没有可导出的文章"); return; }
    let text;
    if (fmt === "ris") {
      text = papers.map((p) => {
        const lines = [
          "TY  - JOUR",
          "TI  - " + (p.title || ""),
          "JO  - " + (p.journal || ""),
          "PY  - " + (p.publication_date || "").slice(0, 4),
          "DA  - " + (p.publication_date || ""),
          "UR  - " + (p.url_doi || p.url || ""),
          (p.doi ? "DO  - " + p.doi : ""),
          ...(p.authors || []).map((a) => "AU  - " + a),
          "ER  -"
        ].filter(Boolean);
        return lines.join("\n");
      }).join("\n\n");
      download(text, "papers.ris", "application/x-research-info-systems");
    } else {
      text = papers.map((p) => {
        const year = (p.publication_date || "").slice(0, 4) || "0000";
        const authors = (p.authors || []).map((a) => {
          const parts = a.split(/,\s*/);
          return parts.length > 1 ? parts[1] + ", " + parts[0] : a;
        }).join(" and ") || "Anonymous";
        return "@article{" + (p.doi ? p.doi.replace(/[^a-zA-Z0-9]/g, "") : "paper" + Math.abs([...(p.title || "")].reduce((a, c) => a + c.charCodeAt(0), 0))) +
          ",\n  title = {" + (p.title || "") + "},\n" +
          "  journal = {" + (p.journal || "") + "},\n" +
          "  year = {" + year + "},\n" +
          "  author = {" + authors + "},\n" +
          (p.doi ? "  doi = {" + p.doi + "},\n" : "") +
          "  url = {" + (p.url_doi || p.url || "") + "}\n}";
      }).join("\n\n");
      download(text, "papers.bib", "application/x-bibtex");
    }
  }

  function download(text, filename, mime) {
    const blob = new Blob([text], { type: mime + ";charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 100);
  }

  function card(p) {
    const k = keyOf(p);
    const isFav = favs.has(k);
    const detailId = "d-" + (p.doi || p.title).replace(/[^a-zA-Z0-9]/g, "-").slice(0, 40);
    const s = p.summary || {};
    const summaryHtml = p.summary_status === "done" && p.summary
      ? `<div class="detail-block"><div class="detail-label">一句话概述</div><div class="detail-text">${esc(s.one_liner)}</div></div>
         <div class="detail-block"><div class="detail-label">创新点</div><div class="detail-text">${esc(s.innovation)}</div></div>
         <div class="detail-block"><div class="detail-label">意义与应用前景</div><div class="detail-text">${esc(s.significance)}</div></div>`
      : `<div class="detail-block"><span class="summary-pending">AI 总结待补充（下次运行自动重试）</span></div>`;
    const abstractHtml = p.abstract
      ? `<div class="detail-block">
           <div class="detail-label">摘要 <button class="abstract-toggle" data-target="${detailId}-abs">展开</button></div>
           <div class="detail-text abstract-text" id="${detailId}-abs">${esc(p.abstract)}</div>
         </div>`
      : "";
    const authorHtml = (p.authors && p.authors.length)
      ? `<div class="authors">作者：${esc(p.authors.slice(0, 10).join(", "))}${p.authors.length > 10 ? " 等" : ""}</div>`
      : "";

    const el = document.createElement("article");
    el.className = "paper-card";
    el.innerHTML = `
      <div class="paper-head">
        <div style="flex:1;min-width:0">
          <a class="paper-title" href="${esc(p.url_doi || p.url || "#")}" target="_blank" rel="noopener">${esc(p.title)}</a>
          <div class="paper-meta">
            <span class="tier-badge tier-${esc(p.tier)}">${esc(p.tier)}</span>
            <span>${esc(p.journal)}</span>
            <span>${esc(p.publication_date || "日期未知")}${(p.date_precision === "month" || p.date_precision === "approx") ? "（约）" : ""}</span>
            ${(p.directions || []).map((d) => `<span class="tag">${esc(d)}</span>`).join("")}
          </div>
        </div>
        <button class="star ${isFav ? "active" : ""}" title="收藏" data-key="${esc(k)}">★</button>
      </div>
      ${authorHtml}
      <div class="paper-actions">
        ${p.url_doi ? `<a href="${esc(p.url_doi)}" target="_blank" rel="noopener">DOI ↗</a>` : ""}
        ${p.url_pubmed ? `<a href="${esc(p.url_pubmed)}" target="_blank" rel="noopener">PubMed ↗</a>` : ""}
        <button class="btn export-one" data-fmt="ris">RIS</button>
        <button class="btn export-one" data-fmt="bib">BibTeX</button>
        <button class="btn expand-btn" data-target="${detailId}">展开总结</button>
      </div>
      <div class="paper-detail" id="${detailId}">
        ${summaryHtml}
        ${abstractHtml}
      </div>`;
    el.querySelector(".star").onclick = () => {
      favs.has(k) ? favs.delete(k) : favs.add(k);
      saveFavs(favs);
      el.querySelector(".star").classList.toggle("active", favs.has(k));
      if (state.favOnly) renderList();
    };
    el.querySelector(".expand-btn").onclick = () => {
      const d = document.getElementById(detailId);
      d.classList.toggle("open");
      el.querySelector(".expand-btn").textContent = d.classList.contains("open") ? "收起" : "展开总结";
    };
    el.querySelectorAll(".export-one").forEach((b) => {
      b.onclick = (e) => { e.stopPropagation(); exportPapers([p], b.dataset.fmt); };
    });
    const absBtn = el.querySelector(".abstract-toggle");
    if (absBtn) {
      absBtn.onclick = () => {
        const t = document.getElementById(detailId + "-abs");
        const open = t.classList.toggle("expanded");
        absBtn.textContent = open ? "收起" : "展开";
      };
    }
    return el;
  }

  function renderList() {
    const list = $("paper-list");
    const empty = $("empty-state");
    const filtered = state.papers.filter(matches);
    list.innerHTML = "";
    filtered.forEach((p) => list.appendChild(card(p)));
    empty.classList.toggle("hidden", filtered.length > 0);
    $("result-info").textContent = `显示 ${filtered.length} / ${state.papers.length} 篇相关文章`;
  }

  function init() {
    $("search").addEventListener("input", (e) => { state.query = e.target.value; renderList(); });
    $("range").addEventListener("change", (e) => { state.range = e.target.value; renderList(); });
    $("tier").addEventListener("change", (e) => {
      state.tiers.clear();
      if (e.target.value) state.tiers.add(e.target.value);
      renderList();
    });
    $("fav-only").addEventListener("change", (e) => { state.favOnly = e.target.checked; renderList(); });
    $("export-ris").addEventListener("click", () => exportPapers(state.papers.filter(matches), "ris"));
    $("export-bib").addEventListener("click", () => exportPapers(state.papers.filter(matches), "bib"));

    fetch("data/papers.json")
      .then((r) => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then((data) => {
        state.papers = data.papers || [];
        $("updated-at").textContent = "更新于 " + (data.updated_at || "--").replace("T", " ").slice(0, 16) + " UTC";
        $("total-count").textContent = (data.count || 0) + " 篇";
        renderChips();
        renderList();
      })
      .catch(() => {
        $("empty-state").classList.remove("hidden");
        $("empty-state").querySelector("p").textContent = "数据文件尚未生成，请先运行 python -m pipeline run。";
        $("result-info").textContent = "";
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
