/* Render trusted repository Markdown into crawlable documentation HTML. */

const fs = require('node:fs');
const path = require('node:path');
const { marked } = require('../docs/public/docs/vendor/marked.umd.js');

const [, , markdownPath, currentSlug, pageLanguage = 'en'] = process.argv;

if (!markdownPath || !currentSlug) {
  throw new Error('Usage: node scripts/render_pages_markdown.cjs <markdown-path> <slug> [language]');
}

const slugify = (value) => value
  .toLowerCase()
  .replace(/<[^>]+>/g, '')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/^-|-$/g, '');

const escapeAttribute = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('"', '&quot;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;');

const pageHref = (targetSlug, anchor = '') => {
  let href;
  if (targetSlug === 'home') {
    href = currentSlug === 'home' ? './' : '../';
  } else {
    href = currentSlug === 'home' ? `${targetSlug}/` : `../${targetSlug}/`;
  }
  return `${href}${anchor ? `#${anchor}` : ''}`;
};

const rewriteHref = (href) => {
  if (!href || /^(https?:|mailto:|tel:)/i.test(href)) return href;
  if (href.startsWith('#')) return href;

  const [rawPath, anchor = ''] = href.split('#');
  const normalized = rawPath.replace(/^\.\//, '');
  if (normalized.startsWith('../')) {
    return `https://github.com/Xerolux/idm-heatpump-hass/blob/main/${normalized.replace(/^\.\.\//, '')}${anchor ? `#${anchor}` : ''}`;
  }

  const targetName = path.basename(normalized).replace(/\.md$/i, '');
  if (targetName && !targetName.includes('.')) {
    return pageHref(slugify(targetName), anchor);
  }
  return href;
};

const headingCounts = new Map();
const headings = [];

marked.use({
  gfm: true,
  renderer: {
    heading({ tokens, depth }) {
      const text = this.parser.parseInline(tokens);
      const plainText = tokens.map((token) => token.text || token.raw || '').join('');
      const baseId = slugify(plainText) || 'section';
      const count = headingCounts.get(baseId) || 0;
      headingCounts.set(baseId, count + 1);
      const id = count ? `${baseId}-${count + 1}` : baseId;
      if (depth > 1) headings.push({ id, text: plainText, level: depth });
      return `<h${depth} id="${escapeAttribute(id)}">${text}</h${depth}>`;
    },
    link({ href, title, tokens }) {
      const rewritten = rewriteHref(href);
      const external = /^https?:/i.test(rewritten);
      const titleAttribute = title ? ` title="${escapeAttribute(title)}"` : '';
      const externalAttributes = external ? ' target="_blank" rel="noreferrer"' : '';
      return `<a href="${escapeAttribute(rewritten)}"${titleAttribute}${externalAttributes}>${this.parser.parseInline(tokens)}</a>`;
    },
    image({ href, title, text }) {
      let source = href;
      if (source.startsWith('../images/')) {
        source = `${imageRoot}${path.basename(source)}`;
      }
      const titleAttribute = title ? ` title="${escapeAttribute(title)}"` : '';
      return `<img src="${escapeAttribute(source)}" alt="${escapeAttribute(text)}" loading="lazy"${titleAttribute}>`;
    },
  },
});

const markdown = fs.readFileSync(markdownPath, 'utf8');
let html = marked.parse(markdown);
/* German pages live one directory deeper: docs/de/<slug>/ instead of docs/<slug>/. */
const imageRoot = pageLanguage === 'de'
  ? (currentSlug === 'home' ? '../images/' : '../../images/')
  : (currentSlug === 'home' ? 'images/' : '../images/');
html = html.replaceAll('src="../images/', `src="${imageRoot}`);
process.stdout.write(JSON.stringify({ html, headings }));
