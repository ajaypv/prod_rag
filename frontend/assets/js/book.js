const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function scrollToPageTop() {
  window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
}

function initialiseReadingProgress() {
  const bar = document.querySelector(".reading-progress span");
  if (!bar) return;

  const update = () => {
    const available = document.documentElement.scrollHeight - window.innerHeight;
    const progress = available > 0 ? Math.min(1, window.scrollY / available) : 0;
    bar.style.width = `${progress * 100}%`;
  };
  update();
  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
}

function initialiseGlossary() {
  const contents = document.querySelector("[data-book-contents]");
  const reader = document.querySelector("[data-chapter-reader]");
  if (!contents || !reader) return;

  const chapters = [...document.querySelectorAll("[data-chapter]")];
  const chapterLinks = [...document.querySelectorAll("[data-chapter-link]")];
  const search = document.querySelector("[data-glossary-search]");
  const filterButtons = [...document.querySelectorAll("[data-category-filter]")];
  const groups = [...document.querySelectorAll("[data-category-group]")];
  const resultCount = document.querySelector("[data-result-count]");
  const noResults = document.querySelector("[data-no-results]");
  let activeCategory = "All topics";

  function showContents({ updateHistory = true } = {}) {
    chapters.forEach((chapter) => { chapter.hidden = true; });
    reader.hidden = true;
    contents.hidden = false;
    document.body.classList.remove("reading-chapter");
    document.title = "RAG Textbook";
    if (updateHistory) history.pushState(null, "", window.location.pathname);
    scrollToPageTop();
  }

  function showChapter(id, { updateHistory = true } = {}) {
    const selected = chapters.find((chapter) => chapter.dataset.chapter === id);
    if (!selected) {
      showContents({ updateHistory: false });
      return;
    }

    chapters.forEach((chapter) => { chapter.hidden = chapter !== selected; });
    contents.hidden = true;
    reader.hidden = false;
    document.body.classList.add("reading-chapter");
    document.title = `${selected.querySelector("h1")?.textContent ?? "Concept"} · RAG Textbook`;
    if (updateHistory) history.pushState(null, "", `#concept-${id}`);
    scrollToPageTop();
    selected.querySelector("h1")?.focus({ preventScroll: true });
  }

  chapterLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showChapter(link.dataset.chapterLink);
    });
  });
  document.querySelectorAll("[data-back-to-contents]").forEach((button) => {
    button.addEventListener("click", () => showContents());
  });

  function applyDirectoryFilter() {
    const query = search?.value.trim().toLowerCase() ?? "";
    let visibleCount = 0;

    groups.forEach((group) => {
      let groupCount = 0;
      group.querySelectorAll("[data-search-copy]").forEach((link) => {
        const categoryMatches = activeCategory === "All topics" || link.dataset.category === activeCategory;
        const queryMatches = !query || link.dataset.searchCopy.includes(query);
        link.hidden = !(categoryMatches && queryMatches);
        if (!link.hidden) {
          groupCount += 1;
          visibleCount += 1;
        }
      });
      group.hidden = groupCount === 0;
    });

    if (resultCount) resultCount.textContent = String(visibleCount);
    if (noResults) noResults.hidden = visibleCount !== 0;
  }

  search?.addEventListener("input", applyDirectoryFilter);
  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.categoryFilter;
      filterButtons.forEach((candidate) => candidate.classList.toggle("active", candidate === button));
      applyDirectoryFilter();
    });
  });

  window.addEventListener("hashchange", () => {
    const id = window.location.hash.replace("#concept-", "");
    if (window.location.hash.startsWith("#concept-")) showChapter(id, { updateHistory: false });
    else showContents({ updateHistory: false });
  });

  if (window.location.hash.startsWith("#concept-")) {
    showChapter(window.location.hash.replace("#concept-", ""), { updateHistory: false });
  }
}

function initialiseInterview() {
  const exchanges = [...document.querySelectorAll("[data-interview-exchange]")];
  if (!exchanges.length) return;

  const toggle = document.querySelector("[data-practice-toggle]");
  const progress = document.querySelector("[data-interview-progress]");

  toggle?.addEventListener("click", () => {
    const enabled = !document.body.classList.contains("practice-mode");
    document.body.classList.toggle("practice-mode", enabled);
    toggle.classList.toggle("active", enabled);
    toggle.setAttribute("aria-pressed", String(enabled));
    toggle.textContent = enabled ? "Practice mode on" : "Practice before revealing";
    exchanges.forEach((exchange) => exchange.classList.remove("revealed"));
  });

  document.querySelectorAll("[data-reveal-answer]").forEach((button) => {
    button.addEventListener("click", () => {
      const exchange = button.closest("[data-interview-exchange]");
      exchange?.classList.toggle("revealed");
      button.textContent = exchange?.classList.contains("revealed") ? "Hide candidate answer" : "Show candidate answer";
    });
  });

  if (reduceMotion || !("IntersectionObserver" in window)) {
    exchanges.forEach((exchange) => exchange.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      if (progress) progress.textContent = `Question ${entry.target.dataset.interviewExchange} of ${exchanges.length}`;
    });
  }, { threshold: 0.28, rootMargin: "0px 0px -18%" });
  exchanges.forEach((exchange) => observer.observe(exchange));
}

initialiseReadingProgress();
initialiseGlossary();
initialiseInterview();
