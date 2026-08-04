import { useState } from "react";
import { DataTable, type DataColumn, type SortDescriptor } from "./DataTable";
import "./app.css";

type RecordRow = {
  id: number;
  account: string;
  region: string;
  status: string;
  owner: string;
  revenue: number;
};

const REGIONS = ["North", "South", "East", "West", "Central"];
const STATUSES = ["Active", "Review", "Paused", "Closed"];

const initialRows: RecordRow[] = Array.from({ length: 100_000 }, (_, index) => ({
  id: index + 1,
  account: `Account ${String(index + 1).padStart(6, "0")}`,
  region: REGIONS[index % REGIONS.length],
  status: STATUSES[index % STATUSES.length],
  owner: `Team ${(index % 24) + 1}`,
  revenue: ((index * 7919) % 900_000) + 10_000,
}));

const baseColumns: DataColumn<RecordRow>[] = [
  { id: "id", header: "ID", accessor: "id", width: 92, sortable: true, filterable: true, align: "right" },
  { id: "account", header: "Account", accessor: "account", width: 220, sortable: true, filterable: true, editable: true },
  { id: "region", header: "Region", accessor: "region", width: 140, sortable: true, filterable: true, editable: true },
  { id: "status", header: "Status", accessor: "status", width: 135, sortable: true, filterable: true, editable: true },
  { id: "owner", header: "Owner", accessor: "owner", width: 145, sortable: true, filterable: true, editable: true },
  {
    id: "revenue",
    header: "Revenue",
    accessor: "revenue",
    width: 150,
    sortable: true,
    filterable: true,
    editable: true,
    align: "right",
    parse: (value) => Number(value),
    render: (value) => Number(value).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }),
    compare: (left, right) => left.revenue - right.revenue,
  },
];

const metricColumns: DataColumn<RecordRow>[] = Array.from({ length: 46 }, (_, index) => ({
  id: `metric-${index + 1}`,
  header: `Metric ${index + 1}`,
  width: 128,
  sortable: true,
  align: "right" as const,
  accessor: (row: RecordRow) => (row.id * (index + 17)) % 10_000,
  compare: (left: RecordRow, right: RecordRow) =>
    ((left.id * (index + 17)) % 10_000) - ((right.id * (index + 17)) % 10_000),
}));

const columns = [...baseColumns, ...metricColumns];

export default function App() {
  const [rows, setRows] = useState(initialRows);
  const [sortSummary, setSortSummary] = useState("No active sort");

  const updateRow = (row: RecordRow, columnId: string, value: unknown) => {
    setRows((current) => current.map((item) => item.id === row.id ? { ...item, [columnId]: value } : item));
  };

  const summarizeSort = (sorts: SortDescriptor[]) => {
    setSortSummary(sorts.length ? sorts.map((sort) => `${sort.columnId} ${sort.direction}`).join(", ") : "No active sort");
  };

  return (
    <main>
      <header className="hero">
        <div>
          <p className="eyebrow">Operations intelligence</p>
          <h1>Atlas Ledger</h1>
        </div>
        <p className="hero-note">100,000 records · 52 dimensions<br />{sortSummary}</p>
      </header>
      <DataTable
        ariaLabel="Account operations"
        rows={rows}
        columns={columns}
        rowKey="id"
        height={620}
        rowHeight={42}
        selectionMode="multi"
        onSortChange={summarizeSort}
        onRowUpdate={updateRow}
      />
    </main>
  );
}
