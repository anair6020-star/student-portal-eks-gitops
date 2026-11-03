// Small progressive enhancements. Every page works without this file.
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
    start();
    toast.addEventListener("mouseenter", function () { window.clearTimeout(timer); });
    toast.addEventListener("mouseleave", start);
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
