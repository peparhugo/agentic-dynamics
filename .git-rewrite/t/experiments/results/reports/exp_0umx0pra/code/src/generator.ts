import fs from 'fs';
import path from 'path';
import { SiteConfig, PageData } from './types';
import { parseMarkdownFile } from './parser';
import { renderPage, renderTagPage, setupHandlebars } from './renderer';

export async function generateSite(config: SiteConfig): Promise<PageData[]> {
  setupHandlebars(config);

  const pages = collectPages(config);

  const publishablePages = config.includeDrafts
    ? pages
    : pages.filter((p) => !p.isDraft);

  if (fs.existsSync(config.outputDir)) {
    fs.rmSync(config.outputDir, { recursive: true });
  }
  fs.mkdirSync(config.outputDir, { recursive: true });

  for (const page of publishablePages) {
    const html = renderPage(page, pages, config);
    const outFile = path.join(config.outputDir, page.outputPath);
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, html);
  }

  generateTagPages(pages, config);
  generateRssFeed(publishablePages, config);
  copyStaticAssets(config);

  return pages;
}

function collectPages(config: SiteConfig): PageData[] {
  const pages: PageData[] = [];
  walkDir(config.sourceDir, (filePath) => {
    if (filePath.endsWith('.md')) {
      pages.push(parseMarkdownFile(filePath, config.sourceDir));
    }
  });
  return pages;
}

export function walkDir(
  dir: string,
  callback: (filePath: string) => void
): void {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkDir(fullPath, callback);
    } else {
      callback(fullPath);
    }
  }
}

function generateTagPages(pages: PageData[], config: SiteConfig): void {
  const tagMap = new Map<string, PageData[]>();

  for (const page of pages) {
    if (page.isDraft && !config.includeDrafts) continue;
    for (const tag of page.tags) {
      if (!tagMap.has(tag)) tagMap.set(tag, []);
      tagMap.get(tag)!.push(page);
    }
  }

  for (const [tag, taggedPages] of tagMap) {
    const html = renderTagPage(tag, taggedPages, pages, config);
    const outDir = path.join(config.outputDir, 'tags', tag);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'index.html'), html);
  }
}

function generateRssFeed(pages: PageData[], config: SiteConfig): void {
  const posts = pages
    .filter((p) => !p.isDraft && p.frontmatter.date)
    .sort(
      (a, b) =>
        new Date(b.frontmatter.date!).getTime() -
        new Date(a.frontmatter.date!).getTime()
    );

  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(config.siteUrl)}</link>
    <description>${escapeXml(config.siteTitle)} RSS Feed</description>
    <atom:link href="${escapeXml(config.siteUrl)}/feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
`;

  for (const page of posts) {
    const url = `${config.siteUrl}${page.url}`;
    xml += `    <item>
      <title>${escapeXml(page.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid>${escapeXml(url)}</guid>
      <pubDate>${new Date(page.frontmatter.date!).toUTCString()}</pubDate>
      <description>${escapeXml(page.html.slice(0, 500))}</description>
    </item>
`;
  }

  xml += `  </channel>
</rss>`;

  fs.writeFileSync(path.join(config.outputDir, 'feed.xml'), xml);
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function copyStaticAssets(config: SiteConfig): void {
  walkDir(config.sourceDir, (filePath) => {
    if (!filePath.endsWith('.md')) {
      const relativePath = path.relative(config.sourceDir, filePath);
      const outPath = path.join(config.outputDir, relativePath);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.copyFileSync(filePath, outPath);
    }
  });
}
