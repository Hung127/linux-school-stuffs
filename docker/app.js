/* Course-notes site behaviour. Vanilla JS, no dependencies, ~6 KB.
 *
 * Six independent features, each guarded so one failure cannot break the
 * page: theme, navigation drawer, table of contents, copy buttons,
 * lightbox, search.
 *
 * Search reads an index inlined into the page as
 * <script type="application/json" id="search-index">, so it works from a
 * file:// URL where fetch() of a sibling file is blocked. No network calls.
 */
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;

  /* ---------------------------------------------------------- theme */

  var THEME_KEY = "course-notes-theme";

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function readTheme() {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch (e) {
      return null; // private mode, or storage disabled
    }
  }

  function storeTheme(value) {
    try {
      localStorage.setItem(THEME_KEY, value);
    } catch (e) {
      /* nothing to do: the toggle still works for this page view */
    }
  }

  function currentTheme() {
    return root.getAttribute("data-theme") || systemTheme();
  }

  function applyTheme(value) {
    root.setAttribute("data-theme", value);
  }

  function initTheme() {
    var toggle = doc.getElementById("theme-toggle");
    if (!toggle) return;

    var DARK_ICON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
    var LIGHT_ICON =
      '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>';
    var LABEL = { dark: "Switch to light theme", light: "Switch to dark theme" };

    function paint() {
      var dark = currentTheme() === "dark";
      toggle.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' +
        (dark ? LIGHT_ICON : DARK_ICON) + "</svg>";
      toggle.setAttribute("aria-label", LABEL[dark ? "dark" : "light"]);
    }

    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      storeTheme(next);
      paint();
    });

    // Follow the system only while the user has expressed no preference.
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var onChange = function (event) {
      if (!readTheme()) {
        applyTheme(event.matches ? "dark" : "light");
        paint();
      }
    };
    if (mq.addEventListener) mq.addEventListener("change", onChange);
    else if (mq.addListener) mq.addListener(onChange);

    paint();
  }

  /* ------------------------------------------------------ nav drawer */

  function initNav() {
    var toggle = doc.getElementById("nav-toggle");
    var sidebar = doc.querySelector(".sidebar");
    var scrim = doc.querySelector(".nav-scrim");
    if (!toggle || !sidebar) return;

    var mobile = window.matchMedia("(max-width: 900px)");

    function setOpen(open) {
      doc.body.classList.toggle("nav-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      sidebar.setAttribute("aria-hidden", open ? "false" : "true");
      if (open) {
        var first = sidebar.querySelector("a");
        if (first) first.focus();
      } else {
        toggle.focus();
      }
    }

    function isOpen() {
      return doc.body.classList.contains("nav-open");
    }

    toggle.addEventListener("click", function () {
      setOpen(!isOpen());
    });
    if (scrim) scrim.addEventListener("click", function () { setOpen(false); });

    doc.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && isOpen()) setOpen(false);
    });

    // Leaving the mobile breakpoint must not strand the drawer open.
    var onChange = function () {
      if (!mobile.matches) {
        doc.body.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
        sidebar.removeAttribute("aria-hidden");
      }
    };
    if (mobile.addEventListener) mobile.addEventListener("change", onChange);
    else if (mobile.addListener) mobile.addListener(onChange);
  }

  /* -------------------------------------------------------------- TOC */

  function initToc() {
    var links = doc.querySelectorAll(".toc-link");
    if (!links.length) return;

    var byId = {};
    var targets = [];
    Array.prototype.forEach.call(links, function (link) {
      var id = decodeURIComponent(link.getAttribute("href").slice(1));
      var heading = doc.getElementById(id);
      if (!heading) return;
      byId[id] = link;
      targets.push({ id: id, link: link, el: heading });
    });
    if (!targets.length) return;

    // Mark the section nearest the top of the viewport, so the highlight
    // tracks the heading you are actually reading rather than the last one
    // that scrolled past.
    var active = null;
    function mark(id) {
      if (active === id) return;
      if (active && byId[active]) byId[active].classList.remove("is-active");
      active = id;
      if (byId[id]) byId[id].classList.add("is-active");
    }

    function onScroll() {
      var offset = 96;
      var current = targets[0].id;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i].el.getBoundingClientRect().top - offset <= 0) {
          current = targets[i].id;
        } else {
          break;
        }
      }
      // At the very bottom, highlight the final heading.
      if (window.innerHeight + window.scrollY >= doc.body.scrollHeight - 2) {
        current = targets[targets.length - 1].id;
      }
      mark(current);
    }

    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        onScroll();
        ticking = false;
      });
    }, { passive: true });

    onScroll();
  }

  /* ---------------------------------------------------- copy buttons */

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // file:// and plain http have no clipboard permission in some browsers.
    return new Promise(function (resolve, reject) {
      var area = doc.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      doc.body.appendChild(area);
      area.select();
      var ok = false;
      try {
        ok = doc.execCommand("copy");
      } catch (e) {
        ok = false;
      }
      doc.body.removeChild(area);
      ok ? resolve() : reject(new Error("copy unavailable"));
    });
  }

  function initCopy() {
    var buttons = doc.querySelectorAll("[data-copy]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function () {
        var block = button.closest(".code-block");
        var code = block && block.querySelector("pre");
        if (!code) return;

        copyText(code.innerText.replace(/\n$/, "")).then(
          function () {
            var previous = button.textContent;
            button.textContent = "Copied";
            button.classList.add("copied");
            button.setAttribute("aria-live", "polite");
            window.setTimeout(function () {
              button.textContent = previous;
              button.classList.remove("copied");
            }, 1600);
          },
          function () {
            button.textContent = "Press Ctrl+C";
            window.setTimeout(function () { button.textContent = "Copy"; }, 2000);
          }
        );
      });
    });
  }

  /* --------------------------------------------------------- lightbox */

  function initLightbox() {
    var images = doc.querySelectorAll(".content img");
    if (!images.length) return;

    var dialog = doc.createElement("dialog");
    dialog.className = "lightbox";
    dialog.setAttribute("aria-label", "Screenshot viewer");
    dialog.innerHTML =
      '<button class="lightbox-close" aria-label="Close viewer">&times;</button>' +
      '<img alt="">' +
      '<p class="lightbox-caption" aria-live="polite"></p>';
    doc.body.appendChild(dialog);

    var img = dialog.querySelector("img");
    var caption = dialog.querySelector(".lightbox-caption");
    var closeBtn = dialog.querySelector(".lightbox-close");
    var lastFocus = null;

    function open(source) {
      lastFocus = doc.activeElement;
      img.src = source.currentSrc || source.src;
      img.alt = source.alt || "";
      caption.textContent = source.alt || "";
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      closeBtn.focus();
    }

    function close() {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      img.removeAttribute("src");
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    Array.prototype.forEach.call(images, function (image) {
      image.setAttribute("tabindex", "0");
      image.setAttribute("role", "button");
      var label = "View screenshot larger" + (image.alt ? ": " + image.alt : "");
      image.setAttribute("aria-label", label);
      image.addEventListener("click", function () { open(image); });
      image.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open(image);
        }
      });
    });

    closeBtn.addEventListener("click", close);
    // Click the backdrop, not the image.
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) close();
    });
  }

  /* ----------------------------------------------------------- search */

  function escapeHtml(text) {
    return text.replace(/[&<>"]/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
    });
  }

  // Trim surrounding whitespace, then cut to a window around the first hit.
  function snippet(text, terms) {
    var flat = text.replace(/\s+/g, " ").trim();
    var at = -1;
    for (var i = 0; i < terms.length && at === -1; i++) {
      at = flat.toLowerCase().indexOf(terms[i]);
    }
    if (at === -1) return escapeHtml(flat.slice(0, 140));
    var start = Math.max(0, at - 55);
    var piece = flat.slice(start, start + 160);
    var html = escapeHtml(piece);
    terms.forEach(function (term) {
      if (!term) return;
      var re = new RegExp("(" + term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
      html = html.replace(re, "<mark>$1</mark>");
    });
    return (start > 0 ? "…" : "") + html + "…";
  }

  function score(entry, terms) {
    var title = entry.title.toLowerCase();
    var text = entry.text.toLowerCase();
    var total = 0;
    for (var i = 0; i < terms.length; i++) {
      var term = terms[i];
      if (!term) continue;
      if (title.indexOf(term) !== -1) total += 40;
      if ((entry.headings || "").toLowerCase().indexOf(term) !== -1) total += 18;
      if (text.indexOf(term) !== -1) total += 6;
    }
    return total;
  }

  function initSearch() {
    var node = doc.getElementById("search-index");
    var dialog = doc.getElementById("search-dialog");
    var openBtn = doc.getElementById("search-toggle");
    if (!node || !dialog || !openBtn) return;

    var entries;
    try {
      entries = JSON.parse(node.textContent);
    } catch (e) {
      return; // malformed index: leave search disabled rather than throwing
    }
    if (!Array.isArray(entries) || !entries.length) return;

    // Index URLs are stored relative to the output root, so a page nested at
    // labs/lab01/ has to walk back up before following one. Derived from the
    // <body> depth the build step records, which stays correct for any
    // deployment path, including a site served from a subdirectory.
    var prefix = "";
    var depth = parseInt(doc.body.getAttribute("data-depth"), 10) || 0;
    for (var d = 0; d < depth; d++) prefix += "../";

    var input = doc.getElementById("search-input");
    var list = doc.getElementById("search-results");
    var hint = doc.getElementById("search-hint");
    if (!input || !list) return;

    var active = -1;
    var results = [];

    function close() {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      openBtn.focus();
    }

    function open() {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      input.focus();
      input.select();
    }

    function render(query) {
      var terms = query.toLowerCase().split(/\s+/).filter(Boolean);
      list.innerHTML = "";
      results = [];
      active = -1;

      if (!terms.length) {
        list.innerHTML = '<li class="search-empty">Type to search the course notes.</li>';
        if (hint) hint.hidden = true;
        return;
      }
      if (hint) hint.hidden = true;

      var scored = [];
      for (var i = 0; i < entries.length; i++) {
        var value = score(entries[i], terms);
        if (value > 0) scored.push({ entry: entries[i], value: value });
      }
      scored.sort(function (a, b) { return b.value - a.value; });
      results = scored.slice(0, 8).map(function (hit) { return hit.entry; });

      if (!results.length) {
        list.innerHTML = '<li class="search-empty">No matches for “' +
          escapeHtml(query) + "”.</li>";
        return;
      }

      results.forEach(function (entry, index) {
        var item = doc.createElement("li");
        item.className = "search-result";
        item.id = "search-result-" + index;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", "false");
        item.innerHTML =
          '<span class="search-result-path">' + escapeHtml(entry.url) + "</span>" +
          '<span class="search-result-title">' + escapeHtml(entry.title) + "</span>" +
          '<span class="search-result-text">' + snippet(entry.text, terms) + "</span>";
        item.addEventListener("click", function () { go(index); });
        item.addEventListener("mousemove", function () { highlight(index); });
        list.appendChild(item);
      });
      highlight(0);
    }

    function highlight(index) {
      if (index === active) return;
      var items = list.querySelectorAll(".search-result");
      if (active >= 0 && items[active]) items[active].setAttribute("aria-selected", "false");
      active = index;
      if (items[index]) {
        items[index].setAttribute("aria-selected", "true");
        input.setAttribute("aria-activedescendant", items[index].id);
        items[index].scrollIntoView({ block: "nearest" });
      }
    }

    function go(index) {
      var entry = results[index];
      if (!entry) return;
      // Relative to this page, so search works from a file:// URL too.
      window.location.href = prefix + entry.url;
    }

    openBtn.addEventListener("click", open);
    input.addEventListener("input", function () { render(input.value); });

    doc.addEventListener("keydown", function (event) {
      var isOpenDialog = dialog.hasAttribute("open");
      // "/" focuses search, the way most documentation sites behave.
      if (event.key === "/" && !isOpenDialog && !/^(INPUT|TEXTAREA)$/.test(
        doc.activeElement && doc.activeElement.tagName)) {
        event.preventDefault();
        open();
        return;
      }
      if (event.key === "Escape" && isOpenDialog) {
        event.preventDefault();
        close();
        return;
      }
      if (!isOpenDialog || !results.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        highlight(Math.min(active + 1, results.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        highlight(Math.max(active - 1, 0));
      } else if (event.key === "Enter" && active >= 0) {
        event.preventDefault();
        go(active);
      }
    });
  }

  /* ------------------------------------------------------------ boot */

  function ready(fn) {
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  ready(function () {
    initTheme();
    initNav();
    initToc();
    initCopy();
    initLightbox();
    initSearch();
  });
})();
