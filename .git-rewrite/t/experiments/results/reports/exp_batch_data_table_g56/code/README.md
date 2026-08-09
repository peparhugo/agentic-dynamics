# Atlas Data Grid

A dependency-light React and TypeScript data grid for high-volume datasets. The demo renders a 100,000-row by 52-column dataset while mounting only the visible row window.

## Run

```bash
npm install
npm run dev
```

Use `DataTable` from `src/index.ts`. Set `sortMode="server"` or `filterMode="server"` and handle the corresponding callbacks for remote datasets. `rows` should contain the currently loaded server result and `totalRowCount` may describe the full result count.

## Interaction

- Click a heading to sort; Shift+click adds sort levels.
- Drag headings or use their accessible arrow controls to reorder columns.
- Drag column separators or focus them and use Left/Right to resize.
- Click or press Space to select; Shift selects a contiguous range.
- Double-click an editable cell, or press Enter/F2, to edit.
- Use arrows, Home, End, Page Up, and Page Down to navigate cells.
- Export the filtered/sorted result as UTF-8 CSV or an Excel-compatible `.xls` table.
