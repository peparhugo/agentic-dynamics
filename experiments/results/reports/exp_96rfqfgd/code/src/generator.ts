import { mkdir, writeFile, readFile, readdir, cp } from 'node:fs/promises';
import { join, dirname, extname, basename } from 'node:path';
import Handlebars from 'handlebars';
import type { Page, SiteConfig, TemplateContext } from './types.js';

export async function generateSite(
  pages: Page[],
  config: SiteConfig,
): Promise<void> {
  await mkdir(config.outputDir, { recursive: true });

  const partialsDir = join(config.templateDir, 'partials');
  try {
    const partialFiles = await readdir(partialsDir);
    for (const file of partialFiles) {
      const ext = extname(file);
      if (ext === '.hbs' || ext === '.handlebars') {
        const name = basename(file, ext);
        const content = await readFile(join(partialsDir, file), 'utf-8');
        Handlebars.registerPartial(name, content);
      }
    }
  } catch {
    // partials directory may not exist
  }

  const layoutSrc = await readFile(
    join(config.templateDir, 'layout.hbs'),
    'utf-8',
  );
  const layoutTemplate = Handlebars.compile(layoutSrc);

  const published = pages
    .filter((p) => !p.frontmatter.draft)
    .sort(sortByDate);

  const site = {
    title: config.siteTitle,
    description: config.siteDescription,
    url: config.siteUrl,
  };

  // render individual pages
  try {
    const pageSrc = await readFile(
      join(config.templateDir, 'page.hbs'),
      'utf-8',
    );
    const pageTemplate = Handlebars.compile(pageSrc);

    for (const page of published) {
      const body = pageTemplate(buildCtx({ page, pages: published, site }));
      const html = layoutTemplate(buildCtx({ body, page, pages: published, site }));
      const outPath = join(config.outputDir, page.url.replace(/^\//, ''));
      await mkdir(dirname(outPath), { recursive: true });
      await writeFile(outPath, html);
    }
  } catch {
    // page template is optional
  }

  // render index
  try {
    const indexSrc = await readFile(
      join(config.templateDir, 'index.hbs'),
      'utf-8',
    );
    const indexTemplate = Handlebars.compile(indexSrc);
    const indexBody = indexTemplate(buildCtx({ pages: published, site }));
    const indexHtml = layoutTemplate(
      buildCtx({
        body: indexBody,
        page: {
          path: '',
          frontmatter: { title: site.title || 'Home' },
          content: '',
          html: '',
          url: '/index.html',
        },
        pages: published,
        site,
      }),
    );
    await writeFile(join(config.outputDir, 'index.html'), indexHtml);
  } catch {
    // index template is optional
  }

  // render tag pages
  const tagMap = new Map<string, Page[]>();
  for (const page of published) {
    if (page.frontmatter.tags) {
      for (const tag of page.frontmatter.tags) {
        const list = tagMap.get(tag) || [];
        list.push(page);
        tagMap.set(tag, list);
      }
    }
  }

  if (tagMap.size > 0) {
    const tagsDir = join(config.outputDir, 'tags');
    await mkdir(tagsDir, { recursive: true });

    try {
      const tagSrc = await readFile(
        join(config.templateDir, 'tag.hbs'),
        'utf-8',
      );
      const tagTemplate = Handlebars.compile(tagSrc);

      for (const [tag, tagPages] of tagMap) {
        const tagBody = tagTemplate(
          buildCtx({ tag, pages: tagPages, site }),
        );
        const tagHtml = layoutTemplate(
          buildCtx({
            body: tagBody,
            page: {
              path: '',
              frontmatter: { title: `Tag: ${tag}` },
              content: '',
              html: '',
              url: `/tags/${tag}.html`,
            },
            pages: published,
            site,
          }),
        );
        await writeFile(join(tagsDir, `${tag}.html`), tagHtml);
      }
    } catch {
      // tag template is optional
    }
  }

  // RSS feed
  if (config.siteUrl) {
    const rss = generateRSS(published, config);
    await writeFile(join(config.outputDir, 'feed.xml'), rss);
  }

  // copy static assets from source (non-.md files)
  await copyAssets(config.sourceDir, config.outputDir);
}

function sortByDate(a: Page, b: Page): number {
  const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
  const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
  return db - da;
}

function buildCtx(overrides: Partial<TemplateContext>): TemplateContext {
  return {
    pages: [],
    site: {},
    ...overrides,
  };
}

function generateRSS(pages: Page[], config: SiteConfig): string {
  const items = pages
    .slice(0, 20)
    .map((p) => {
      const date = p.frontmatter.date
        ? new Date(p.frontmatter.date).toUTCString()
        : new Date().toUTCString();
      return `<item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${config.siteUrl}${p.url}</link>
      <guid>${config.siteUrl}${p.url}</guid>
      <pubDate>${date}</pubDate>
      <description>${escapeXml(p.html.substring(0, 500))}</description>
    </item>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle || 'Site')}</title>
    <link>${config.siteUrl}</link>
    <description>${escapeXml(config.siteDescription || '')}</description>
    <atom:link href="${config.siteUrl}/feed.xml" rel="self" type="application/rss+xml"/>
    ${items}
  </channel>
</rss>`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

async function copyAssets(
  sourceDir: string,
  outputDir: string,
): Promise<void> {
  try {
    const entries = await readdir(sourceDir, { withFileTypes: true });
    for (const entry of entries) {
      const srcPath = join(sourceDir, entry.name);
      if (entry.isDirectory()) {
        const destDir = join(outputDir, entry.name);
        await mkdir(destDir, { recursive: true });
        await copyAssets(srcPath, destDir);
      } else if (!entry.name.endsWith('.md')) {
        await cp(srcPath, join(outputDir, entry.name));
      }
    }
  } catch {
    // source directory may not have assets
  }
}
