const root = document.documentElement;
const article = document.querySelector('[data-article]');
const navigation = document.querySelector('[data-navigation]');
const breadcrumbs = document.querySelector('[data-breadcrumbs]');
const toc = document.querySelector('[data-toc]');
const pageNavigation = document.querySelector('[data-page-navigation]');
const editLink = document.querySelector('[data-edit-link]');
const sidebar = document.querySelector('[data-sidebar]');
const overlay = document.querySelector('[data-overlay]');
const menuButton = document.querySelector('[data-menu]');
const themeButton = document.querySelector('[data-theme-toggle]');
const languageButton = document.querySelector('[data-language]');
const contentLanguage = document.querySelector('[data-content-language]');
const progressBar = document.querySelector('[data-progress]');
const searchInput = document.querySelector('[data-search]');
const mobileSearchInput = document.querySelector('[data-search-mobile]');
const mobileSearchResults = document.querySelector('[data-mobile-results]');
const searchResults = document.querySelector('[data-search-results]');
const toast = document.querySelector('[data-toast]');

const GROUPS = [
  {
    id: 'start',
    de: 'Erste Schritte',
    en: 'Getting started',
    icon: '<svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12M10 4l6 6-6 6"/></svg>',
  },
  {
    id: 'entities',
    de: 'Entitäten & Geräte',
    en: 'Entities & devices',
    icon: '<svg viewBox="0 0 20 20" fill="none"><rect x="3" y="3" width="5" height="5" rx="1"/><rect x="12" y="3" width="5" height="5" rx="1"/><rect x="3" y="12" width="5" height="5" rx="1"/><rect x="12" y="12" width="5" height="5" rx="1"/></svg>',
  },
  {
    id: 'automation',
    de: 'Automation',
    en: 'Automation',
    icon: '<svg viewBox="0 0 20 20" fill="none"><path d="m11 2-7 9h5l-1 7 8-10h-5V2Z"/></svg>',
  },
  {
    id: 'operation',
    de: 'Betrieb & Wartung',
    en: 'Operation & maintenance',
    icon: '<svg viewBox="0 0 20 20" fill="none"><path d="M10 3a7 7 0 1 0 7 7M10 6v4l3 2"/></svg>',
  },
  {
    id: 'development',
    de: 'Entwicklung',
    en: 'Development',
    icon: '<svg viewBox="0 0 20 20" fill="none"><path d="m7 5-5 5 5 5m6-10 5 5-5 5"/></svg>',
  },
];

const PAGES = [
  { slug: 'home', file: 'Home.md', group: 'start', de: 'Übersicht', en: 'Overview' },
  { slug: 'installation-and-setup', file: 'Installation-and-Setup.md', group: 'start', de: 'Installation & Einrichtung', en: 'Installation & setup' },
  { slug: 'configuration', file: 'Configuration.md', group: 'start', de: 'Konfiguration', en: 'Configuration' },
  { slug: 'entities', file: 'Entities.md', group: 'entities', de: 'Alle Entitäten', en: 'All entities' },
  { slug: 'supported-devices', file: 'Supported-Devices.md', group: 'entities', de: 'Unterstützte Geräte', en: 'Supported devices' },
  { slug: 'compatibility-matrix', file: 'Compatibility-Matrix.md', group: 'entities', de: 'Kompatibilitätsmatrix', en: 'Compatibility matrix' },
  { slug: 'services', file: 'Services.md', group: 'automation', de: 'Aktionen & Dienste', en: 'Actions & services' },
  { slug: 'examples', file: 'Examples.md', group: 'automation', de: 'Beispiel-Automationen', en: 'Example automations' },
  { slug: 'data-update', file: 'Data-Update.md', group: 'operation', de: 'Datenaktualisierung', en: 'Data update' },
  { slug: 'local-web-interface', file: 'Local-Web-Interface.md', group: 'operation', de: 'Lokale Web-Schnittstelle', en: 'Local web interface' },
  { slug: 'known-limitations', file: 'Known-Limitations.md', group: 'operation', de: 'Bekannte Einschränkungen', en: 'Known limitations' },
  { slug: 'troubleshooting', file: 'Troubleshooting.md', group: 'operation', de: 'Fehlerbehebung', en: 'Troubleshooting' },
  { slug: 'modbus-register', file: 'Modbus-Register.md', group: 'operation', de: 'Modbus-Register', en: 'Modbus registers' },
  { slug: 'stability-and-release-readiness', file: 'Stability-and-Release-Readiness.md', group: 'operation', de: 'Stabilität & Releases', en: 'Stability & releases' },
  { slug: 'navigator-protocol-analysis', file: 'Navigator-Protocol-Analysis.md', group: 'operation', de: 'Navigator-Protokollanalyse', en: 'Navigator protocol analysis' },
  { slug: 'contributing', file: 'Contributing.md', group: 'development', de: 'Mitwirken', en: 'Contributing' },
  { slug: 'changelog', file: 'Changelog.md', group: 'development', de: 'Änderungsverlauf', en: 'Changelog' },
];

const I18N = {
  de: {
    docs: 'Dokumentation', edit: 'Auf GitHub bearbeiten', onThisPage: 'Auf dieser Seite',
    needHelp: 'Hilfe benötigt?', reportIssue: 'Problem auf GitHub melden',
    footer: 'Mit Sorgfalt für die Home-Assistant- und Wärmepumpen-Community dokumentiert.',
    search: 'Dokumentation durchsuchen …', searchResults: 'Suchergebnisse', noResults: 'Keine passenden Inhalte gefunden.',
    previous: 'Vorherige Seite', next: 'Nächste Seite', copied: 'Code kopiert', loading: 'Dokumentation wird geladen …',
    error: 'Diese Seite konnte nicht geladen werden.', contentEnglish: 'Technischer Inhalt: EN',
  },
  en: {
    docs: 'Documentation', edit: 'Edit on GitHub', onThisPage: 'On this page',
    needHelp: 'Need help?', reportIssue: 'Report a problem on GitHub',
    footer: 'Documented with care for the Home Assistant and heat pump community.',
    search: 'Search documentation …', searchResults: 'Search results', noResults: 'No matching content found.',
    previous: 'Previous page', next: 'Next page', copied: 'Code copied', loading: 'Loading documentation …',
    error: 'This page could not be loaded.', contentEnglish: '',
  },
};

const pageCache = new Map();
let language = localStorage.getItem('idm-docs-language') || 'de';
let currentSlug = '';
let headingObserver;

const titleFor = (page) => page[language] || page.en;
const groupFor = (id) => GROUPS.find((group) => group.id === id);
const pageFor = (slug) => PAGES.find((page) => page.slug === slug) || PAGES[0];
const escapeHtml = (value) => value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);

const slugify = (value) => value
  .toLowerCase()
  .replace(/<[^>]+>/g, '')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/^-|-$/g, '');

const parseRoute = () => {
  const route = location.hash.replace(/^#\/?/, '');
  const [slug = 'home', ...anchorParts] = route.split('/');
  return { slug: pageFor(slug).slug, anchor: anchorParts.join('/') };
};

const routeHref = (slug, anchor = '') => `#/${slug}${anchor ? `/${anchor}` : ''}`;

const rewriteInternalHref = (href) => {
  if (!href || /^(https?:|mailto:|tel:)/i.test(href)) return href;
  if (href.startsWith('#')) return routeHref(currentSlug || 'home', href.slice(1));
  const [rawPage, anchor = ''] = href.split('#');
  const normalized = rawPage.replace(/^\.\//, '').replace(/\.md$/i, '');
  const target = PAGES.find((page) => page.file.replace(/\.md$/i, '').toLowerCase() === normalized.toLowerCase());
  if (target) return routeHref(target.slug, anchor);
  if (normalized.startsWith('../')) return `https://github.com/Xerolux/idm-heatpump-hass/blob/main/${normalized.replace(/^\.\.\//, '')}${anchor ? `#${anchor}` : ''}`;
  return href;
};

const fetchPage = async (page) => {
  if (pageCache.has(page.slug)) return pageCache.get(page.slug);
  const response = await fetch(`content/${page.file}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const markdown = await response.text();
  const record = { markdown, text: markdown.replace(/```[\s\S]*?```/g, ' ').replace(/<[^>]+>/g, ' ').replace(/[#>*_`|\[\]()-]/g, ' ').replace(/\s+/g, ' ').trim() };
  pageCache.set(page.slug, record);
  return record;
};

const decorateContent = (html, page) => {
  const template = document.createElement('template');
  template.innerHTML = html;
  const headings = [];
  const usedIds = new Map();

  template.content.querySelectorAll('h1, h2, h3, h4').forEach((heading) => {
    let id = slugify(heading.textContent) || 'section';
    const count = usedIds.get(id) || 0;
    usedIds.set(id, count + 1);
    if (count) id = `${id}-${count + 1}`;
    heading.id = id;
    if (heading.tagName !== 'H1') {
      headings.push({ id, text: heading.textContent, level: Number(heading.tagName[1]) });
      const anchor = document.createElement('a');
      anchor.className = 'heading-anchor';
      anchor.href = routeHref(page.slug, id);
      anchor.setAttribute('aria-label', `Link zu ${heading.textContent}`);
      anchor.textContent = '#';
      heading.append(anchor);
    }
  });

  template.content.querySelectorAll('a[href]').forEach((link) => {
    const original = link.getAttribute('href');
    const rewritten = rewriteInternalHref(original);
    link.setAttribute('href', rewritten);
    if (/^https?:/i.test(rewritten)) {
      link.target = '_blank';
      link.rel = 'noreferrer';
    }
  });

  template.content.querySelectorAll('table').forEach((table) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrap';
    table.replaceWith(wrapper);
    wrapper.append(table);
  });

  template.content.querySelectorAll('pre').forEach((pre) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'code-wrap';
    const button = document.createElement('button');
    button.className = 'copy-code';
    button.type = 'button';
    button.textContent = language === 'de' ? 'Kopieren' : 'Copy';
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(pre.textContent);
      showToast(I18N[language].copied);
    });
    pre.replaceWith(wrapper);
    wrapper.append(pre, button);
  });

  template.content.querySelectorAll('img').forEach((image) => {
    const src = image.getAttribute('src') || '';
    if (src.startsWith('../images/')) image.src = `images/${src.split('/').pop()}`;
    image.loading = 'lazy';
  });

  return { fragment: template.content, headings };
};

const renderNavigation = () => {
  navigation.innerHTML = GROUPS.map((group) => {
    const links = PAGES.filter((page) => page.group === group.id).map((page) => `
      <a class="nav-item${page.slug === currentSlug ? ' is-active' : ''}" href="${routeHref(page.slug)}" data-page="${page.slug}">
        <span>${escapeHtml(titleFor(page))}</span>
      </a>`).join('');
    return `<section class="nav-group"><h2 class="nav-group-title">${group.icon}<span>${escapeHtml(group[language])}</span></h2>${links}</section>`;
  }).join('');
};

const renderBreadcrumbs = (page) => {
  const group = groupFor(page.group);
  breadcrumbs.innerHTML = `<a href="../">IDM Heatpump</a><i>›</i><a href="${routeHref(PAGES.find((item) => item.group === page.group).slug)}">${escapeHtml(group[language])}</a><i>›</i><span>${escapeHtml(titleFor(page))}</span>`;
};

const renderToc = (headings) => {
  const visible = headings.filter((heading) => heading.level <= 3);
  toc.innerHTML = visible.map((heading) => `<a class="toc-link" data-level="${heading.level}" href="${routeHref(currentSlug, heading.id)}" data-toc-id="${heading.id}">${escapeHtml(heading.text)}</a>`).join('');
  headingObserver?.disconnect();
  if (!visible.length) return;
  headingObserver = new IntersectionObserver((entries) => {
    const intersecting = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (!intersecting) return;
    toc.querySelectorAll('.toc-link').forEach((link) => link.classList.toggle('is-active', link.dataset.tocId === intersecting.target.id));
  }, { rootMargin: '-90px 0px -72% 0px' });
  visible.forEach((heading) => {
    const element = document.getElementById(heading.id);
    if (element) headingObserver.observe(element);
  });
};

const renderPageNavigation = (page) => {
  const index = PAGES.indexOf(page);
  const previous = PAGES[index - 1];
  const next = PAGES[index + 1];
  pageNavigation.innerHTML = `
    ${previous ? `<a class="page-nav-link previous" href="${routeHref(previous.slug)}"><span>←</span><p><small>${I18N[language].previous}</small><strong>${escapeHtml(titleFor(previous))}</strong></p></a>` : '<span></span>'}
    ${next ? `<a class="page-nav-link next" href="${routeHref(next.slug)}"><p><small>${I18N[language].next}</small><strong>${escapeHtml(titleFor(next))}</strong></p><span>→</span></a>` : '<span></span>'}`;
};

const loadRoute = async () => {
  const { slug, anchor } = parseRoute();
  const page = pageFor(slug);
  currentSlug = page.slug;
  renderNavigation();
  renderBreadcrumbs(page);
  renderPageNavigation(page);
  editLink.href = `https://github.com/Xerolux/idm-heatpump-hass/edit/main/docs/wiki/${page.file}`;
  contentLanguage.hidden = language === 'en';
  contentLanguage.textContent = I18N[language].contentEnglish;
  article.innerHTML = `<div class="article-loading"><i></i><span>${I18N[language].loading}</span></div>`;
  closeMenu();

  try {
    const record = await fetchPage(page);
    const rendered = marked.parse(record.markdown, { gfm: true });
    const { fragment, headings } = decorateContent(rendered, page);
    article.innerHTML = '';
    article.append(fragment);
    renderToc(headings);
    document.title = `${titleFor(page)} · IDM Heatpump`;
    if (anchor) {
      requestAnimationFrame(() => document.getElementById(anchor)?.scrollIntoView());
    } else {
      window.scrollTo({ top: 0, behavior: 'auto' });
    }
  } catch (error) {
    article.innerHTML = `<div class="article-error"><strong>${I18N[language].error}</strong><span>${escapeHtml(error.message)}</span></div>`;
    toc.innerHTML = '';
  }
};

const updateLanguage = () => {
  root.lang = language;
  languageButton.textContent = language.toUpperCase();
  document.querySelectorAll('[data-i18n]').forEach((element) => {
    const value = I18N[language][element.dataset.i18n];
    if (value) element.textContent = value;
  });
  searchInput.placeholder = I18N[language].search;
  mobileSearchInput.placeholder = I18N[language].search;
};

const closeMenu = () => {
  sidebar.classList.remove('is-open');
  overlay.classList.remove('is-visible');
  menuButton.setAttribute('aria-expanded', 'false');
  document.body.classList.remove('menu-open');
};

const showToast = (message) => {
  toast.textContent = message;
  toast.classList.add('is-visible');
  setTimeout(() => toast.classList.remove('is-visible'), 1800);
};

const indexAllPages = async () => {
  await Promise.all(PAGES.map((page) => fetchPage(page).catch(() => null)));
};

const makeSnippet = (text, term) => {
  const lower = text.toLowerCase();
  const index = Math.max(0, lower.indexOf(term.toLowerCase()));
  const start = Math.max(0, index - 65);
  const end = Math.min(text.length, index + term.length + 100);
  let snippet = `${start ? '…' : ''}${text.slice(start, end)}${end < text.length ? '…' : ''}`;
  const safe = escapeHtml(snippet);
  return safe.replace(new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig'), '<mark>$1</mark>');
};

const search = async (query, target = searchResults) => {
  const term = query.trim();
  if (term.length < 2) {
    target.hidden = true;
    return;
  }
  await indexAllPages();
  const words = term.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = PAGES.map((page) => {
    const record = pageCache.get(page.slug);
    if (!record) return null;
    const title = `${page.de} ${page.en}`.toLowerCase();
    const body = record.text.toLowerCase();
    let score = 0;
    words.forEach((word) => {
      if (title.includes(word)) score += 12;
      score += Math.min(7, body.split(word).length - 1);
    });
    return score ? { page, record, score } : null;
  }).filter(Boolean).sort((a, b) => b.score - a.score).slice(0, 8);

  target.innerHTML = matches.length
    ? `<div class="search-heading">${I18N[language].searchResults}</div>${matches.map(({ page, record }) => `<a class="search-result" href="${routeHref(page.slug)}"><strong>${escapeHtml(titleFor(page))}</strong><p>${makeSnippet(record.text, words[0])}</p></a>`).join('')}`
    : `<div class="search-empty">${I18N[language].noResults}</div>`;
  target.hidden = false;
};

const savedTheme = localStorage.getItem('idm-theme');
root.dataset.theme = savedTheme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
const updateThemeLabel = () => {
  const light = root.dataset.theme === 'light';
  themeButton.setAttribute('aria-label', light ? 'Dunkles Design aktivieren' : 'Helles Design aktivieren');
  document.querySelector('meta[name="theme-color"]').content = light ? '#f6f9f6' : '#07110f';
};
updateThemeLabel();
updateLanguage();

themeButton.addEventListener('click', () => {
  root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('idm-theme', root.dataset.theme);
  updateThemeLabel();
});

languageButton.addEventListener('click', () => {
  language = language === 'de' ? 'en' : 'de';
  localStorage.setItem('idm-docs-language', language);
  updateLanguage();
  loadRoute();
});

menuButton.addEventListener('click', () => {
  const opening = !sidebar.classList.contains('is-open');
  sidebar.classList.toggle('is-open', opening);
  overlay.classList.toggle('is-visible', opening);
  menuButton.setAttribute('aria-expanded', String(opening));
  document.body.classList.toggle('menu-open', opening);
});
overlay.addEventListener('click', closeMenu);

let searchTimer;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => search(searchInput.value), 120);
});
mobileSearchInput.addEventListener('input', async () => {
  searchInput.value = mobileSearchInput.value;
  await search(mobileSearchInput.value, mobileSearchResults);
});

document.addEventListener('keydown', (event) => {
  if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
    event.preventDefault();
    searchInput.focus();
  }
  if (event.key === 'Escape') {
    searchResults.hidden = true;
    mobileSearchResults.hidden = true;
    closeMenu();
  }
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('[data-search-wrap]')) searchResults.hidden = true;
});
searchResults.addEventListener('click', () => { searchResults.hidden = true; searchInput.value = ''; });
mobileSearchResults.addEventListener('click', () => {
  mobileSearchResults.hidden = true;
  mobileSearchInput.value = '';
  closeMenu();
});

window.addEventListener('hashchange', loadRoute);
window.addEventListener('resize', () => { if (innerWidth > 760) closeMenu(); });
window.addEventListener('scroll', () => {
  const max = document.documentElement.scrollHeight - innerHeight;
  progressBar.style.width = `${max > 0 ? Math.min(100, (scrollY / max) * 100) : 0}%`;
}, { passive: true });

loadRoute();
if ('requestIdleCallback' in window) {
  window.requestIdleCallback(() => indexAllPages());
} else {
  window.setTimeout(() => indexAllPages(), 250);
}
