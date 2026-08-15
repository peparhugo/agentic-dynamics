#!/usr/bin/env node
import { buildSite } from './generator';
import { serveSite } from './dev-server';

function usage(): void {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  console.error('       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]');
}

export async function main(args: string[] = process.argv.slice(2)): Promise<void> {
  if (args[0] !== 'build' && args[0] !== 'serve') {
    usage();
    process.exitCode = 1;
    return;
  }
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number } = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    if (option !== '--content' && option !== '--output' && option !== '--templates'
      && (option !== '--port' || args[0] !== 'serve')) {
      usage(); process.exitCode = 1; return;
    }
    const value = args[++index];
    if (!value) { usage(); process.exitCode = 1; return; }
    if (option === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 0 || port > 65535) { usage(); process.exitCode = 1; return; }
      options.port = port;
    } else if (option === '--content') options.contentDir = value;
    else if (option === '--output') options.outputDir = value;
    else options.templatesDir = value;
  }
  if (args[0] === 'serve') await serveSite(options);
  else await buildSite(options);
}

if (require.main === module) {
  main().catch((error: unknown) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
}
