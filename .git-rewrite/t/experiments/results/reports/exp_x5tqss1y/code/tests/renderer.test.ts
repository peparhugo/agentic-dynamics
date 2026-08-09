import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { registerPartials, render } from "../src/renderer.js";
import Handlebars from "handlebars";

describe("renderer", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("renders a simple Handlebars template", () => {
    const tmpl = path.join(tmpDir, "test.hbs");
    fs.writeFileSync(tmpl, "<h1>{{site.title}}</h1>");
    const result = render(tmpl, tmpDir, {
      site: { title: "My Site", url: "", description: "" },
      pages: [],
      tags: [],
    });
    expect(result).toBe("<h1>My Site</h1>");
  });

  it("renders with a layout", () => {
    const layoutsDir = path.join(tmpDir, "layouts");
    fs.mkdirSync(layoutsDir);
    const layout = path.join(layoutsDir, "base.hbs");
    fs.writeFileSync(layout, "<html><body>{{{body}}}</body></html>");

    const pageTpl = path.join(tmpDir, "page.hbs");
    fs.writeFileSync(pageTpl, `{{#layout "base"}}<h1>Hello</h1>{{/layout}}`);

    const result = render(pageTpl, layoutsDir, {
      site: { title: "S", url: "", description: "" },
      pages: [],
      tags: [],
    });
    expect(result).toBe("<html><body><h1>Hello</h1></body></html>");
  });

  it("registers and resolves partials", () => {
    const partialsDir = path.join(tmpDir, "partials");
    fs.mkdirSync(partialsDir);
    fs.writeFileSync(path.join(partialsDir, "nav.hbs"), "<nav>nav</nav>");
    registerPartials(partialsDir);

    const tmpl = path.join(tmpDir, "p.hbs");
    fs.writeFileSync(tmpl, "{{> nav}}<h1>Page</h1>");
    const result = render(tmpl, tmpDir, {
      site: { title: "T", url: "", description: "" },
      pages: [],
      tags: [],
    });
    expect(result).toBe("<nav>nav</nav><h1>Page</h1>");
  });

  it("renders page context with frontmatter and html", () => {
    const tmpl = path.join(tmpDir, "post.hbs");
    fs.writeFileSync(tmpl, "<h1>{{page.frontmatter.title}}</h1><div>{{{page.html}}}</div>");

    const result = render(tmpl, tmpDir, {
      site: { title: "S", url: "", description: "" },
      pages: [],
      tags: [],
      page: {
        frontmatter: { title: "Post Title" },
        html: "<p>content</p>",
        content: "content",
        raw: "",
        slug: "post-title",
        sourcePath: "",
        outputPath: "post-title.html",
      },
    });
    expect(result).toContain("<h1>Post Title</h1>");
    expect(result).toContain("<p>content</p>");
  });

  it("renders list of pages for index", () => {
    const tmpl = path.join(tmpDir, "index.hbs");
    fs.writeFileSync(tmpl, "{{#each pages}}<a>{{frontmatter.title}}</a>{{/each}}");

    const result = render(tmpl, tmpDir, {
      site: { title: "S", url: "", description: "" },
      pages: [
        {
          frontmatter: { title: "A" },
          html: "",
          content: "",
          raw: "",
          slug: "a",
          sourcePath: "",
          outputPath: "a.html",
        },
        {
          frontmatter: { title: "B" },
          html: "",
          content: "",
          raw: "",
          slug: "b",
          sourcePath: "",
          outputPath: "b.html",
        },
      ],
      tags: [],
    });
    expect(result).toBe("<a>A</a><a>B</a>");
  });
});
