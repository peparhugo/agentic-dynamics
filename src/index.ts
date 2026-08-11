import { promises as fs } from "fs";
import path from "path";
import matter from "gray-matter";
import yaml from "js-yaml";
import MarkdownIt from "markdown-it";
import { PageData, Frontmatter } from "./types";

const md = new MarkdownIt();

const matterOptions = {
  engines: {
    yaml: {
      parse: (input: string) => yaml.load(input, { schema: yaml.FAILSAFE_SCHEMA }) as Record<string, unknown>,
    },
  },
};

async function walkDir(
  dir: string,
  baseDir: string,
  results: string[]
): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const sortedEntries = entries
    .filter((e) => e.isFile() && e.name.endsWith(".md"))
    .sort((a, b) => a.name.localeCompare(b.name));

  for (const entry of sortedEntries) {
    results.push(path.relative(baseDir, path.join(dir, entry.name)));
  }

  const subdirs = entries
    .filter((e) => e.isDirectory())
    .sort((a, b) => a.name.localeCompare(b.name));

  for (const subdir of subdirs) {
    await walkDir(path.join(dir, subdir.name), baseDir, results);
  }

  return results;
}

export async function getMarkdownFiles(
  contentDir: string
): Promise<string[]> {
  const absDir = path.resolve(contentDir);
  try {
    await fs.access(absDir);
  } catch {
    throw new Error(`Content directory not found: ${absDir}`);
  }
  const files: string[] = [];
  await walkDir(absDir, absDir, files);
  return files.sort();
}

export async function parseMarkdownFile(
  contentDir: string,
  filePath: string
): Promise<PageData> {
  const absPath = path.join(contentDir, filePath);
  const raw = await fs.readFile(absPath, "utf-8");
  const { data, content } = matter(raw, matterOptions);
  const html = md.render(content);

  const frontmatter: Frontmatter = {};
  for (const [key, value] of Object.entries(data)) {
    frontmatter[key] = String(value ?? "");
  }

  return { path: filePath, frontmatter, html };
}

export function generatePageHtml(page: PageData): string {
  let title = page.frontmatter.title || page.path;
  const date = page.frontmatter.date
    ? `<p class="date">${page.frontmatter.date}</p>`
    : "";
  const tags = page.frontmatter.tags
    ? `<p class="tags">Tags: ${page.frontmatter.tags}</p>`
    : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
</head>
<body>
${date}
${tags}
${page.html}
</body>
</html>`;
}

export function generateIndexHtml(pages: PageData[]): string {
  const items = pages
    .map((page) => {
      const href = page.path.replace(/\.md$/, ".html");
      const title = page.frontmatter.title || page.path;
      const date = page.frontmatter.date
        ? `<span class="date">${page.frontmatter.date}</span>`
        : "";
      const tags = page.frontmatter.tags
        ? `<span class="tags">Tags: ${page.frontmatter.tags}</span>`
        : "";
      return `    <li>
      <a href="${href}">${title}</a>
      ${date}
      ${tags}
    </li>`;
    })
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Site Index</title>
</head>
<body>
<h1>Pages</h1>
<ul>
${items}
</ul>
</body>
</html>`;
}

export async function build(options: {
  contentDir: string;
  outputDir: string;
}): Promise<void> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);

  await fs.mkdir(outputDir, { recursive: true });

  const files = await getMarkdownFiles(contentDir);
  const pages: PageData[] = [];

  for (const file of files) {
    const page = await parseMarkdownFile(contentDir, file);
    pages.push(page);

    const outPath = file.replace(/\.md$/, ".html");
    const fullOutPath = path.join(outputDir, outPath);
    const outDir = path.dirname(fullOutPath);
    await fs.mkdir(outDir, { recursive: true });

    const pageHtml = generatePageHtml(page);
    await fs.writeFile(fullOutPath, pageHtml, "utf-8");
  }

  const indexHtml = generateIndexHtml(pages);
  await fs.writeFile(path.join(outputDir, "index.html"), indexHtml, "utf-8");
}
