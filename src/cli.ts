#!/usr/bin/env node

import { parseDirectory } from './parser';
import { generateSite } from './generator';
import { startServer } from './server';

function parseArgs(args: string[]): {
  content: string;
  output: string;
  templates: string;
  port: number;
} {
  let content = 'content';
  let output = 'dist';
  let templates = 'templates';
  let port = 3000;
  let i = 0;

  while (i < args.length) {
    if (args[i] === '--content' && i + 1 < args.length) {
      content = args[i + 1];
      i += 2;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      output = args[i + 1];
      i += 2;
    } else if (args[i] === '--templates' && i + 1 < args.length) {
      templates = args[i + 1];
      i += 2;
    } else if (args[i] === '--port' && i + 1 < args.length) {
      port = parseInt(args[i + 1], 10);
      i += 2;
    } else {
      i++;
    }
  }

  return { content, output, templates, port };
}

const command = process.argv[2];

if (command === 'build') {
  const { content, output, templates } = parseArgs(process.argv.slice(3));

  const pages = parseDirectory(content);
  generateSite(pages, output, templates);
  console.log(`Site generated in ${output} (${pages.length} pages)`);
} else if (command === 'serve') {
  const { content, output, templates, port } = parseArgs(process.argv.slice(3));

  const pages = parseDirectory(content);
  generateSite(pages, output, templates);
  console.log(`Site generated in ${output} (${pages.length} pages)`);

  startServer({ port, content, output, templates });
} else {
  console.log(
    'Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n' +
    '       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]'
  );
  process.exit(command ? 1 : 0);
}
