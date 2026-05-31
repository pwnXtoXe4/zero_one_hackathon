import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const eur = (n: number, d = 0) =>
  '€' + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

export const eurM = (n: number) => '€' + (n / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'M'

export const tons = (n: number) =>
  Math.abs(n) >= 1000
    ? (n / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'k t'
    : Math.round(n) + ' t'

export const num = (n: number, d = 0) =>
  n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

export const pct = (n: number) => (n > 0 ? '+' : '') + n.toFixed(1) + '%'
