#!/usr/bin/env node
import { Command } from "commander";
import * as path from "node:path";
import { build } from "./index.js";
import { injectReloadScript, startDevServer } from "./server.js";
import * as fs from "node:fs";
import { SSGConfig } from "./types.js";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator from Markdown with Handlebars templates")
  .version("1.0.0")
  .requiredOption("-s, --source <dir>", "Source directory of Markdown files")
  .requiredOption("-t, --templates <dir>", "Template directory of Handlebars files")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML")
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-url <url>", "Site base URL", "https://example.com")
  .option("--site-description <desc>", "Site description", "A static site")
  .option("-p, --port <number>", "Dev server port", "3000")
  .option("--serve", "Start dev server with live reload", false)
  .action(async (opts) => {
    const config: SSGConfig = {
      source: path.resolve(opts.source),
      templates: path.resolve(opts.templates),
      output: path.resolve(opts.output),
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
      siteDescription: opts.siteDescription,
    };

    if (opts.serve) {
      await build(config);

      const injectReload = (dir: string): void => {
        for (const entry of fs.readdirSync(dir, { recursive: true })) {
          const full = path.join(dir, entry as string);
          if (
            fs.statSync(full).isFile() &&
            (entry as string).endsWith(".html")
          ) {
            const html = fs.readFileSync(full, "utf-8");
            const rewritten = injectReloadScript(html, parseInt(opts.port, 10) + 1);
            fs.writeFileSync(full, rewritten, "utf-8");
          }
        }
      };

      injectReload(config.output);

      startDevServer(
        config.output,
        config.source,
        config.templates,
        parseInt(opts.port, 10),
        async () => {
          await build(config);
          injectReload(config.output);
        }
      );
    } else {
      await build(config);
      process.stdout.write(`Site built to ${config.output}\n`);
    }
  });

program.parse();
