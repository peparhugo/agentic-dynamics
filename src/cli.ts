#!/usr/bin/env node
import * as path from 'path';
import { build } from './ssg';
import { startDevServer, type ServeOptions } from './serve';
import type { BuildStats } from './types';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
  templateDir: string;
  incremental?: boolean;
  clean?: boolean;
}

export type ParseResult = CliOptions | ServeOptions | 'help' | 'invalid';

export function printHelp(): void {
  console.log(`Usage: ssg build [options] | ssg serve [options]

Generate a static site from Markdown files.

Commands:
  build             Build the site once into the output directory
  serve             Build and serve the site with live reload

Options:
  --content <dir>   Directory containing Markdown content (default: ./content)
  --output <dir>    Directory to write the generated HTML (default: ./dist)
  --templates <dir> Directory containing Handlebars templates (default: ./templates)
  --incremental     Only rebuild pages whose source or template changed
  --clean           Force a full rebuild, ignoring any cached build
  --port <number>   Port for the dev server (default: 3000)
  --help, -h        Show this help message
`);
}

function isValidPort(value: string): boolean {
  if (!/^\d+$/.test(value)) {
    return false;
  }
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

export function parseArgs(args: string[]): ParseResult {
  if (args.length === 0) {
    return 'invalid';
  }
  const subcommand = args[0];
  if (subcommand === '--help' || subcommand === '-h') {
    return 'help';
  }
  const options: CliOptions = {
    contentDir: 'content',
    outputDir: 'dist',
    templateDir: 'templates',
  };
  if (subcommand === 'serve') {
    const serveOptions: ServeOptions = { command: 'serve', ...options, port: 3000 };
    for (let i = 1; i < args.length; i++) {
      const arg = args[i];
      if (arg === '--help' || arg === '-h') {
        return 'help';
      }
      if (
        arg === '--content' ||
        arg === '--output' ||
        arg === '--templates' ||
        arg === '--port'
      ) {
        const value = args[i + 1];
        if (!value || value.startsWith('--')) {
          return 'invalid';
        }
        if (arg === '--content') {
          serveOptions.contentDir = value;
        } else if (arg === '--output') {
          serveOptions.outputDir = value;
        } else if (arg === '--templates') {
          serveOptions.templateDir = value;
        } else {
          if (!isValidPort(value)) {
            return 'invalid';
          }
          serveOptions.port = Number(value);
        }
        i += 1;
      } else {
        return 'invalid';
      }
    }
    return serveOptions;
  }
  if (subcommand !== 'build') {
    return 'invalid';
  }
  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') {
      return 'help';
    }
    if (arg === '--incremental') {
      options.incremental = true;
      continue;
    }
    if (arg === '--clean') {
      options.clean = true;
      continue;
    }
    if (arg === '--content' || arg === '--output' || arg === '--templates') {
      const value = args[i + 1];
      if (!value || value.startsWith('--')) {
        return 'invalid';
      }
      if (arg === '--content') {
        options.contentDir = value;
      } else if (arg === '--output') {
        options.outputDir = value;
      } else {
        options.templateDir = value;
      }
      i += 1;
    } else {
      return 'invalid';
    }
  }
  return options;
}

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv.slice(2));
  if (parsed === 'help') {
    printHelp();
    return;
  }
  if (parsed === 'invalid') {
    console.error('Invalid arguments. Run `ssg --help` for usage.');
    process.exitCode = 1;
    return;
  }
  if ('command' in parsed && parsed.command === 'serve') {
    try {
      const server = await startDevServer(parsed);
      console.log(`Serving ${path.resolve(parsed.outputDir)} at http://localhost:${server.port}`);
      console.log('Watching for changes...');
      const shutdown = (): void => {
        void server.close().then(() => process.exit(0));
      };
      process.on('SIGINT', shutdown);
      process.on('SIGTERM', shutdown);
      return;
    } catch (err) {
      console.error(`Dev server failed to start: ${(err as Error).message}`);
      process.exitCode = 1;
      return;
    }
  }
  try {
    const pages = await build({
      ...parsed,
      onStats: (stats) => printBuildStats(stats),
    });
    console.log(`Generated ${pages.length} page(s) in ${path.resolve(parsed.outputDir)}`);
  } catch (err) {
    console.error(`Build failed: ${(err as Error).message}`);
    process.exitCode = 1;
  }
}

function printBuildStats(stats: BuildStats): void {
  if (!stats.incremental) {
    return;
  }
  console.log(
    `Incremental build: ${stats.built} built, ${stats.skipped} skipped, saved ${stats.timeSavedMs}ms`
  );
}

if (require.main === module) {
  void main();
}
