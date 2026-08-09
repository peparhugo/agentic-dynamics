#!/usr/bin/env node

import { Command } from "commander";
import fs from "fs";
import path from "path";
import { generate } from "./generator";
import { startDevServer } from "./server";
import { SiteConfig } from "./types";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator")
  .requiredOption("--source <dir>", "Source directory of Markdown files")
  .requiredOption("--template <dir>", "Template directory of Handlebars files")
  .requiredOption("--output <dir>", "Output directory for generated HTML")
  .option("--serve", "Start a dev server with live reload")
  .option("--port <num>", "Port for dev server", "3000")
  .option("--site-config <path>", "Path to site config JSON file")
  .action(async (options) => {
    const sourceDir = path.resolve(options.source);
    const templateDir = path.resolve(options.template);
    const outputDir = path.resolve(options.output);
    const port = parseInt(options.port, 10);

    let siteConfig: SiteConfig = {
      title: "My Site",
      description: "A static site",
      url: `http://localhost:${port}`,
    };

    if (options.siteConfig) {
      const configPath = path.resolve(options.siteConfig);
      if (fs.existsSync(configPath)) {
        siteConfig = {
          ...siteConfig,
          ...JSON.parse(fs.readFileSync(configPath, "utf-8")),
        };
      }
    }

    if (!fs.existsSync(sourceDir)) {
      console.error(`Source directory not found: ${sourceDir}`);
      process.exit(1);
    }
    if (!fs.existsSync(templateDir)) {
      console.error(`Template directory not found: ${templateDir}`);
      process.exit(1);
    }

    const build = () =>
      generate({ sourceDir, templateDir, outputDir, siteConfig });

    build();
    console.log(`Site built to ${outputDir}`);

    if (options.serve) {
      startDevServer(outputDir, sourceDir, templateDir, port, build);
    }
  });

program.parse();
