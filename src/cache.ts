import { createHash } from 'node:crypto';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin, PluginPage } from './plugin';

export const CACHE_VERSION = 1;

export interface CachedPage extends PluginPage {
  sourceHash: string;
  renderHash: string;
  buildTimeMs: number;
}

export interface CacheManifest {
  version: number;
  contentDir: string;
  outputDir: string;
  pages: Record<string, CachedPage>;
}

export function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

export async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const manifest = JSON.parse(await fs.readFile(file, 'utf8')) as Partial<CacheManifest> | null;
    return manifest?.version === CACHE_VERSION
      && typeof manifest.contentDir === 'string'
      && typeof manifest.outputDir === 'string'
      && typeof manifest.pages === 'object'
      && manifest.pages !== null
      ? manifest as CacheManifest
      : undefined;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

export async function writeManifest(file: string, manifest: CacheManifest): Promise<void> {
  await fs.writeFile(file, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}

async function fileHash(file: string): Promise<string> {
  try {
    return hash(await fs.readFile(file, 'utf8'));
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return 'missing';
    throw error;
  }
}

async function partialHashes(directory: string, root = directory): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const values = await Promise.all(entries.map(async (entry): Promise<string[]> => {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) return partialHashes(file, root);
    if (!entry.isFile() || path.extname(entry.name).toLowerCase() !== '.hbs') return [];
    return [`${path.relative(root, file)}:${await fileHash(file)}`];
  }));
  return values.flat().sort();
}

function templateFile(directory: string, value: unknown, fallback: string): string | undefined {
  if (value === false) return undefined;
  const name = typeof value === 'string' && value.trim() ? value.trim() : fallback;
  const file = path.resolve(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
  const relative = path.relative(directory, file);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative))
    ? file
    : undefined;
}

export async function pageRenderHash(page: Pick<PluginPage, 'data'>, templatesDir: string, plugins: Plugin[]): Promise<string> {
  const template = templateFile(templatesDir, page.data.template, 'default');
  const layout = templateFile(path.join(templatesDir, 'layouts'), page.data.layout, 'default');
  const dependencies = await Promise.all([template, layout].filter((file): file is string => Boolean(file)).map(async (file) => (
    `${path.relative(templatesDir, file)}:${await fileHash(file)}`
  )));
  dependencies.push(...await partialHashes(path.join(templatesDir, 'partials')));
  const pluginHash = plugins.map((plugin) => [
    plugin.name ?? '',
    plugin.onStart,
    plugin.beforeBuild,
    plugin.onFile,
    plugin.afterBuild,
    plugin.onEnd,
  ].map(String).join('|')).join('|');
  return hash(`${dependencies.sort().join('|')}|${pluginHash}`);
}
