import fs from "node:fs";
import path from "node:path";
import Handlebars from "handlebars";
import { TemplateData } from "./types";

let partialsDir = "";

export function registerPartials(dir: string): void {
  partialsDir = dir;
  if (!fs.existsSync(dir)) return;
  for (const file of fs.readdirSync(dir)) {
    if (file.endsWith(".hbs")) {
      const name = path.basename(file, ".hbs");
      const source = fs.readFileSync(path.join(dir, file), "utf-8");
      Handlebars.registerPartial(name, source);
    }
  }
}

export function renderTemplate(
  templateDir: string,
  layout: string,
  data: TemplateData
): string {
  const layoutPath = path.join(templateDir, `${layout}.hbs`);
  const layoutSource = fs.readFileSync(layoutPath, "utf-8");

  registerPartials(path.join(templateDir, "partials"));

  const compiled = Handlebars.compile(layoutSource);
  return compiled(data);
}
