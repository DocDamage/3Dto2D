function setMobileRail(open) {
  document.body.classList.toggle('mobile-rail-open', open);
  $('#mobileRailToggle')?.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function toggleMobileRail() {
  setMobileRail(!document.body.classList.contains('mobile-rail-open'));
}

function installMobileNav() {
  $('#mobileRailToggle')?.addEventListener('click', toggleMobileRail);
  $('#mobileRailBackdrop')?.addEventListener('click', () => setMobileRail(false));
  $$('.rail .nav').forEach(button => {
    button.addEventListener('click', () => setMobileRail(false));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setMobileRail(false);
  });
}

installMobileNav();
