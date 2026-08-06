#!/usr/bin/env node
import { pathToFileURL } from 'node:url';
import { build } from './build.js';
import { serve } from './server.js';
import { DEFAULT_CONFIG, type SiteConfig } from './types.js';

const HELP = `sitegen - static site generator (Markdown + Handlebars)

Usage:
  sitegen build [options]   Build the site once
  sitegen serve [options]   Build, serve, watch, and live-reload

Options:
  -s, --source <dir>      Source directory of markdown files   (default: ${DEFAULT_CONFIG.sourceDir})
  -t, --templates <dir>   Handlebars template directory        (default: ${DEFAULT_CONFIG.templateDir})
  -o, --out <dir>         Output directory                     (default: ${DEFAULT_CONFIG.outDir})
      --title <text>      Site title                           (default: "${DEFAULT_CONFIG.title}")
      --description <t>   Site description
      --base-url <url>    Absolute base URL (RSS links)        (default: ${DEFAULT_CONFIG.baseUrl})
      --drafts            Include pages marked draft: true
      --clean             Remove the output directory before building
  -p, --port <n>          Dev server port (serve only)         (default: ${DEFAULT_CONFIG.port})
  -h, --help              Show this help
  -v, --version           Show version
`;

export interface ParsedArgs {
  command: 'build' | 'serve' | 'help' | 'version';
  config: SiteConfig;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const config: SiteConfig = { ...DEFAULT_CONFIG };
  let command: ParsedArgs['command'] | null = null;

  const takeValue = (flag: string, i: number): string => {
    const value = argv[i];
    if (value === undefined || value.startsWith('-')) {
      throw new Error(`Missing value for ${flag}`);
    }
    return value;
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case 'build':
      case 'serve':
        if (command) throw new Error(`Unexpected argument: ${arg}`);
        command = arg;
        break;
      case '-s':
      case '--source':
        config.sourceDir = takeValue(arg, ++i);
        break;
      case '-t':
      case '--templates':
        config.templateDir = takeValue(arg, ++i);
        break;
      case '-o':
      case '--out':
        config.outDir = takeValue(arg, ++i);
        break;
      case '--title':
        config.title = takeValue(arg, ++i);
        break;
      case '--description':
        config.description = takeValue(arg, ++i);
        break;
      case '--base-url':
        config.baseUrl = takeValue(arg, ++i).replace(/\/+$/, '');
        break;
      case '--drafts':
        config.includeDrafts = true;
        break;
      case '--clean':
        config.clean = true;
        break;
      case '-p':
      case '--port': {
        const port = Number(takeValue(arg, ++i));
        if (!Number.isInteger(port) || port < 0 || port > 65535) {
          throw new Error(`Invalid port: ${argv[i]}`);
        }
        config.port = port;
        break;
      }
      case '-h':
      case '--help':
        return { command: 'help', config };
      case '-v':
      case '--version':
        return { command: 'version', config };
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!command) throw new Error('Missing command: expected "build" or "serve"');
  return { command, config };
}

export async function main(argv: string[]): Promise<number> {
  let parsed: ParsedArgs;
  try {
    parsed = parseArgs(argv);
  } catch (err) {
    console.error(`Error: ${err instanceof Error ? err.message : err}\n`);
    console.error(HELP);
    return 2;
  }

  switch (parsed.command) {
    case 'help':
      console.log(HELP);
      return 0;
    case 'version': {
      const { createRequire } = await import('node:module');
      const pkg = createRequire(import.meta.url)('../package.json');
      console.log(pkg.version);
      return 0;
    }
    case 'build': {
      try {
        const start = Date.now();
        const result = await build(parsed.config);
        console.log(
          `Built ${result.pages.length} page(s), ${Object.keys(result.tags).length} tag(s) ` +
            `-> ${parsed.config.outDir} in ${Date.now() - start}ms`,
        );
        return 0;
      } catch (err) {
        console.error(`Build failed: ${err instanceof Error ? err.message : err}`);
        return 1;
      }
    }
    case 'serve': {
      try {
        await serve(parsed.config);
        return 0; // server keeps the event loop alive
      } catch (err) {
        console.error(`Server failed: ${err instanceof Error ? err.message : err}`);
        return 1;
      }
    }
  }
}

// Run only when invoked directly (not when imported by tests).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).then((code) => {
    if (code !== 0) process.exitCode = code;
  });
}
