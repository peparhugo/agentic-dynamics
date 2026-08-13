import { createHash } from 'node:crypto';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { BuildContext, CachedPage } from './types';

interface Manifest {
  version: 1;
  templateHash: string;
  pages: Record<string, CachedPage>;
}

async function filesIn(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const nested = await Promise.all(entries.map(async entry => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? filesIn(filename) : [filename];
  }));
  return nested.flat().sort((a, b) => a.localeCompare(b));
}

export function hash(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

async function templateHash(directory: string): Promise<string> {
  const digest = createHash('sha256');
  for (const filename of await filesIn(directory)) {
    if (!/\.hbs$/i.test(filename)) continue;
    digest.update(path.relative(directory, filename).split(path.sep).join('/'));
    digest.update('\0');
    digest.update(await fs.readFile(filename));
    digest.update('\0');
  }
  return digest.digest('hex');
}

function validManifest(value: unknown): value is Manifest {
  if (!value || typeof value !== 'object') return false;
  const manifest = value as Partial<Manifest>;
  return manifest.version === 1 && typeof manifest.templateHash === 'string'
    && !!manifest.pages && typeof manifest.pages === 'object';
}

export async function prepareCache(context: BuildContext, options: { cacheFile?: string; clean?: boolean }): Promise<void> {
  const filename = path.resolve(options.cacheFile ?? '.ssg-cache.json');
  if (options.clean) {
    await Promise.all([
      fs.rm(context.outputDir, { recursive: true, force: true }),
      fs.rm(filename, { force: true })
    ]);
  }

  let previous: Manifest | undefined;
  try {
    const parsed: unknown = JSON.parse(await fs.readFile(filename, 'utf8'));
    if (validManifest(parsed)) previous = parsed;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
  }

  context.cache = {
    filename,
    templateHash: await templateHash(context.templatesDir),
    previousTemplateHash: previous?.templateHash,
    entries: {},
    previousEntries: previous?.pages ?? {}
  };
}

function outputPathFor(context: BuildContext, sourceRelativePath: string): string | undefined {
  const outputRelativePath = sourceRelativePath.replace(/\.md$/i, '.html');
  const output = path.resolve(context.outputDir, outputRelativePath);
  const relative = path.relative(context.outputDir, output);
  return relative && !relative.startsWith('..') && !path.isAbsolute(relative) ? output : undefined;
}

export async function writeCache(context: BuildContext): Promise<void> {
  const cache = context.cache;
  if (!cache) return;

  for (const key of Object.keys(cache.previousEntries)) {
    if (cache.entries[key]) continue;
    const output = outputPathFor(context, key);
    if (output) await fs.rm(output, { force: true });
  }

  await fs.mkdir(path.dirname(cache.filename), { recursive: true });
  const manifest: Manifest = { version: 1, templateHash: cache.templateHash, pages: cache.entries };
  await fs.writeFile(cache.filename, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}
