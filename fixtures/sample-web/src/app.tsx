import { OrderRow } from '@/components/OrderRow'
import { formatMoney } from '@/lib/money'
import React from 'react'

export function App({ orders }: { orders: { id: string; totalCents: number }[] }) {
  const total = orders.reduce((sum, o) => sum + o.totalCents, 0)
  return (
    <table>
      <tbody>
        {orders.map((o) => (
          <OrderRow key={o.id} id={o.id} totalCents={o.totalCents} status="draft" />
        ))}
      </tbody>
      <tfoot><tr><td>{formatMoney(total)}</td></tr></tfoot>
    </table>
  )
}
