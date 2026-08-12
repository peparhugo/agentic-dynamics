#!/usr/bin/env node

import path from 'node:path';
import { buildSite, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR } from './generator';
import { serve, DEFAULT_PORT, type ServeOptions } from './serve';
import { DEFAULT_TEMPLATE_DIR } from './templates';
import { loadConfig } from './config';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

export function parseArgs(argv: string[]): { ok: true; options: CliOptions } | { ok: false; error: string } {
  let contentDir = DEFAULT_CONTENT_DIR;
  let outputDir = DEFAULT_OUTPUT_DIR;
  let templatesDir = DEFAULT_TEMPLATE_DIR;
  let port: number | undefined = undefined;
  let incremental: boolean | undefined = undefined;
  let clean: boolean | undefined = undefined;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === '--content') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --content' };
      }
      contentDir = value;
      i += 1;
      continue;
    }

    if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
      continue;
    }

    if (arg === '--output') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --output' };
      }
      outputDir = value;
      i += 1;
      continue;
    }

    if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
      continue;
    }

    if (arg === '--templates') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --templates' };
      }
      templatesDir = value;
      i += 1;
      continue;
    }

    if (arg.startsWith('--templates=')) {
      templatesDir = arg.slice('--templates='.length);
      continue;
    }

    if (arg === '--port') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --port' };
      }
      const parsedPort = Number(value);
      if (!Number.isInteger(parsedPort) || parsedPort < 0 || parsedPort > 65535) {
        return { ok: false, error: `Invalid port: ${value}` };
      }
      port = parsedPort;
      i += 1;
      continue;
    }

    if (arg.startsWith('--port=')) {
      const value = arg.slice('--port='.length);
      const parsedPort = Number(value);
      if (!Number.isInteger(parsedPort) || parsedPort < 0 || parsedPort > 65535) {
        return { ok: false, error: `Invalid port: ${value}` };
      }
      port = parsedPort;
      continue;
    }

    if (arg === '--incremental') {
      incremental = true;
      continue;
    }

    if (arg === '--clean') {
      clean = true;
      continue;
    }

    if (arg === '-h' || arg === '--help') {
      return {
        ok: false,
        error: 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean]',
      };
    }

    return { ok: false, error: `Unknown option: ${arg}` };
  }

  if (!contentDir) return { ok: false, error: 'Content directory cannot be empty' };
  if (!outputDir) return { ok: false, error: 'Output directory cannot be empty' };
  if (!templatesDir) return { ok: false, error: 'Templates directory cannot be empty' };

  return {
    ok: true,
    options: {
      contentDir: path.resolve(contentDir),
      outputDir: path.resolve(outputDir),
      templatesDir: path.resolve(templatesDir),
      port,
      incremental,
      clean,
    },
  };
}

export function usage(): string {
  return 'Usage: ssg <command> [options]\n\nCommands:\n  build  Build the site\n  serve  Start a development server with live reload\n\nOptions:\n  --content <dir>     Content directory (default: content)\n  --output <dir>      Output directory (default: dist)\n  --templates <dir>   Templates directory (default: templates)\n  --port <number>     Port for the dev server (default: 3000)\n  --incremental       Only rebuild pages whose source or template changed\n  --clean             Ignore the cache and rebuild everything\n  -h, --help          Show this help';
}

export async function main(argv: string[]): Promise<void> {
  const command = argv[0];

  if (command === 'build') {
    const parsed = parseArgs(argv.slice(1));
    if (!parsed.ok) {
      console.error(parsed.error);
      process.exitCode = 1;
      return;
    }

    const { contentDir, outputDir, templatesDir } = parsed.options;
    const config = loadConfig();
    const result = await buildSite(contentDir, outputDir, {
      templatesDir,
      plugins: config?.plugins,
      port: parsed.options.port,
      incremental: parsed.options.incremental,
      clean: parsed.options.clean,
    });

    console.log(`Generated ${result.pages.length} page(s) into ${outputDir}`);
    if (result.stats) {
      console.log(
        `Build stats: ${result.stats.built} built, ${result.stats.skipped} skipped, ${result.stats.timeSaved} ms saved (${result.stats.time} ms total)`,
      );
    }
    for (const file of result.files) {
      console.log(`  ${file}`);
    }
    return;
  }

  if (command === 'serve') {
    const parsed = parseArgs(argv.slice(1));
    if (!parsed.ok) {
      console.error(parsed.error);
      process.exitCode = 1;
      return;
    }

    const config = loadConfig();

    const serveOptions: ServeOptions = {
      contentDir: parsed.options.contentDir,
      outputDir: parsed.options.outputDir,
      templatesDir: parsed.options.templatesDir,
      port: parsed.options.port ?? DEFAULT_PORT,
      plugins: config?.plugins,
    };

    await serve(serveOptions);
    return;
  }

  console.error(usage());
  process.exitCode = 1;
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((err: unknown) => {
    console.error(err instanceof Error ? err.message : String(err));
    process.exitCode = 1;
  });
}
