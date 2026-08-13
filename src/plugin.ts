import { mkdir, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
}

export interface BuildPage extends Page {
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
}

export interface BuildContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: BuildPage[];
}

export interface Plugin {
  onStart?(context: BuildContext): Promise<void> | void;
  beforeBuild?(context: BuildContext): Promise<void> | void;
  afterBuild?(context: BuildContext): Promise<void> | void;
  onFile?(page: BuildPage, context: BuildContext): Promise<void> | void;
  onEnd?(context: BuildContext): Promise<void> | void;
}

export function createBuildContext(options: BuildOptions = {}): BuildContext {
  return {
    options,
    contentDir: resolve(options.contentDir ?? 'content'),
    outputDir: resolve(options.outputDir ?? 'dist'),
    templatesDir: resolve(options.templatesDir ?? 'templates'),
    pages: [],
  };
}

export async function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext, page?: BuildPage): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    if (hook === 'onFile') await (handler as NonNullable<Plugin['onFile']>)(page!, context);
    else await (handler as Exclude<Plugin[keyof Plugin], undefined>)(context);
  }
}

export async function resetOutput(context: BuildContext): Promise<void> {
  await rm(context.outputDir, { recursive: true, force: true });
  await mkdir(context.outputDir, { recursive: true });
}

export async function writeIndex(context: BuildContext): Promise<void> {
  const links = context.pages.map((page) => `      <li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a></li>`).join('\n');
  await writeFile(join(context.outputDir, 'index.html'), document('Index', `    <h1>Pages</h1>\n    <ul>\n${links}\n    </ul>`));
}

export const escapeHtml = (value: string): string => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

export function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n  <main>\n${body}\n  </main>\n</body>\n</html>\n`;
}
