import { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';
import { columns, makeRows } from './data';
import { DataGrid } from './DataGrid';
import { exportCsv, exportExcel } from './export';
import { ChevronIcon, ColumnsIcon, DownloadIcon, FilterIcon, SearchIcon } from './icons';
import type { DataRow, FilterMode, SelectionMode, SortRule } from './types';

const allRows = makeRows(100_000);

function sortRows(rows: DataRow[], rules: SortRule[]) {
  if (!rules.length) return rows;
  return [...rows].sort((left, right) => {
    for (const rule of rules) {
      const column = columns.find((item) => item.id === rule.columnId)!;
      const a = column.value(left);
      const b = column.value(right);
      const compared = typeof a === 'number' && typeof b === 'number'
        ? a - b
        : String(a ?? '').localeCompare(String(b ?? ''), undefined, { numeric: true });
      if (compared) return rule.direction === 'asc' ? compared : -compared;
    }
    return left.id - right.id;
  });
}

function queryRows(query: string, status: string, rules: SortRule[]) {
  const term = query.trim().toLowerCase();
  const filtered = !term && status === 'All'
    ? allRows
    : allRows.filter((row) => {
      const matchesStatus = status === 'All' || row.status === status;
      const haystack = `${row.id} ${row.company} ${row.owner} ${row.region} ${row.plan}`.toLowerCase();
      return matchesStatus && (!term || haystack.includes(term));
    });
  return sortRows(filtered, rules);
}

export default function App() {
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query);
  const [status, setStatus] = useState('All');
  const [filterMode, setFilterMode] = useState<FilterMode>('client');
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('multi');
  const [sortRules, setSortRules] = useState<SortRule[]>([]);
  const [serverRows, setServerRows] = useState(allRows);
  const [serverLoading, setServerLoading] = useState(false);
  const [selectedCount, setSelectedCount] = useState(0);
  const [exportOpen, setExportOpen] = useState(false);

  const clientRows = useMemo(() => queryRows(deferredQuery, status, sortRules), [deferredQuery, status, sortRules]);

  useEffect(() => {
    if (filterMode !== 'server') return;
    setServerLoading(true);
    const timer = window.setTimeout(() => {
      startTransition(() => {
        setServerRows(queryRows(deferredQuery, status, sortRules));
        setServerLoading(false);
      });
    }, 420);
    return () => window.clearTimeout(timer);
  }, [deferredQuery, status, sortRules, filterMode]);

  const rows = filterMode === 'client' ? clientRows : serverRows;

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#" aria-label="Atlas home"><span className="brand-mark"><i /><i /><i /></span><strong>ATLAS</strong></a>
        <nav aria-label="Primary navigation">
          <a href="#overview">Overview</a>
          <a className="active" href="#data">Data</a>
          <a href="#automations">Automations</a>
          <a href="#reports">Reports</a>
        </nav>
        <div className="top-actions"><button className="help-button">?</button><div className="avatar" title="Nora Singh">NS</div></div>
      </header>

      <section className="page-head">
        <div>
          <span className="eyebrow">DATA OPERATIONS / ACCOUNTS</span>
          <h1>Customer accounts</h1>
          <p>Explore, edit, and export your complete account dataset.</p>
        </div>
        <div className="dataset-meta"><span className="live-dot" /> <strong>Live dataset</strong><i /> Updated just now</div>
      </section>

      <section className="workspace" aria-label="Account data workspace">
        <div className="toolbar">
          <label className="search-field">
            <SearchIcon />
            <span className="sr-only">Search accounts</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company, owner, region..." />
            <kbd>⌘ K</kbd>
          </label>
          <label className="select-control">
            <FilterIcon />
            <span className="sr-only">Filter by status</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option>All</option><option>Healthy</option><option>At risk</option><option>Onboarding</option><option>Paused</option>
            </select>
            <ChevronIcon />
          </label>
          <div className="mode-toggle" aria-label="Filtering mode">
            <button className={filterMode === 'client' ? 'active' : ''} onClick={() => setFilterMode('client')}>Client</button>
            <button className={filterMode === 'server' ? 'active' : ''} onClick={() => setFilterMode('server')}>Server</button>
          </div>
          <div className="toolbar-spacer" />
          <label className="compact-select">
            <span>Selection</span>
            <select value={selectionMode} onChange={(event) => setSelectionMode(event.target.value as SelectionMode)}>
              <option value="single">Single</option><option value="multi">Multi</option><option value="range">Range</option>
            </select>
            <ChevronIcon />
          </label>
          <button className="tool-button" title="53 columns available"><ColumnsIcon /> 53 columns</button>
          <div className="export-wrap">
            <button className="primary-button" onClick={() => setExportOpen((open) => !open)} aria-expanded={exportOpen}><DownloadIcon /> Export <ChevronIcon /></button>
            {exportOpen && (
              <div className="export-menu">
                <button onClick={() => { exportCsv(rows, columns); setExportOpen(false); }}><strong>CSV</strong><span>Comma-separated values</span></button>
                <button onClick={() => { exportExcel(rows, columns); setExportOpen(false); }}><strong>Excel</strong><span>Microsoft Excel workbook</span></button>
              </div>
            )}
          </div>
        </div>

        <div className="result-bar">
          <div><strong>{rows.length.toLocaleString()}</strong> accounts <span>across {columns.length} columns</span></div>
          {sortRules.length > 0 && <span className="sort-summary">Sorted by {sortRules.map((rule) => columns.find((column) => column.id === rule.columnId)?.label).join(' + ')}</span>}
          {selectedCount > 0 && <span className="selection-summary">{selectedCount.toLocaleString()} selected</span>}
          <span className={`engine-badge ${filterMode}`}><i /> {filterMode === 'client' ? 'In-browser engine' : 'Server query'}</span>
        </div>

        <DataGrid
          rows={rows}
          columns={columns}
          sortRules={sortRules}
          onSortChange={setSortRules}
          selectionMode={selectionMode}
          onSelectionCountChange={setSelectedCount}
          loading={serverLoading}
        />
      </section>
    </main>
  );
}
