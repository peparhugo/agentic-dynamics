import { readdir, mkdir, writeFile, copyFile, stat } from "node:fs/promises";
import { join, extname, relative, dirname } from "node:path";
import { glob } from "./glob.js";
import { parseFile } from "./parser.js";
import { loadTemplates, renderMarkdown, renderTemplate, type LoadedTemplates } from "./renderer.js";
import { generateRss } from "./rss.js";
import type { Page, SiteConfig } from "./types.js";

async function ensureDir(dir: string): Promise<void> {
  await mkdir(dir, { recursive: true });
}

async function copyAssets(src: string, out: string): Promise<void> {
  const entries = await readdir(src, { withFileTypes: true }).catch(() => [] as never[]);
  for (const e of entries as { name: string; isDirectory(): boolean }[]) {
    const sp = join(src, e.name);
    const dp = join(out, e.name);
    if (e.isDirectory()) {
      if (e.name === "templates" || e.name.startsWith(".")) continue;
      await ensureDir(dp);
      await copyAssets(sp, dp);
    } else {
      if (e.name.endsWith(".md")) continue;
      await ensureDir(dirname(dp));
      await copyFile(sp, dp);
    }
  }
}

async function collectMarkdown(dir: string): Promise<string[]> {
  const files: string[] = [];
  const entries = await readdir(dir, { withFileTypes: true }).catch(() => [] as never[]);
  for (const e of entries as { name: string; isDirectory(): boolean }[]) {
    const full = join(dir, e.name);
    if (e.isDirectory()) {
      const nested = await collectMarkdown(full);
      files.push(...nested);
    } else if (e.name.endsWith(".md")) {
      files.push(full);
    }
  }
  return files;
}

function buildTagIndex(pages: Page[]): Map<string, Page[]> {
  const index = new Map<string, Page[]>();
  for (const page of pages) {
    const tags = page.frontmatter.tags ?? [];
    for (const tag of tags) {
      const list = index.get(tag) ?? [];
      list.push(page);
      index.set(tag, list);
    }
  }
  return index;
}

export async function generate(config: SiteConfig): Promise<void> {
  await ensureDir(config.out);

  const templates = await loadTemplates(config.tmpl);

  const mdFiles = await collectMarkdown(config.src);
  const pages: Page[] = [];

  for (const f of mdFiles) {
    const page = await parseFile(f);
    if (!page) continue;
    page.html = renderMarkdown(page.content);
    pages.push(page);
  }

  const published = pages.filter((p) => !p.frontmatter.draft).sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  const postPagesSub = ensureDir(join(config.out, "posts"));
  const tagDirSub = ensureDir(join(config.out, "tags"));

  const pageJobs = pages.map(async (page) => {
    const html = renderTemplate(templates, "post", {
      title: page.frontmatter.title,
      date: page.frontmatter.date ?? "",
      tags: page.frontmatter.tags ?? [],
      content: page.html,
      site: config,
      pages: published,
      page,
    });
    await writeFile(join(config.out, `${page.slug}.html`), html, "utf-8");
  });

  const indexJob = writeFile(
    join(config.out, "index.html"),
    renderTemplate(templates, "index", {
      title: config.title,
      pages: published,
      site: config,
    }),
    "utf-8",
  );

  const tagIndex = buildTagIndex(published);
  const tagJobs = [...tagIndex.entries()].map(async ([tag, taggedPages]) => {
    const html = renderTemplate(templates, "tag", {
      tag,
      pages: taggedPages,
      site: config,
      allTags: [...tagIndex.keys()],
    });
    await writeFile(join(config.out, "tags", `${tag}.html`), html, "utf-8");
  });

  const rssJob = generateRss(published, config);
  const assetsJob = copyAssets(config.src, config.out);

  await Promise.all([...pageJobs, indexJob, ...tagJobs, rssJob, assetsJob, postPagesSub, tagDirSub]);
}
