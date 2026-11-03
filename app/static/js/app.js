// Small progressive enhancements. Every page works without this file.
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Theme toggle ------------------------------------------------------------------
  function currentTheme() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("sis-theme", next); } catch (e) { /* ignore */ }
    });
  });

  // ---- Toasts: auto-dismiss after 5s, pause on hover ----------------------------------
  function dismiss(toast) {
    if (toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", function () { toast.remove(); }, { once: true });
    if (reduceMotion) toast.remove();
  }
  document.querySelectorAll("[data-toast]").forEach(function (toast) {
    var timer = null;
    var start = function () { timer = window.setTimeout(function () { dismiss(toast); }, 5000); };
    toast.classList.add("is-timed");
    start();
    toast.addEventListener("mouseenter", function () { window.clearTimeout(timer); toast.classList.remove("is-timed"); });
    toast.addEventListener("mouseleave", function () { toast.classList.add("is-timed"); start(); });
    var close = toast.querySelector("[data-toast-close]");
    if (close) close.addEventListener("click", function () { dismiss(toast); });
  });

  // ---- Delete confirmation with <dialog> (falls back to a plain submit) --------------
  var dialog = document.getElementById("confirm-delete");
  var pending = null;
  if (dialog && typeof dialog.showModal === "function") {
    document.querySelectorAll("form[data-confirm-delete]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        pending = form;
        dialog.querySelector("[data-delete-name]").textContent = form.getAttribute("data-name") || "this student";
        dialog.returnValue = "";
        dialog.showModal();
      });
    });
    dialog.addEventListener("close", function () {
      if (dialog.returnValue === "confirm" && pending) pending.submit();  // submit() skips the listener
      pending = null;
    });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close("cancel");  // click on backdrop
    });
  }

  // ---- Filters submit when a select changes -------------------------------------------
  document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () {
      var form = select.form;
      var page = form && form.querySelector("input[name=page]");
      if (page) page.remove();
      if (form) form.requestSubmit ? form.requestSubmit() : form.submit();
    });
  });
  document.addEventListener("keydown", function (event) {
    // "/" focuses the search box, like most dashboards.
    var search = document.querySelector(".field-search input");
    if (event.key === "/" && search && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      event.preventDefault();
      search.focus();
      search.select();
    }
  });

  // ---- KPI count-up --------------------------------------------------------------------
  var counters = document.querySelectorAll("[data-count]");
  function animateCount(el) {
    var target = parseFloat(el.getAttribute("data-count")) || 0;
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var duration = 900;
    var t0 = null;
    function frame(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min((ts - t0) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals);
      if (p < 1) window.requestAnimationFrame(frame);
    }
    window.requestAnimationFrame(frame);
  }
  if (!reduceMotion && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { animateCount(entry.target); io.unobserve(entry.target); }
      });
    }, { threshold: 0.4 });
    counters.forEach(function (el) { io.observe(el); });
  }

  // ---- Hero illustration: gentle 3D tilt toward the pointer ---------------------------
  var tilt = document.querySelector("[data-tilt]");
  if (tilt && !reduceMotion && window.matchMedia("(pointer: fine)").matches) {
    var inner = tilt.firstElementChild;
    var hero = tilt.closest(".hero") || tilt;
    hero.addEventListener("pointermove", function (event) {
      var r = tilt.getBoundingClientRect();
      var x = (event.clientX - r.left) / r.width - 0.5;
      var y = (event.clientY - r.top) / r.height - 0.5;
      inner.style.setProperty("--tilt-y", (x * 14).toFixed(2) + "deg");
      inner.style.setProperty("--tilt-x", (-y * 10).toFixed(2) + "deg");
    });
    hero.addEventListener("pointerleave", function () {
      inner.style.setProperty("--tilt-y", "0deg");
      inner.style.setProperty("--tilt-x", "0deg");
    });
  }

  // ---- Form: live preview, focus the error summary ------------------------------------
  document.querySelectorAll("[data-preview]").forEach(function (target) {
    var input = document.getElementById(target.getAttribute("data-preview"));
    if (!input) return;
    var fallback = target.textContent;
    input.addEventListener("input", function () {
      var value = input.value.trim();
      if (input.id === "roll_number") value = value.toUpperCase();
      target.textContent = value || fallback;
      if (input.id === "name") {
        var avatar = document.querySelector(".preview .avatar");
        if (avatar) {
          var parts = value.split(/\s+/).filter(Boolean);
          avatar.textContent = parts.length ? (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() : "NS";
        }
      }
    });
  });
  var summary = document.querySelector("[data-error-summary]");
  if (summary) summary.focus();
})();
