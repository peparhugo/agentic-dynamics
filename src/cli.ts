#!/usr/bin/env node

import { buildSite, BuildOptions } from './index';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

export async function run(argv: string[]): Promise<void> {
  if (argv[0] !== 'build') {
    throw new Error(usage());
  }

  const options: BuildOptions = {};
  for (let index = 1; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument !== '--content' && argument !== '--output' && argument !== '--templates') {
      throw new Error(`Unknown option: ${argument}\n${usage()}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${argument}\n${usage()}`);
    }
    if (argument === '--content') options.contentDir = value;
    if (argument === '--output') options.outputDir = value;
    if (argument === '--templates') options.templatesDir = value;
    index += 1;
  }

  const pages = await buildSite(options);
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`${message}\n`);
    process.exitCode = 1;
  });
}
