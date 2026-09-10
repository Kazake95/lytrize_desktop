(function () {
  const root = document.documentElement;
  const themeButton = document.getElementById('theme-toggle');
  const menuButton = document.getElementById('menu-toggle');
  const mobileNav = document.getElementById('mobile-nav');
  const year = document.getElementById('year');
  const themeMeta = document.getElementById('theme-color-meta');

  const saved = localStorage.getItem('lytrize-theme');
  const systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  let theme = saved || (systemDark ? 'dark' : 'light');

  function applyTheme(value) {
    root.setAttribute('data-theme', value);
    localStorage.setItem('lytrize-theme', value);
    themeButton.textContent = value === 'dark' ? '☀' : '☾';
    themeButton.setAttribute('title', value === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    themeButton.setAttribute('aria-label', value === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    themeMeta.setAttribute('content', value === 'dark' ? '#080b14' : '#f7f8fc');
  }

  applyTheme(theme);

  themeButton.addEventListener('click', function () {
    theme = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(theme);
  });

  menuButton.addEventListener('click', function () {
    const open = mobileNav.classList.toggle('open');
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  });

  mobileNav.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', function () {
      mobileNav.classList.remove('open');
      menuButton.setAttribute('aria-expanded', 'false');
      menuButton.setAttribute('aria-label', 'Open menu');
    });
  });

  if (year) year.textContent = new Date().getFullYear();

  // Add a subtle active-nav hint while scrolling through major sections.
  const navLinks = Array.from(document.querySelectorAll('.desktop-nav a'));
  const sections = navLinks.map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      navLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + entry.target.id));
    });
  }, { rootMargin: '-35% 0px -55% 0px', threshold: 0 });
  sections.forEach(section => observer.observe(section));
})();
