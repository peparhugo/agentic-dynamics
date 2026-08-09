#!/usr/bin/env node
import { program } from "commander";
import { resolve } from "node:path";
import { watch } from "chokidar";
import type { SiteConfig } from "./types.js";
import { build } from "./generator.js";
import { createDevServer } from "./server.js";

program
  .name("ssg")
  .description("A static site generator")
  .version("1.0.0");

program
  .command("build")
  .description("Build the static site")
  .option("-s, --source <path>", "Source directory of markdown files", "content")
  .option("-t, --templates <path>", "Template directory with Handlebars files", "templates")
  .option("-o, --output <path>", "Output directory for generated site", "public")
  .option("-b, --base-url <url>", "Base URL for the site", "http://localhost:3000")
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-description <desc>", "Site description", "A static site")
  .option("--include-drafts", "Include draft posts", false)
  .action((opts) => {
    const config: SiteConfig = {
      source: resolve(opts.source),
      templates: resolve(opts.templates),
      output: resolve(opts.output),
      baseUrl: opts.baseUrl,
      includeDrafts: opts.includeDrafts,
      siteTitle: opts.siteTitle,
      siteDescription: opts.siteDescription,
    };
    console.log("Building site...");
    build(config);
    console.log(`Site built to ${config.output}`);
  });

program
  .command("serve")
  .description("Start a dev server with live reload")
  .option("-s, --source <path>", "Source directory of markdown files", "content")
  .option("-t, --templates <path>", "Template directory with Handlebars files", "templates")
  .option("-o, --output <path>", "Output directory for generated site", "public")
  .option("-b, --base-url <url>", "Base URL for the site", "http://localhost:3000")
  .option("-p, --port <number>", "Port for the dev server", "3000")
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-description <desc>", "Site description", "A static site")
  .option("--include-drafts", "Include draft posts", false)
  .action((opts) => {
    const config: SiteConfig = {
      source: resolve(opts.source),
      templates: resolve(opts.templates),
      output: resolve(opts.output),
      baseUrl: opts.baseUrl,
      includeDrafts: opts.includeDrafts,
      siteTitle: opts.siteTitle,
      siteDescription: opts.siteDescription,
    };
    const port = parseInt(opts.port, 10);

    console.log("Building site...");
    build(config);

    const { server, reload } = createDevServer(config, port);

    server.listen(port, () => {
      console.log(`Dev server running at http://localhost:${port}`);
    });

    const watchPaths = [config.source, config.templates];
    const watcher = watch(watchPaths, {
      ignoreInitial: true,
      awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 100 },
    });

    watcher.on("all", (_event, _path) => {
      console.log("Changes detected, rebuilding...");
      try {
        build(config);
        reload();
        console.log("Rebuild complete.");
      } catch (err) {
        console.error("Build error:", err);
      }
    });
  });

program.parse();
