import { describe, it, expect, beforeEach } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import Handlebars from "handlebars";
import {
  loadPartials,
  compileTemplate,
  compileLayout,
  renderPage,
} from "../src/renderer.js";

describe("renderer", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-renderer-"));
  });

  describe("loadPartials", () => {
    it("loads and registers partials from a directory", () => {
      const partialsDir = path.join(tmpDir, "partials");
      fs.mkdirSync(partialsDir, { recursive: true });
      fs.writeFileSync(
        path.join(partialsDir, "header.hbs"),
        "<header>{{title}}</header>"
      );
      fs.writeFileSync(
        path.join(partialsDir, "footer.hbs"),
        "<footer>end</footer>"
      );

      loadPartials(partialsDir);

      const main = `{{> header}}{{> footer}}`;
      const tmpl = Handlebars.compile(main);
      const result = tmpl({ title: "Hello" });
      expect(result).toContain("<header>Hello</header>");
      expect(result).toContain("<footer>end</footer>");
    });

    it("does nothing if partials directory does not exist", () => {
      expect(() =>
        loadPartials(path.join(tmpDir, "nonexistent"))
      ).not.toThrow();
    });
  });

  describe("compileTemplate and renderPage", () => {
    it("renders a simple template with context", () => {
      fs.writeFileSync(
        path.join(tmpDir, "page.hbs"),
        "<h1>{{page.title}}</h1><div>{{{page.content}}}</div>"
      );

      const template = compileTemplate(tmpDir, "page");
      const result = renderPage("", null, template, {
        page: { title: "Test", content: "<p>Body</p>" },
      });
      expect(result).toContain("<h1>Test</h1>");
      expect(result).toContain("<p>Body</p>");
    });

    it("renders with a layout", () => {
      fs.writeFileSync(
        path.join(tmpDir, "layout.hbs"),
        "<html><body>{{{body}}}</body></html>"
      );
      fs.writeFileSync(
        path.join(tmpDir, "page.hbs"),
        "<main>{{page.title}}</main>"
      );

      const layout = compileLayout(tmpDir, "layout");
      const template = compileTemplate(tmpDir, "page");
      const result = renderPage("", layout, template, {
        page: { title: "Layered" },
      });
      expect(result).toContain("<html>");
      expect(result).toContain("<main>Layered</main>");
      expect(result).toContain("</html>");
    });

    it("renders without layout when layout is null", () => {
      fs.writeFileSync(
        path.join(tmpDir, "page.hbs"),
        "<p>{{page.title}}</p>"
      );

      const template = compileTemplate(tmpDir, "page");
      const result = renderPage("", null, template, {
        page: { title: "Solo" },
      });
      expect(result).toBe("<p>Solo</p>");
    });

    it("throws when template not found", () => {
      expect(() => compileTemplate(tmpDir, "missing")).toThrow(
        /Template not found/
      );
    });

    it("returns null when layout not found", () => {
      const layout = compileLayout(tmpDir, "nonexistent");
      expect(layout).toBeNull();
    });
  });

  describe("context propagation", () => {
    it("passes site context to template", () => {
      fs.writeFileSync(
        path.join(tmpDir, "page.hbs"),
        "<title>{{site.title}}</title><p>{{page.title}}</p>"
      );

      const template = compileTemplate(tmpDir, "page");
      const result = renderPage("", null, template, {
        site: { title: "My Site" },
        page: { title: "Post" },
      });

      expect(result).toContain("<title>My Site</title>");
      expect(result).toContain("<p>Post</p>");
    });

    it("passes pages list for navigation", () => {
      fs.writeFileSync(
        path.join(tmpDir, "page.hbs"),
        "{{#each pages}}<a href=\"/{{slug}}/\">{{title}}</a>{{/each}}"
      );

      const template = compileTemplate(tmpDir, "page");
      const result = renderPage("", null, template, {
        pages: [
          { title: "A", slug: "a" },
          { title: "B", slug: "b" },
        ],
      });

      expect(result).toContain('href="/a/"');
      expect(result).toContain('href="/b/"');
    });
  });
});
