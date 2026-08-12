#!/usr/bin/env node
import path from 'path';
import { SSG } from './engine';
import { createDevServerPlugin } from './plugins';
import { loadConfig } from './config';

export interface CliArgs {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  host: string;
  showHelp: boolean;
  command: string | undefined;
  incremental: boolean;
  clean: boolean;
}

const DEFAULT_PORT = 3000;
const DEFAULT_HOST = 'localhost';

const HELP = `Usage: ssg [command] [options]

Commands:
  build       Generate the site from markdown content (default)
  serve       Build the site and serve it with live reload (default port 3000)

Options:
  --content <dir>    Content directory containing markdown files (default: ./content)
  --output <dir>     Output directory for generated HTML (default: ./dist)
  --templates <dir>  Templates directory with .hbs templates, layouts and partials (default: ./templates)
  --port <number>    Port for the dev server (default: 3000)
  --host <host>      Host for the dev server (default: localhost)
  --incremental      Only rebuild pages whose source or template changed
  --clean            Force a full clean rebuild (ignores the cache)
  -h, --help         Show this help message
`;

export function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    contentDir: 'content',
    outputDir: 'dist',
    templatesDir: 'templates',
    port: DEFAULT_PORT,
    host: DEFAULT_HOST,
    showHelp: false,
    command: undefined,
    incremental: false,
    clean: false,
  };

  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];
    switch (arg) {
      case '-h':
      case '--help':
        args.showHelp = true;
        break;
      case 'build':
        args.command = 'build';
        break;
      case 'serve':
        args.command = 'serve';
        break;
      case '--incremental':
        args.incremental = true;
        break;
      case '--clean':
        args.clean = true;
        break;
      case '--content':
      case '--output':
      case '--templates':
      case '--port':
      case '--host': {
        const next = argv[i + 1];
        if (next === undefined || next.startsWith('-')) {
          throw new Error(`Option ${arg} requires a value`);
        }
        if (arg === '--content') args.contentDir = next;
        else if (arg === '--output') args.outputDir = next;
        else if (arg === '--templates') args.templatesDir = next;
        else if (arg === '--port') {
          const parsed = Number(next);
          if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
            throw new Error(`Option --port requires a valid port number`);
          }
          args.port = parsed;
        } else {
          args.host = next;
        }
        i += 1;
        break;
      }
      default:
        throw new Error(`Unknown option or command: ${arg}`);
    }
    i += 1;
  }

  return args;
}

export function run(argv: string[]): number | undefined {
  let args: CliArgs;
  try {
    args = parseArgs(argv);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    console.error(HELP);
    return 1;
  }

  if (args.showHelp) {
    process.stdout.write(HELP);
    return 0;
  }

  const contentDir = path.resolve(process.cwd(), args.contentDir);
  const outputDir = path.resolve(process.cwd(), args.outputDir);
  const templatesDir = path.resolve(process.cwd(), args.templatesDir);

  if (args.command === 'serve') {
    const config = loadConfig();
    const dev = createDevServerPlugin({ host: args.host, port: args.port });
    const engine = new SSG({
      options: { contentDir, outputDir, templatesDir },
      plugins: [...config.plugins, dev.plugin],
    });
    engine.start();
    try {
      const pages = engine.build();
      console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${outputDir}`);
    } catch (err) {
      console.error(`Initial build failed: ${(err as Error).message}`);
    }
    console.log(`Dev server running at http://${args.host}:${args.port}`);
    return undefined;
  }

  try {
    const config = loadConfig();
    const engine = new SSG({
      options: { contentDir, outputDir, templatesDir },
      plugins: config.plugins,
    });
    engine.start();
    const pages = engine.build({ incremental: args.incremental, clean: args.clean });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${outputDir}`);
    if (engine.lastBuildStats) {
      const s = engine.lastBuildStats;
      console.log(
        `Build stats: ${s.built} built, ${s.skipped} skipped, ${s.timeSavedMs}ms time saved`
      );
    }
    return 0;
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    return 1;
  }
}

if (require.main === module) {
  const code = run(process.argv.slice(2));
  if (code !== undefined) {
    process.exit(code);
  }
}
