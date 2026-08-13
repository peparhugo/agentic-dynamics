#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { parseMarkdown } from './parser';
import { generatePageHTML, generateIndexHTML } from './generator';
import { TemplateEngine } from './template-engine';
import { serve } from './serve';

interface CliOptions {
  content: string;
  output: string;
  templates?: string;
  port?: number;
}

function parseArgs(): CliOptions {
  const args = process.argv.slice(2);
  const options: CliOptions = {
    content: './content',
    output: './dist',
    port: 3000,
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--content' && args[i + 1]) {
      options.content = args[i + 1];
      i++;
    } else if (args[i] === '--output' && args[i + 1]) {
      options.output = args[i + 1];
      i++;
    } else if (args[i] === '--templates' && args[i + 1]) {
      options.templates = args[i + 1];
      i++;
    } else if (args[i] === '--port' && args[i + 1]) {
      options.port = parseInt(args[i + 1], 10);
      i++;
    }
  }

  return options;
}

async function build(options: CliOptions): Promise<void> {
  const { content: contentDir, output: outputDir, templates: templatesDir } = options;

  if (!fs.existsSync(contentDir)) {
    console.error(`Error: Content directory "${contentDir}" does not exist`);
    process.exit(1);
  }

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  let templateEngine: TemplateEngine | undefined;
  if (templatesDir && fs.existsSync(templatesDir)) {
    templateEngine = new TemplateEngine({ templateDir: templatesDir });
  }

  const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.md'));

  if (files.length === 0) {
    console.warn(`Warning: No markdown files found in "${contentDir}"`);
  }

  const pages = [];

  for (const file of files) {
    const filePath = path.join(contentDir, file);
    const content = fs.readFileSync(filePath, 'utf-8');
    const slug = path.parse(file).name;

    try {
      const page = await parseMarkdown(content, slug);
      pages.push(page);

      const outputFile = path.join(outputDir, `${slug}.html`);
      const html = generatePageHTML(page, templateEngine);
      fs.writeFileSync(outputFile, html, 'utf-8');
      console.log(`✓ Generated ${outputFile}`);
    } catch (error) {
      console.error(`Error processing ${file}:`, error);
      process.exit(1);
    }
  }

  const indexFile = path.join(outputDir, 'index.html');
  const indexHtml = generateIndexHTML(pages);
  fs.writeFileSync(indexFile, indexHtml, 'utf-8');
  console.log(`✓ Generated ${indexFile}`);

  console.log(`\nBuild complete: ${pages.length} page${pages.length !== 1 ? 's' : ''} generated`);
}

const command = process.argv[2];

if (command === 'build' || !command) {
  const options = parseArgs();
  build(options).catch(error => {
    console.error('Build failed:', error);
    process.exit(1);
  });
} else if (command === 'serve') {
  const options = parseArgs();
  serve(options).catch(error => {
    console.error('Serve failed:', error);
    process.exit(1);
  });
} else {
  console.error(`Unknown command: ${command}`);
  console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
  console.error('       ssg serve [--content <dir>] [--output <dir>] [--port <port>]');
  process.exit(1);
}
