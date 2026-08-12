#!/usr/bin/env node

import path from 'node:path';
import { buildSite, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR } from './generator';
import { DEFAULT_TEMPLATE_DIR } from './templates';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export function parseArgs(argv: string[]): { ok: true; options: CliOptions } | { ok: false; error: string } {
  let contentDir = DEFAULT_CONTENT_DIR;
  let outputDir = DEFAULT_OUTPUT_DIR;
  let templatesDir = DEFAULT_TEMPLATE_DIR;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === '--content') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --content' };
      }
      contentDir = value;
      i += 1;
      continue;
    }

    if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
      continue;
    }

    if (arg === '--output') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --output' };
      }
      outputDir = value;
      i += 1;
      continue;
    }

    if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
      continue;
    }

    if (arg === '--templates') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        return { ok: false, error: 'Missing value for --templates' };
      }
      templatesDir = value;
      i += 1;
      continue;
    }

    if (arg.startsWith('--templates=')) {
      templatesDir = arg.slice('--templates='.length);
      continue;
    }

    if (arg === '-h' || arg === '--help') {
      return {
        ok: false,
        error: 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]',
      };
    }

    return { ok: false, error: `Unknown option: ${arg}` };
  }

  if (!contentDir) return { ok: false, error: 'Content directory cannot be empty' };
  if (!outputDir) return { ok: false, error: 'Output directory cannot be empty' };
  if (!templatesDir) return { ok: false, error: 'Templates directory cannot be empty' };

  return {
    ok: true,
    options: {
      contentDir: path.resolve(contentDir),
      outputDir: path.resolve(outputDir),
      templatesDir: path.resolve(templatesDir),
    },
  };
}

export async function main(argv: string[]): Promise<void> {
  const command = argv[0];
  if (command !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
    process.exitCode = 1;
    return;
  }

  const parsed = parseArgs(argv.slice(1));
  if (!parsed.ok) {
    console.error(parsed.error);
    process.exitCode = 1;
    return;
  }

  const { contentDir, outputDir, templatesDir } = parsed.options;
  const result = await buildSite(contentDir, outputDir, { templatesDir });

  console.log(`Generated ${result.pages.length} page(s) into ${outputDir}`);
  for (const file of result.files) {
    console.log(`  ${file}`);
  }
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((err: unknown) => {
    console.error(err instanceof Error ? err.message : String(err));
    process.exitCode = 1;
  });
}
