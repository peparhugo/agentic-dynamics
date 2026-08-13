# Test Coverage Documentation

## Parser Tests (`src/__tests__/parser.test.ts`)

### Test Cases (7 tests)

1. **parseMarkdown - simple markdown without frontmatter**
   - Input: Basic markdown content without YAML frontmatter
   - Expected: Title defaults to "Untitled", HTML parsed correctly
   - Status: ✓ Pass

2. **parseMarkdown - with frontmatter**
   - Input: Markdown with YAML frontmatter (title, date, tags array)
   - Expected: Frontmatter extracted correctly, markdown parsed to HTML
   - Status: ✓ Pass

3. **parseMarkdown - headings and lists**
   - Input: Markdown with H2 heading and bulleted list
   - Expected: HTML contains proper `<h2>` tags and `<li>` elements
   - Status: ✓ Pass

4. **parseMarkdown - code blocks**
   - Input: Markdown with fenced code block (```typescript)
   - Expected: HTML contains `<code>` tags with content preserved
   - Status: ✓ Pass

5. **parseMarkdown - custom frontmatter**
   - Input: YAML frontmatter with custom properties (author, category)
   - Expected: Custom properties preserved in frontmatter object
   - Status: ✓ Pass

6. **parseMarkdown - empty tags**
   - Input: Frontmatter without tags property
   - Expected: tags defaults to empty array
   - Status: ✓ Pass

## Generator Tests (`src/__tests__/generator.test.ts`)

### generatePageHTML Tests (6 tests)

1. **generates valid HTML for a page**
   - Input: ParsedPage with title, date, tags, and HTML content
   - Expected: Valid HTML structure with all frontmatter rendered
   - Validates: DOCTYPE, title tag, h1, date, tags, navigation link
   - Status: ✓ Pass

2. **handles pages without date**
   - Input: ParsedPage with no date
   - Expected: Date section omitted from output
   - Status: ✓ Pass

3. **handles pages without tags**
   - Input: ParsedPage with empty tags array
   - Expected: Tag section not rendered
   - Status: ✓ Pass

4. **escapes HTML in title (XSS prevention)**
   - Input: Title with script tags
   - Expected: `<` and `>` escaped to `&lt;` and `&gt;`
   - Status: ✓ Pass

5. **escapes HTML in tags (XSS prevention)**
   - Input: Tags with HTML entities and quotes
   - Expected: Properly escaped (`&lt;`, `&quot;`)
   - Status: ✓ Pass

### generateIndexHTML Tests (5 tests)

1. **generates index with multiple pages**
   - Input: Array of ParsedPage objects
   - Expected: Valid HTML with links to all pages and page count
   - Status: ✓ Pass

2. **sorts pages by date in descending order**
   - Input: Pages with different dates
   - Expected: Newest posts appear first in HTML
   - Status: ✓ Pass

3. **handles pages without dates**
   - Input: Mix of pages with and without dates
   - Expected: All pages listed, undated pages show "No date"
   - Status: ✓ Pass

4. **displays correct page count**
   - Input: Varying number of pages (1 and 5 examples)
   - Expected: Correct singular/plural form ("1 page" vs "5 pages")
   - Status: ✓ Pass

5. **escapes HTML in page titles (XSS prevention)**
   - Input: Page title with dangerous HTML
   - Expected: HTML properly escaped, injection prevented
   - Status: ✓ Pass

## CLI Integration Tests (`src/__tests__/cli.test.ts`)

### Integration Tests (4 tests)

1. **builds site from markdown files**
   - Setup: Create temp directory with markdown files
   - Action: Run `ssg build` with custom directories
   - Expected: 
     - dist/ directory created
     - HTML files generated for each markdown
     - index.html created
     - Content properly rendered
   - Cleanup: Remove test directories
   - Status: ✓ Pass

2. **generates index.html with all pages**
   - Setup: Create multiple markdown files
   - Action: Run build command
   - Expected:
     - index.html contains all page titles
     - Shows correct page count (2 pages)
   - Status: ✓ Pass

3. **uses default directories if not specified**
   - Setup: Create ./content directory
   - Action: Run `ssg build` without arguments
   - Expected:
     - Uses ./content as input
     - Generates to ./dist
     - Creates valid output
   - Status: ✓ Pass

4. **handles custom content and output directories**
   - Setup: Create custom directory structure
   - Action: Run with `--content` and `--output` flags
   - Expected: Files generated to specified locations
   - Status: ✓ Pass

## Security Tests

### XSS Prevention

All HTML output is sanitized:
- Titles escaped in page HTML
- Tags escaped in page HTML
- Page titles escaped in index
- `escapeHtml()` function converts: `& < > " '`

### Input Validation

- Non-existent content directories rejected with error message
- Missing markdown files handled gracefully
- Invalid frontmatter handled by gray-matter

## Summary

- **Total Tests**: 22 tests across 3 test suites
- **Coverage Areas**:
  - Markdown parsing and frontmatter extraction
  - HTML generation with proper escaping
  - Index page generation with sorting
  - CLI argument handling and file operations
  - XSS prevention and security
  - Edge cases (missing dates, tags, empty files)

All tests are designed to verify:
1. Correct functionality of core features
2. Proper handling of edge cases
3. Security (XSS prevention)
4. Integration between components
