import { promises as fs } from "fs";
import path from "path";
import { PageData, BuildOptions } from "./types";
import { Plugin, runHook, runFilePipeline } from "./plugin";
import { createMarkdownPlugin } from "./plugins/markdown";
import { createTemplatePlugin } from "./plugins/template";

export { generatePageHtml, generateIndexHtml } from "./html-generator";
export { parseMarkdownFile } from "./plugins/markdown";

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

export async function build(options: BuildOptions): Promise<void> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);

  const plugins = getBuiltinPlugins();

  await runHook(plugins, "onStart", options);
  await runHook(plugins, "beforeBuild", options);

  await fs.mkdir(outputDir, { recursive: true });

  const files = await getMarkdownFiles(contentDir);
  const pages: PageData[] = [];

  for (const file of files) {
    let page: PageData = { path: file, frontmatter: {}, html: "" };
    page = await runFilePipeline(plugins, page, options);
    pages.push(page);

    const outPath = file.replace(/\.md$/, ".html");
    const fullOutPath = path.join(outputDir, outPath);
    const outDir = path.dirname(fullOutPath);
    await fs.mkdir(outDir, { recursive: true });
    await fs.writeFile(fullOutPath, page.html, "utf-8");
  }

  await runHook(plugins, "afterBuild", options, pages);
  await runHook(plugins, "onEnd", options);
}
