import fs from 'fs';
import path from 'path';

import { loadPlugins } from './config';
import { Page, Plugin } from './plugin';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';
import { renderIndex } from './render';
import { Post } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  /** Extra plugins appended after the built-in plugins. */
  plugins?: Plugin[];
  /** Directory searched for `ssg.config.ts`. Defaults to `process.cwd()`. */
  configDir?: string;
}

export interface BuildResult {
  posts: Post[];
  filesWritten: string[];
  outputDir: string;
}

function listMarkdownFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) {
    return files;
  }
  for (const entry of fs.readdirSync(dir)) {
    const fullPath = path.join(dir, entry);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      files.push(...listMarkdownFiles(fullPath));
    } else if (stat.isFile() && /\.md$/i.test(entry)) {
      files.push(fullPath);
    }
  }
  return files;
}

function slugForFile(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath);
  const withoutExtension = relative.replace(/\.md$/i, '');
  return withoutExtension.split(path.sep).join('/');
}

function sortPosts(posts: Post[]): void {
  posts.sort((a, b) => {
    const dateA = a.date ? Date.parse(a.date) : NaN;
    const dateB = b.date ? Date.parse(b.date) : NaN;
    if (!Number.isNaN(dateA) && !Number.isNaN(dateB) && dateA !== dateB) {
      return dateB - dateA;
    }
    if (Number.isNaN(dateA) && !Number.isNaN(dateB)) {
      return 1;
    }
    if (!Number.isNaN(dateA) && Number.isNaN(dateB)) {
      return -1;
    }
    return a.title.localeCompare(b.title);
  });
}

type LifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

function runHooksSync(plugins: Plugin[], method: LifecycleHook): void {
  for (const plugin of plugins) {
    const hook = plugin[method] as (() => unknown) | undefined;
    if (typeof hook !== 'function') {
      continue;
    }
    const result = hook.call(plugin);
    if (result != null && typeof (result as Promise<unknown>).then === 'function') {
      throw new Error(
        `Plugin "${plugin.name ?? 'unnamed'}" returned a Promise from "${method}". ` +
          'Asynchronous plugin hooks are not supported by the synchronous build pipeline.',
      );
    }
  }
}

function runFileHooksSync(plugins: Plugin[], page: Page): void {
  for (const plugin of plugins) {
    const hook = plugin.onFile as ((page: Page) => unknown) | undefined;
    if (typeof hook !== 'function') {
      continue;
    }
    const result = hook.call(plugin, page);
    if (result != null && typeof (result as Promise<unknown>).then === 'function') {
      throw new Error(
        `Plugin "${plugin.name ?? 'unnamed'}" returned a Promise from "onFile". ` +
          'Asynchronous plugin hooks are not supported by the synchronous build pipeline.',
      );
    }
  }
}

/**
 * Build a static site by running the plugin pipeline.
 *
 * The built-in `MarkdownPlugin` and `TemplatePlugin` always run first (in that
 * order), followed by any plugins passed via `options.plugins` and any plugins
 * declared in the project's `ssg.config.ts`.
 */
export function buildSite(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? path.join(process.cwd(), 'templates');
  const configDir = options.configDir ?? process.cwd();

  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    new TemplatePlugin(templatesDir),
    ...(options.plugins ?? []),
    ...loadPlugins(configDir),
  ];

  runHooksSync(plugins, 'onStart');
  runHooksSync(plugins, 'beforeBuild');

  const markdownFiles = listMarkdownFiles(contentDir);
  const pages: Page[] = markdownFiles.map((filePath) => {
    const slug = slugForFile(filePath, contentDir);
    const source = fs.readFileSync(filePath, 'utf-8');
    return {
      slug,
      title: '',
      date: undefined,
      tags: [],
      template: undefined,
      content: source,
      html: '',
    };
  });

  for (const page of pages) {
    runFileHooksSync(plugins, page);
  }

  sortPosts(pages);

  fs.mkdirSync(outputDir, { recursive: true });

  const filesWritten: string[] = [];

  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, renderIndex(pages));
  filesWritten.push(indexPath);

  for (const page of pages) {
    const pagePath = path.join(outputDir, `${page.slug}.html`);
    fs.mkdirSync(path.dirname(pagePath), { recursive: true });
    fs.writeFileSync(pagePath, page.rendered ?? '');
    filesWritten.push(pagePath);
  }

  runHooksSync(plugins, 'afterBuild');
  runHooksSync(plugins, 'onEnd');

  const posts: Post[] = pages.map((page) => ({
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    template: page.template,
    content: page.content,
    html: page.html,
  }));

  return { posts, filesWritten, outputDir };
}
