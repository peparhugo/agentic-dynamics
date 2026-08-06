#!/usr/bin/env node
import { Command } from "commander";
import { join } from "node:path";
import { build } from "./build.js";
import { serve } from "./serve.js";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator")
  .option("-s, --source <dir>", "source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "output directory for generated HTML", "public")
  .option("--serve", "start a dev server with live reload")
  .option("-p, --port <number>", "dev server port", "3000")
  .action((opts) => {
    const source = join(process.cwd(), opts.source);
    const templates = join(process.cwd(), opts.templates);
    const output = join(process.cwd(), opts.output);
    const port = parseInt(opts.port, 10);

    if (opts.serve) {
      build({ source, templates, output });
      serve({ source, templates, output, port });
      return;
    }

    const site = build({ source, templates, output });
    const published = site.pages.filter((p) => !p.frontmatter.draft);
    console.log(`Built ${published.length} pages (${site.pages.length - published.length} drafts)`);
    console.log(`  Pages: ${published.length}`);
    console.log(`  Tags:  ${site.tags.size}`);
  });

program.parse();
