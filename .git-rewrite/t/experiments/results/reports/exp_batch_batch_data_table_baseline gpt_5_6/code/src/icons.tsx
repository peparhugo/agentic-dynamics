import type { SVGProps } from 'react';

type Props = SVGProps<SVGSVGElement>;
const Icon = ({ children, ...props }: Props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;

export const SearchIcon = (props: Props) => <Icon {...props}><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></Icon>;
export const FilterIcon = (props: Props) => <Icon {...props}><path d="M4 5h16M7 12h10M10 19h4" /></Icon>;
export const DownloadIcon = (props: Props) => <Icon {...props}><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" /></Icon>;
export const ColumnsIcon = (props: Props) => <Icon {...props}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16m6-16v16" /></Icon>;
export const ChevronIcon = (props: Props) => <Icon {...props}><path d="m8 10 4 4 4-4" /></Icon>;
export const SortIcon = (props: Props) => <Icon {...props}><path d="m8 9 4-4 4 4M16 15l-4 4-4-4" /></Icon>;
export const CloseIcon = (props: Props) => <Icon {...props}><path d="m6 6 12 12M18 6 6 18" /></Icon>;
export const CheckIcon = (props: Props) => <Icon {...props}><path d="m5 12 4 4L19 6" /></Icon>;
