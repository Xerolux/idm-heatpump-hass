const root = document.documentElement;
const header = document.querySelector('[data-header]');
const themeToggle = document.querySelector('[data-theme-toggle]');
const menuToggle = document.querySelector('[data-menu-toggle]');
const siteNav = document.querySelector('#site-nav');
const copyButton = document.querySelector('[data-copy]');
const repoUrl = document.querySelector('[data-repo-url]');
const toast = document.querySelector('[data-toast]');

const savedTheme = localStorage.getItem('idm-theme');
const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
const initialTheme = savedTheme || (prefersLight ? 'light' : 'dark');
root.dataset.theme = initialTheme;

const updateThemeLabel = () => {
  const lightActive = root.dataset.theme === 'light';
  themeToggle.setAttribute('aria-label', lightActive ? 'Dunkles Design aktivieren' : 'Helles Design aktivieren');
  document.querySelector('meta[name="theme-color"]').setAttribute('content', lightActive ? '#f3f7f3' : '#07110f');
};

updateThemeLabel();

themeToggle.addEventListener('click', () => {
  root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('idm-theme', root.dataset.theme);
  updateThemeLabel();
});

const closeMenu = () => {
  siteNav.classList.remove('is-open');
  menuToggle.setAttribute('aria-expanded', 'false');
  menuToggle.setAttribute('aria-label', 'Menü öffnen');
  document.body.classList.remove('menu-open');
};

menuToggle.addEventListener('click', () => {
  const willOpen = !siteNav.classList.contains('is-open');
  siteNav.classList.toggle('is-open', willOpen);
  menuToggle.setAttribute('aria-expanded', String(willOpen));
  menuToggle.setAttribute('aria-label', willOpen ? 'Menü schließen' : 'Menü öffnen');
  document.body.classList.toggle('menu-open', willOpen);
});

siteNav.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));

window.addEventListener('resize', () => {
  if (window.innerWidth > 900) closeMenu();
});

const updateHeader = () => header.classList.toggle('is-scrolled', window.scrollY > 16);
updateHeader();
window.addEventListener('scroll', updateHeader, { passive: true });

const tabs = [...document.querySelectorAll('[data-tab]')];
const panels = [...document.querySelectorAll('[data-panel]')];

const activateTab = (tab) => {
  const target = tab.dataset.tab;
  tabs.forEach((item) => item.setAttribute('aria-selected', String(item === tab)));
  panels.forEach((panel) => {
    const isActive = panel.dataset.panel === target;
    panel.hidden = !isActive;
    panel.classList.toggle('is-active', isActive);
  });
};

tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => activateTab(tab));
  tab.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === 'ArrowRight' ? 1 : -1;
    const nextTab = tabs[(index + direction + tabs.length) % tabs.length];
    activateTab(nextTab);
    nextTab.focus();
  });
});

copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(repoUrl.textContent.trim());
  } catch {
    const range = document.createRange();
    range.selectNodeContents(repoUrl);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  toast.classList.add('is-visible');
  window.setTimeout(() => toast.classList.remove('is-visible'), 2200);
});

const revealItems = document.querySelectorAll('.reveal');

revealItems.forEach((item) => {
  const delay = item.dataset.delay;
  if (delay) item.style.setProperty('--delay', `${delay}ms`);
});

if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -40px' },
  );
  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add('is-visible'));
}
