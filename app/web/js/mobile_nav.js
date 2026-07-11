const MOBILE_RAIL_BREAKPOINT = '(max-width: 760px)';
const MOBILE_RAIL_FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])'
].join(',');

let mobileRailMedia = null;
let mobileRailFocusReturn = null;
let mobileNavInstalled = false;

function mobileRailIsNarrow() {
  if (!mobileRailMedia && typeof window.matchMedia === 'function') {
    mobileRailMedia = window.matchMedia(MOBILE_RAIL_BREAKPOINT);
  }
  return mobileRailMedia ? mobileRailMedia.matches : window.innerWidth <= 760;
}

function mobileRailElementIsVisible(element) {
  if (!element || element.hidden || element.getAttribute('aria-hidden') === 'true') return false;
  const style = window.getComputedStyle(element);
  return style.display !== 'none' && style.visibility !== 'hidden';
}

function mobileRailFocusableControls() {
  const rail = document.querySelector('.rail');
  if (!rail) return [];
  return Array.from(rail.querySelectorAll(MOBILE_RAIL_FOCUSABLE)).filter(mobileRailElementIsVisible);
}

function focusMobileRailControl(element) {
  if (!element || typeof element.focus !== 'function') return;
  try {
    element.focus({ preventScroll: true });
  } catch (error) {
    element.focus();
  }
}

function syncMobileRailAccessibility() {
  const narrow = mobileRailIsNarrow();
  const rail = document.querySelector('.rail');
  const toggle = $('#mobileRailToggle');
  const backdrop = $('#mobileRailBackdrop');

  if (!narrow) document.body.classList.remove('mobile-rail-open');
  const open = narrow && document.body.classList.contains('mobile-rail-open');

  if (toggle) {
    const expanded = !narrow || open;
    toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    toggle.setAttribute('aria-hidden', narrow ? 'false' : 'true');
    toggle.setAttribute('aria-label', expanded ? 'Close navigation' : 'Open navigation');
    if (rail) {
      if (!rail.id) rail.id = 'appNavigationRail';
      toggle.setAttribute('aria-controls', rail.id);
    }
  }

  if (rail) {
    const hidden = narrow && !open;
    rail.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    rail.inert = hidden;
  }

  if (backdrop) {
    backdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
  }
}

function setMobileRail(open) {
  const narrow = mobileRailIsNarrow();
  const wasOpen = narrow && document.body.classList.contains('mobile-rail-open');
  const shouldOpen = narrow && Boolean(open);
  const toggle = $('#mobileRailToggle');

  if (shouldOpen && !wasOpen) {
    const active = document.activeElement;
    mobileRailFocusReturn = active && typeof active.focus === 'function' ? active : toggle;
  }

  document.body.classList.toggle('mobile-rail-open', shouldOpen);
  syncMobileRailAccessibility();

  if (shouldOpen && !wasOpen) {
    const focusFirstControl = () => {
      if (!mobileRailIsNarrow() || !document.body.classList.contains('mobile-rail-open')) return;
      const rail = document.querySelector('.rail');
      const firstNavControl = rail?.querySelector('nav')?.querySelector(MOBILE_RAIL_FOCUSABLE);
      focusMobileRailControl(
        mobileRailElementIsVisible(firstNavControl) ? firstNavControl : mobileRailFocusableControls()[0]
      );
    };
    if (typeof window.requestAnimationFrame === 'function') window.requestAnimationFrame(focusFirstControl);
    else focusFirstControl();
  } else if (!shouldOpen && wasOpen) {
    const returnTarget = mobileRailFocusReturn?.isConnected ? mobileRailFocusReturn : toggle;
    mobileRailFocusReturn = null;
    focusMobileRailControl(returnTarget);
  }
}

function toggleMobileRail() {
  setMobileRail(!document.body.classList.contains('mobile-rail-open'));
}

function trapMobileRailFocus(event) {
  if (event.key !== 'Tab' || !mobileRailIsNarrow() || !document.body.classList.contains('mobile-rail-open')) return;

  const toggle = $('#mobileRailToggle');
  const controls = mobileRailFocusableControls();
  if (toggle && mobileRailElementIsVisible(toggle)) controls.push(toggle);

  if (!controls.length) {
    event.preventDefault();
    focusMobileRailControl(toggle);
    return;
  }

  const first = controls[0];
  const last = controls[controls.length - 1];
  const activeIndex = controls.indexOf(document.activeElement);
  if (event.shiftKey && activeIndex <= 0) {
    event.preventDefault();
    focusMobileRailControl(last);
  } else if (!event.shiftKey && (activeIndex === -1 || activeIndex === controls.length - 1)) {
    event.preventDefault();
    focusMobileRailControl(first);
  }
}

function handleMobileRailBreakpointChange() {
  const rail = document.querySelector('.rail');
  const toggle = $('#mobileRailToggle');
  if (mobileRailIsNarrow() && !document.body.classList.contains('mobile-rail-open') && rail?.contains(document.activeElement)) {
    focusMobileRailControl(toggle);
  }
  syncMobileRailAccessibility();
  if (!mobileRailIsNarrow()) mobileRailFocusReturn = null;
}

function installMobileNav() {
  if (mobileNavInstalled) {
    syncMobileRailAccessibility();
    return;
  }
  mobileNavInstalled = true;

  const toggle = $('#mobileRailToggle');
  const backdrop = $('#mobileRailBackdrop');
  const railNav = document.querySelector('.rail nav');

  toggle?.addEventListener('click', toggleMobileRail);
  backdrop?.addEventListener('click', () => setMobileRail(false));
  railNav?.addEventListener('click', event => {
    if (event.target.closest('.nav, .nav-create-sprite-btn, a[href]')) setMobileRail(false);
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && mobileRailIsNarrow() && document.body.classList.contains('mobile-rail-open')) {
      event.preventDefault();
      setMobileRail(false);
      return;
    }
    trapMobileRailFocus(event);
  });

  mobileRailMedia = typeof window.matchMedia === 'function'
    ? window.matchMedia(MOBILE_RAIL_BREAKPOINT)
    : null;
  if (mobileRailMedia?.addEventListener) mobileRailMedia.addEventListener('change', handleMobileRailBreakpointChange);
  else if (mobileRailMedia?.addListener) mobileRailMedia.addListener(handleMobileRailBreakpointChange);

  syncMobileRailAccessibility();
}

installMobileNav();
