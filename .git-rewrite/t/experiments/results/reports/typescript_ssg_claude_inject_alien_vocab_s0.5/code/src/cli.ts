#!/usr/bin/env node
import { buildSite } from './build.js';
import { startDevServer } from './server.js';
import { DEFAULT_CONFIG, type SiteConfig } from './types.js';

export interface CliOptions {
  command: 'build' | 'serve' | 'help';
  config: SiteConfig;
  port: number;
}

export class CliError extends Error {}

const FLAG_ALIASES: Record<string, string> = {
  '-s': '--source',
  '-t': '--templates',
  '-o': '--out',
  '-p': '--port',
  '-d': '--drafts',
  '-h': '--help',
};

/** Parse argv (without node/script prefix) into structured CLI options. */
export function parseArgs(argv: string[]): CliOptions {
  const config: SiteConfig = { ...DEFAULT_CONFIG };
  let command: CliOptions['command'] | null = null;
  let port = 3000;

  const takesValue = new Set([
    '--source',
    '--templates',
    '--out',
    '--port',
    '--base-url',
    '--title',
    '--description',
  ]);

  for (let i = 0; i < argv.length; i++) {
    let arg = argv[i];
    let inlineValue: string | undefined;
    if (arg.startsWith('--') && arg.includes('=')) {
      const eq = arg.indexOf('=');
      inlineValue = arg.slice(eq + 1);
      arg = arg.slice(0, eq);
    }
    arg = FLAG_ALIASES[arg] ?? arg;

    if (!arg.startsWith('-')) {
      if (command) throw new CliError(`Unexpected argument: "${arg}"`);
      if (arg !== 'build' && arg !== 'serve' && arg !== 'help') {
        throw new CliError(`Unknown command: "${arg}"`);
      }
      command = arg;
      continue;
    }

    if (arg === '--help') {
      command = 'help';
      continue;
    }
    if (arg === '--drafts') {
      config.includeDrafts = true;
      continue;
    }
    if (!takesValue.has(arg)) throw new CliError(`Unknown flag: "${arg}"`);

    const value = inlineValue ?? argv[++i];
    if (value == null) throw new CliError(`Flag ${arg} requires a value`);

    switch (arg) {
      case '--source':
        config.sourceDir = value;
        break;
      case '--templates':
        config.templateDir = value;
        break;
      case '--out':
        config.outDir = value;
        break;
      case '--base-url':
        config.baseUrl = value;
        break;
      case '--title':
        config.title = value;
        break;
      case '--description':
        config.description = value;
        break;
      case '--port': {
        port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
          throw new CliError(`Invalid port: "${value}"`);
        }
        break;
      }
    }
  }

  return { command: command ?? 'help', config, port };
}

export const HELP = `sprout — static site generator

Usage:
  sprout build [options]    Build the site once
  sprout serve [options]    Build, serve, watch, and live-reload

Options:
  -s, --source <dir>      Markdown source directory   (default: content)
  -t, --templates <dir>   Handlebars template dir     (default: templates)
  -o, --out <dir>         Output directory            (default: dist-site)
  -p, --port <n>          Dev server port             (default: 3000)
  -d, --drafts            Include draft: true pages
      --base-url <url>    Site base URL for RSS links
      --title <str>       Site title
      --description <str> Site description
  -h, --help              Show this help
`;

export async function main(argv = process.argv.slice(2)): Promise<number> {
  let options: CliOptions;
  try {
    options = parseArgs(argv);
  } catch (err) {
    if (err instanceof CliError) {
      console.error(`Error: ${err.message}\n\n${HELP}`);
      return 1;
    }
    throw err;
  }

  if (options.command === 'help') {
    console.log(HELP);
    return 0;
  }

  if (options.command === 'build') {
    const started = Date.now();
    const result = await buildSite(options.config);
    console.log(
      `[sprout] built ${result.pages.length} pages, ${result.tagPages.length} tag pages, ` +
        `feed.xml -> ${options.config.outDir} (${Date.now() - started}ms)`,
    );
    return 0;
  }

  await startDevServer(options.config, options.port);
  return 0;
}

// Run when invoked directly (not when imported by tests).
const isDirect = process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop()!);
if (isDirect) {
  main().then(
    (code) => {
      if (code !== 0) process.exitCode = code;
    },
    (err) => {
      console.error(`[sprout] fatal: ${err?.message ?? err}`);
      process.exitCode = 1;
    },
  );
}
