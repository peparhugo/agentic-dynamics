#!/usr/bin/env node
import path from 'path';
import { buildSite } from './build';
import { startDevServer } from './serve';

export interface CliArgs {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  host: string;
  showHelp: boolean;
  command: string | undefined;
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
    startDevServer({
      contentDir,
      outputDir,
      templatesDir,
      host: args.host,
      port: args.port,
    });
    console.log(`Dev server running at http://${args.host}:${args.port}`);
    return undefined;
  }

  try {
    const pages = buildSite({ contentDir, outputDir, templatesDir });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${outputDir}`);
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
