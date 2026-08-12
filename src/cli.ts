#!/usr/bin/env node
import { buildSite } from './ssg';

function usage(): never {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
  process.exit(1);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.shift() !== 'build') usage();
  let contentDir: string | undefined;
  let outputDir: string | undefined;
  while (args.length) {
    const option = args.shift();
    if (option !== '--content' && option !== '--output') usage();
    const value = args.shift();
    if (!value || value.startsWith('--')) usage();
    if (option === '--content') contentDir = value;
    else outputDir = value;
  }
  const pages = await buildSite({ contentDir, outputDir });
  console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
