export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidPhone(phone: string): boolean {
  return /^[\d\s\-\+\(\)]{7,20}$/.test(phone);
}

export function isValidPostalCode(code: string): boolean {
  return /^[A-Za-z0-9\s\-]{3,10}$/.test(code);
}

export function isValidDate(date: string): boolean {
  if (!date) return false;
  const d = new Date(date);
  return !isNaN(d.getTime());
}

export function isDateInPast(date: string): boolean {
  const d = new Date(date);
  const now = new Date();
  now.setHours(23, 59, 59, 999);
  return d <= now;
}

export function isNotEmpty(value: string): boolean {
  return value.trim().length > 0;
}

export function isPositiveNumber(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value) && parseFloat(value) > 0;
}
