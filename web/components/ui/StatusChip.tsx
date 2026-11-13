import { STATUS_LABEL, cx } from '@/lib/format';
import type { Status } from '@/lib/types';

export function StatusChip({
  status,
  label,
  size,
  className,
}: {
  status: Status;
  label?: string;
  size?: 'lg';
  className?: string;
}) {
  return (
    <span className={cx('chip chip-dot', `chip-${status}`, size === 'lg' && 'chip-lg', className)}>
      {label ?? STATUS_LABEL[status]}
    </span>
  );
}
