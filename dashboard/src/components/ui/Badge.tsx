import { clsx } from 'clsx'

type Variant = 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'purple'

const variants: Record<Variant, string> = {
  green:  'bg-emerald-900/50 text-emerald-400 border-emerald-800',
  red:    'bg-red-900/50 text-red-400 border-red-800',
  yellow: 'bg-amber-900/50 text-amber-400 border-amber-800',
  blue:   'bg-brand-900/50 text-brand-400 border-brand-800',
  gray:   'bg-gray-800 text-gray-400 border-gray-700',
  purple: 'bg-purple-900/50 text-purple-400 border-purple-800',
}

interface BadgeProps {
  children: React.ReactNode
  variant?: Variant
  className?: string
}

export function Badge({ children, variant = 'gray', className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  )
}
