import { promises as fs } from "fs";
import path from "path";
import { PageData, BuildOptions, BuildStats } from "./types";
import { Plugin, runHook, runFilePipeline } from "./plugin";
import { createMarkdownPlugin } from "./plugins/markdown";
import { createTemplatePlugin } from "./plugins/template";
import { BuildCache, hashContent, hashDirectory } from "./cache";

export { generatePageHtml, generateIndexHtml } from "./html-generator";
export { parseMarkdownFile } from "./plugins/markdown";
export { BuildStats } from "./types";

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

function getBuiltinPlugins(): Plugin[] {
  return [
    createMarkdownPlugin(),
    createTemplatePlugin(),
  ];
}

export async function build(options: BuildOptions): Promise<BuildStats> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);

  const plugins = getBuiltinPlugins();

  const cache = new BuildCache(outputDir);
  const incremental = options.incremental === true;

  let templatesHash = "";

  if (incremental) {
    await fs.mkdir(outputDir, { recursive: true });
    await cache.load();

    if (options.clean) {
      cache.clear();
    }

    const templatesDir = options.templatesDir
      ? path.resolve(options.templatesDir)
      : path.resolve("templates");
    templatesHash = await hashDirectory(templatesDir);
    cache.setTemplatesHash(templatesHash);
  }

  await runHook(plugins, "onStart", options);
  await runHook(plugins, "beforeBuild", options);

  await fs.mkdir(outputDir, { recursive: true });

  const files = await getMarkdownFiles(contentDir);
  const pages: PageData[] = [];

  let pagesBuilt = 0;
  let pagesSkipped = 0;
  const perPageTimeMs = 50;

  for (const file of files) {
    const outPath = file.replace(/\.md$/, ".html");
    const fullOutPath = path.join(outputDir, outPath);

    if (incremental) {
      const absSourcePath = path.join(contentDir, file);
      const sourceContent = await fs.readFile(absSourcePath, "utf-8");
      const sourceHash = hashContent(sourceContent);

      if (!cache.isChanged(file, sourceHash, templatesHash)) {
        const entry = cache.getEntry(file)!;
        const cachedPage: PageData = {
          path: file,
          frontmatter: entry.frontmatter,
          html: entry.html,
        };
        pages.push(cachedPage);

        const outDir = path.dirname(fullOutPath);
        await fs.mkdir(outDir, { recursive: true });
        await fs.writeFile(fullOutPath, cachedPage.html, "utf-8");
        pagesSkipped++;
        continue;
      }

      let page: PageData = { path: file, frontmatter: {}, html: "" };
      page = await runFilePipeline(plugins, page, options);
      pages.push(page);

      cache.setEntry(file, {
        sourceHash,
        templatesHash,
        frontmatter: page.frontmatter,
        html: page.html,
      });

      const outDir = path.dirname(fullOutPath);
      await fs.mkdir(outDir, { recursive: true });
      await fs.writeFile(fullOutPath, page.html, "utf-8");
      pagesBuilt++;
    } else {
      let page: PageData = { path: file, frontmatter: {}, html: "" };
      page = await runFilePipeline(plugins, page, options);
      pages.push(page);

      const outDir = path.dirname(fullOutPath);
      await fs.mkdir(outDir, { recursive: true });
      await fs.writeFile(fullOutPath, page.html, "utf-8");
      pagesBuilt++;
    }
  }

  if (incremental) {
    await cache.save();
  }

  await runHook(plugins, "afterBuild", options, pages);
  await runHook(plugins, "onEnd", options);

  const stats: BuildStats = {
    pagesBuilt,
    pagesSkipped,
    timeSavedMs: pagesSkipped * perPageTimeMs,
  };

  return stats;
}
