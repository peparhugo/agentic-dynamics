#!/usr/bin/env node

import { Command } from "commander";
import { resolve } from "node:path";
import { buildSite } from "./build.js";
import { startServer } from "./server.js";
import type { SiteConfig } from "./types.js";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator CLI")
  .version("1.0.0")
  .option("-s, --source <dir>", "Source directory of Markdown files", "src")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated HTML", "dist")
  .option("--title <title>", "Site title", "My Site")
  .option("--description <desc>", "Site description", "A static site")
  .option("--base-url <url>", "Base URL for RSS feeds", "http://localhost:3000")
  .option("--language <lang>", "Site language", "en")
  .option("--serve", "Start a dev server with live reload")
  .option("-p, --port <port>", "Dev server port", "3000")
  .action(async (options) => {
    const srcDir = resolve(process.cwd(), options.source);
    const templateDir = resolve(process.cwd(), options.templates);
    const outDir = resolve(process.cwd(), options.output);
    const port = parseInt(options.port, 10);

    const config: SiteConfig = {
      title: options.title,
      description: options.description,
      baseUrl: options.baseUrl,
      language: options.language,
    };

    console.log(`[ssg] Building site...`);

    try {
      if (options.serve) {
        await buildSite(srcDir, templateDir, outDir, config, true);
        await startServer(srcDir, templateDir, outDir, config, port);
      } else {
        const ctx = await buildSite(srcDir, templateDir, outDir, config);
        const elapsed = ((Date.now() - ctx.startTime.getTime()) / 1000).toFixed(2);
        console.log(
          `[ssg] Built ${ctx.pages.length} pages and ${ctx.tags.size} tag pages in ${elapsed}s`,
        );
      }
    } catch (err) {
      console.error("[ssg] Error:", err);
      process.exit(1);
    }
  });

program.parse();
