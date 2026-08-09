import Handlebars from "handlebars";
import * as fs from "node:fs";
import * as path from "node:path";
import { TemplateContext } from "./types.js";

export function registerPartials(partialsDir: string): void {
  if (!fs.existsSync(partialsDir)) return;
  for (const entry of fs.readdirSync(partialsDir)) {
    const fullPath = path.join(partialsDir, entry);
    if (fs.statSync(fullPath).isFile() && entry.endsWith(".hbs")) {
      const name = path.basename(entry, ".hbs");
      const source = fs.readFileSync(fullPath, "utf-8");
      Handlebars.registerPartial(name, source);
    }
  }
}

export function render(
  templatePath: string,
  layoutsDir: string,
  context: TemplateContext
): string {
  const templateSource = fs.readFileSync(templatePath, "utf-8");
  const template = Handlebars.compile(templateSource);
  const body = template(context);

  const layoutName = (body.match(/^{{#layout\s+"([^"]+)"}}/) ?? [])[1];
  if (layoutName) {
    const resolved = body.replace(/^{{#layout\s+"[^"]+"}}\s*/s, "");
    const layoutPath = path.join(layoutsDir, `${layoutName}.hbs`);
    if (fs.existsSync(layoutPath)) {
      const layoutSource = fs.readFileSync(layoutPath, "utf-8");
      const layoutTemplate = Handlebars.compile(layoutSource);
      return layoutTemplate({ ...context, body: resolved });
    }
  }

  return body;
}

export function escapeHtml(str: string): string {
  return new Handlebars.SafeString(str).toString();
}
