import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const eur = (n: number, d = 0) =>
  '€' + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

export const eurM = (n: number) => '€' + (n / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'M'

export const tons = (n: number) => {
  const a = Math.abs(n)
  if (a >= 1e6) return (n / 1e6).toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' Mt'
  if (a >= 1000) return (n / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'k t'
  return Math.round(n) + ' t'
}

export const num = (n: number, d = 0) =>
  n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

export const pct = (n: number) => (n > 0 ? '+' : '') + n.toFixed(1) + '%'
