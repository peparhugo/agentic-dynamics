#!/usr/bin/env node
import { Command } from "commander";
import path from "node:path";
import type { SiteConfig } from "./types.js";
import { generateSite } from "./generator.js";
import { generateRss } from "./rss.js";
import { createServer } from "node:http";
import { watchAndServe } from "./watcher.js";

const program = new Command();

program
  .name("staticsmith")
  .description("A high-throughput static site generator")
  .version("1.0.0");

program
  .command("build")
  .description("Build the site")
  .requiredOption("-s, --source <dir>", "Source directory of markdown files", "content")
  .requiredOption("-t, --templates <dir>", "Template directory with Handlebars files", "templates")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML", "dist")
  .option("--title <title>", "Site title", "My Site")
  .option("--url <url>", "Site URL", "https://example.com")
  .option("--base-url <base>", "Base URL path", "/")
  .action(async (options) => {
    const config: SiteConfig = {
      sourceDir: path.resolve(options.source),
      templateDir: path.resolve(options.templates),
      outputDir: path.resolve(options.output),
      siteTitle: options.title,
      siteUrl: options.url,
      baseUrl: options.baseUrl.replace(/\/?$/, "/"),
      devServerPort: 3000,
    };

    console.log("Building site...");
    const { pages, elapsed } = await generateSite(config);
    console.log(`Generated ${pages.length} pages in ${elapsed.toFixed(0)}ms`);

    await generateRss(config, pages);
    console.log("RSS feed generated: feed.xml");
    console.log("Build complete.");
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .requiredOption("-s, --source <dir>", "Source directory of markdown files", "content")
  .requiredOption("-t, --templates <dir>", "Template directory with Handlebars files", "templates")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML", "dist")
  .option("--title <title>", "Site title", "My Site")
  .option("--url <url>", "Site URL", "https://example.com")
  .option("--base-url <base>", "Base URL path", "/")
  .option("--port <port>", "Dev server port", "3000")
  .action(async (options) => {
    const config: SiteConfig = {
      sourceDir: path.resolve(options.source),
      templateDir: path.resolve(options.templates),
      outputDir: path.resolve(options.output),
      siteTitle: options.title,
      siteUrl: options.url,
      baseUrl: options.baseUrl.replace(/\/?$/, "/"),
      devServerPort: parseInt(options.port, 10),
    };

    await watchAndServe(config);
  });

program.parse(process.argv);
