(function () {
  const body = document.body;
  const prefersReducedMotion = window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;
  const TRANSITION_DURATION = 360;

  function markReady() {
    if (!body || !body.classList.contains('page-transition')) {
      return;
    }
    if (prefersReducedMotion) {
      body.classList.add('page-ready');
      return;
    }
    requestAnimationFrame(() => body.classList.add('page-ready'));
  }

  function navigate(url) {
    if (!url) {
      return;
    }
    if (!body || !body.classList.contains('page-transition') || prefersReducedMotion) {
      window.location.href = url;
      return;
    }
    if (body.classList.contains('page-exit')) {
      return;
    }
    body.classList.remove('page-ready');
    body.classList.add('page-exit');
    window.setTimeout(() => {
      window.location.href = url;
    }, TRANSITION_DURATION);
  }

  function revealSection(element) {
    if (!element) {
      return;
    }
    if (prefersReducedMotion) {
      element.classList.remove('hidden');
      element.classList.add('animated-section', 'is-active');
      return;
    }
    element.classList.add('animated-section');
    if (!element.classList.contains('is-active')) {
      element.classList.remove('hidden');
      element.getBoundingClientRect();
      requestAnimationFrame(() => element.classList.add('is-active'));
    }
  }

  function hideSection(element) {
    if (!element) {
      return;
    }
    if (prefersReducedMotion) {
      element.classList.remove('is-active');
      element.classList.add('hidden');
      return;
    }
    if (element.classList.contains('hidden')) {
      return;
    }
    const finalize = () => {
      element.classList.add('hidden');
      element.removeEventListener('transitionend', finalize);
    };
    element.addEventListener('transitionend', finalize, { once: true });
    window.setTimeout(finalize, TRANSITION_DURATION);
    element.classList.remove('is-active');
  }

  function interceptAnchors(event) {
    const anchor = event.target instanceof Element ? event.target.closest('a[data-transition]') : null;
    if (!anchor) {
      return;
    }
    if (anchor.target === '_blank' || anchor.hasAttribute('download')) {
      return;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    navigate(anchor.href);
  }

  document.addEventListener('DOMContentLoaded', () => {
    markReady();
    document.addEventListener('click', interceptAnchors);
  });

  window.SecurePassTransitions = {
    duration: TRANSITION_DURATION,
    navigate,
    revealSection,
    hideSection
  };
})();
