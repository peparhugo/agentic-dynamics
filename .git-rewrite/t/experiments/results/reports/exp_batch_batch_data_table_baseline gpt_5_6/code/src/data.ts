import type { Column, DataRow } from './types';

const companies = ['Northstar Labs', 'Kinetic Works', 'Vela Systems', 'Brightpath', 'Monument Co.', 'Aperture Group', 'Fieldstone', 'Copperline', 'Morrow & Co.', 'Juniper Cloud'];
const owners = ['Avery Chen', 'Maya Patel', 'Theo Martin', 'Nora Singh', 'Jamie Cole', 'Iris Wang', 'Noah Wilson', 'Lena Ortiz'];
const regions = ['North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East'];
const statuses = ['Healthy', 'At risk', 'Onboarding', 'Paused'];
const plans = ['Enterprise', 'Growth', 'Scale', 'Starter'];

export function makeRows(count: number): DataRow[] {
  return Array.from({ length: count }, (_, index) => {
    const id = index + 1;
    const date = new Date(2026, (index * 7) % 12, ((index * 13) % 27) + 1);
    return {
      id,
      company: companies[index % companies.length],
      owner: owners[(index * 3) % owners.length],
      region: regions[(index * 7) % regions.length],
      status: statuses[(index * 5 + Math.floor(index / 17)) % statuses.length],
      plan: plans[(index * 11) % plans.length],
      seats: 12 + ((index * 37) % 950),
      mrr: 850 + ((index * 7919) % 92000),
      health: 41 + ((index * 17) % 59),
      renewal: date.toISOString().slice(0, 10),
      created: new Date(2023 + (index % 3), (index * 5) % 12, (index % 27) + 1).toISOString().slice(0, 10),
    };
  });
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat('en-US');

export const columns: Column<DataRow>[] = [
  { id: 'id', label: 'Account ID', width: 118, value: (row) => `AC-${String(row.id).padStart(6, '0')}` },
  { id: 'company', label: 'Company', width: 190, editable: true, value: (row) => row.company },
  { id: 'status', label: 'Status', width: 132, editable: true, value: (row) => row.status },
  { id: 'owner', label: 'Owner', width: 158, editable: true, value: (row) => row.owner },
  { id: 'region', label: 'Region', width: 158, value: (row) => row.region },
  { id: 'plan', label: 'Plan', width: 126, editable: true, value: (row) => row.plan },
  { id: 'mrr', label: 'Monthly revenue', width: 164, align: 'right', editable: true, value: (row) => row.mrr, format: (value) => money.format(Number(value)) },
  { id: 'seats', label: 'Seats', width: 100, align: 'right', editable: true, value: (row) => row.seats, format: (value) => integer.format(Number(value)) },
  { id: 'health', label: 'Health', width: 118, align: 'right', value: (row) => row.health, format: (value) => `${value}%` },
  { id: 'renewal', label: 'Renewal', width: 136, editable: true, value: (row) => row.renewal },
  { id: 'created', label: 'Created', width: 136, value: (row) => row.created },
  ...Array.from({ length: 42 }, (_, index): Column<DataRow> => ({
    id: `metric-${index + 1}`,
    label: `Metric ${String(index + 1).padStart(2, '0')}`,
    width: 124,
    align: 'right',
    editable: true,
    value: (row) => ((row.id * (index + 19) * 13) % 10000) / 10,
    format: (value) => Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 }),
  })),
];
