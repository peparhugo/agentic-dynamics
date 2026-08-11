import { PageData } from "./types";

export function generatePageHtml(page: PageData): string {
  let title = page.frontmatter.title || page.path;
  const date = page.frontmatter.date
    ? `<p class="date">${page.frontmatter.date}</p>`
    : "";
  const tags = page.frontmatter.tags
    ? `<p class="tags">Tags: ${page.frontmatter.tags}</p>`
    : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
</head>
<body>
${date}
${tags}
${page.html}
</body>
</html>`;
}

export function generateIndexHtml(pages: PageData[]): string {
  const items = pages
    .map((page) => {
      const href = page.path.replace(/\.md$/, ".html");
      const title = page.frontmatter.title || page.path;
      const date = page.frontmatter.date
        ? `<span class="date">${page.frontmatter.date}</span>`
        : "";
      const tags = page.frontmatter.tags
        ? `<span class="tags">Tags: ${page.frontmatter.tags}</span>`
        : "";
      return `    <li>
      <a href="${href}">${title}</a>
      ${date}
      ${tags}
    </li>`;
    })
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Site Index</title>
</head>
<body>
<h1>Pages</h1>
<ul>
${items}
</ul>
</body>
</html>`;
}
