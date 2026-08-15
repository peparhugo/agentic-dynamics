import fs from 'fs';
import path from 'path';
import { loadConfig } from './config';
import { SSGEngine, findMarkdownFiles } from './engine';
import { PluginContext } from './plugin';
import { Page } from './types';

export { findMarkdownFiles };

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

export function defaultTemplatesDir(): string {
  return path.resolve(process.cwd(), 'templates');
}

export function buildPage(contentDir: string, filename: string, templatesDir: string = defaultTemplatesDir()): Page {
  const engine = new SSGEngine(loadConfig(process.cwd()).plugins);
  const ctx: PluginContext = { contentDir, templatesDir };
  return engine.buildFile(contentDir, filename, ctx);
}

/**
 * Runs a full build pass through the plugin pipeline and writes the
 * resulting pages to `ctx.outputDir`. Shared by the one-shot `build()` below
 * and by the dev server, which reruns it on every watched file change using
 * the same engine instance (so plugins like the dev server's own reload
 * broadcast fire on every pass).
 */
export function buildAndWrite(engine: SSGEngine, ctx: PluginContext): Page[] {
  const outputDir = ctx.outputDir;
  if (!outputDir) {
    throw new Error('outputDir is required to write build output');
  }
  fs.mkdirSync(outputDir, { recursive: true });
  const pages = engine.runBuild(ctx);
  for (const page of pages) {
    fs.writeFileSync(path.join(outputDir, page.outputPath), page.html, 'utf-8');
  }
  return pages;
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir, templatesDir = defaultTemplatesDir() } = options;
  const engine = new SSGEngine(loadConfig(process.cwd()).plugins);
  const ctx: PluginContext = { contentDir, outputDir, templatesDir };
  const pages = buildAndWrite(engine, ctx);
  return { pages, outputDir };
}
