#!/usr/bin/env node
import { buildSite } from './generator';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

async function main(argv: string[]): Promise<void> {
  if (argv[0] !== 'build') throw new Error(usage());
  let contentDir: string | undefined;
  let outputDir: string | undefined;
  let templatesDir: string | undefined;
  for (let index = 1; index < argv.length; index += 1) {
    const option = argv[index];
    const value = argv[index + 1];
    if ((option === '--content' || option === '--output' || option === '--templates') && value) {
      if (option === '--content') contentDir = value;
      else if (option === '--output') outputDir = value;
      else templatesDir = value;
      index += 1;
    } else {
      throw new Error(usage());
    }
  }
  const pages = await buildSite({ contentDir, outputDir, templatesDir });
  process.stdout.write(`Generated ${pages.length} page(s).\n`);
}

main(process.argv.slice(2)).catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
