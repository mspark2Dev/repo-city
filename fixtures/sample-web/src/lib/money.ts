export function formatMoney(cents: number, currency = 'USD'): string {
  const value = cents / 100
  if (currency === 'USD') return `$${value.toFixed(2)}`
  if (currency === 'EUR') return `€${value.toFixed(2)}`
  return `${value.toFixed(2)} ${currency}`
}
