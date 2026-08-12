import { Plugin } from "../plugin";
import { PageData, BuildOptions } from "../types";
import { createTemplateEngine, TemplateEngine } from "../template-engine";
import path from "path";
import { generatePageHtml, generateIndexHtml } from "../html-generator";
import { promises as fs } from "fs";

export function createTemplatePlugin(): Plugin {
  let engine: TemplateEngine | null = null;

  return {
    name: "template",

    async beforeBuild(options: BuildOptions): Promise<void> {
      const templatesDir = options.templatesDir
        ? path.resolve(options.templatesDir)
        : path.resolve("templates");
      engine = await createTemplateEngine(templatesDir);
    },

    async onFile(page: PageData, _options: BuildOptions): Promise<PageData> {
      let pageHtml: string;
      if (engine) {
        pageHtml = engine.renderPage(page.frontmatter, page.html);
      } else {
        pageHtml = generatePageHtml(page);
      }
      return { path: page.path, frontmatter: page.frontmatter, html: pageHtml };
    },

    async afterBuild(options: BuildOptions, pages: PageData[]): Promise<void> {
      let indexHtml: string;
      if (engine) {
        indexHtml = engine.renderIndex(pages);
        if (!indexHtml) {
          indexHtml = generateIndexHtml(pages);
        }
      } else {
        indexHtml = generateIndexHtml(pages);
      }

      const outputDir = path.resolve(options.outputDir);
      await fs.writeFile(path.join(outputDir, "index.html"), indexHtml, "utf-8");
    },
  };
}
