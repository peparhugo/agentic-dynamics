#!/usr/bin/env node
import { buildSite } from './generator';
import { startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]';
}

async function main(argv: string[]): Promise<void> {
  const command = argv[0];
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  let contentDir: string | undefined;
  let outputDir: string | undefined;
  let templatesDir: string | undefined;
  let port: number | undefined;
  for (let index = 1; index < argv.length; index += 1) {
    const option = argv[index];
    const value = argv[index + 1];
    if ((option === '--content' || option === '--output' || option === '--templates' || option === '--port') && value) {
      if (option === '--content') contentDir = value;
      else if (option === '--output') outputDir = value;
      else if (option === '--templates') templatesDir = value;
      else {
        port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(usage());
      }
      index += 1;
    } else {
      throw new Error(usage());
    }
  }
  if (command === 'build') {
    if (port !== undefined) throw new Error(usage());
    const pages = await buildSite({ contentDir, outputDir, templatesDir });
    process.stdout.write(`Generated ${pages.length} page(s).\n`);
    return;
  }
  const server = await startDevServer({ contentDir, outputDir, templatesDir, port });
  process.stdout.write(`Serving on http://localhost:${server.port}\n`);
}

main(process.argv.slice(2)).catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
