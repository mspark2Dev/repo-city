import { formatMoney } from '@/lib/money'
import { slugify } from '~lib'

interface Props {
  id: string
  totalCents: number
  status: 'draft' | 'confirmed' | 'settled'
}

export function OrderRow({ id, totalCents, status }: Props) {
  const cls = status === 'settled' ? 'done' : status === 'confirmed' ? 'pending' : 'draft'
  return (
    <tr className={cls} id={slugify(id)}>
      <td>{id}</td>
      <td>{formatMoney(totalCents)}</td>
    </tr>
  )
}
