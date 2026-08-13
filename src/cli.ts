#!/usr/bin/env node
import { slugify, buildSite } from './build';
import type { SiteBuildResult } from './build';
import { startDevServer } from './server';

export { slugify, buildSite };
export type { SiteBuildResult };

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  incremental: boolean;
  clean: boolean;
}

const HELP = `ssg — a tiny static site generator

Usage:
  ssg build [options]
  ssg serve [options]

Commands:
  build    Build the site into the output directory
  serve    Start a dev server with live reload on localhost:3000

Options:
  --content <dir>    Directory containing Markdown files (default: ./content)
  --output <dir>     Directory where the site is written (default: ./dist)
  --templates <dir>  Directory containing Handlebars templates (default: ./templates)
  --port <number>    Port for the dev server (default: 3000, serve only)
  --incremental      Only rebuild pages whose source or template changed
  --clean            Ignore the build cache and rebuild every page
  --help             Show this help message
  --version          Show the version number
`;

const VERSION = '1.0.0';

export function parseArgs(argv: string[]): CliOptions {
  let command = '';
  let contentDir = 'content';
  let outputDir = 'dist';
  let templatesDir = 'templates';
  let port = 3000;
  let incremental = false;
  let clean = false;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--content') {
      contentDir = argv[++i];
    } else if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
    } else if (arg === '--output') {
      outputDir = argv[++i];
    } else if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
    } else if (arg === '--templates') {
      templatesDir = argv[++i];
    } else if (arg.startsWith('--templates=')) {
      templatesDir = arg.slice('--templates='.length);
    } else if (arg === '--port') {
      port = Number(argv[++i]);
    } else if (arg.startsWith('--port=')) {
      port = Number(arg.slice('--port='.length));
    } else if (arg === '--incremental') {
      incremental = true;
    } else if (arg === '--clean') {
      clean = true;
    } else if (arg === '--help' || arg === '-h') {
      command = 'help';
    } else if (arg === '--version' || arg === '-v') {
      command = 'version';
    } else {
      command = arg;
    }
  }

  if (!command) {
    command = 'build';
  }

  return { command, contentDir, outputDir, templatesDir, port, incremental, clean };
}

export function runCli(argv: string[]): number {
  const options = parseArgs(argv);

  if (options.command === 'help') {
    process.stdout.write(HELP);
    return 0;
  }
  if (options.command === 'version') {
    process.stdout.write(`${VERSION}\n`);
    return 0;
  }
  if (options.command === 'serve') {
    startDevServer({
      port: options.port,
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
    });
    return 0;
  }
  if (options.command !== 'build') {
    process.stderr.write(`ssg: unknown command "${options.command}"\n\nRun "ssg --help" for usage.\n`);
    return 1;
  }

  try {
    const result = buildSite(options.contentDir, options.outputDir, options.templatesDir, {
      incremental: options.incremental,
      clean: options.clean,
    });
    process.stdout.write(`Generated ${result.pages.length} page(s) in ${result.outputDir}\n`);
    if (options.incremental) {
      process.stdout.write(
        `Incremental build: ${result.stats.builtPages} built, ` +
          `${result.stats.skippedPages} skipped, ~${result.stats.timeSavedMs}ms saved\n`,
      );
    }
    return 0;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`ssg: build failed: ${message}\n`);
    return 1;
  }
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}
