import Image from 'next/image'

import { cn } from '@/lib/utils'
import mark from '/public/logos/logo-icon.svg'
import fullOnDark from '/public/logos/logo-full-on-dark.svg'
import fullOnLight from '/public/logos/logo-full-on-light.svg'

/**
 * The CloudPilot wordmark from public/logos. The light and dark artwork are both rendered and
 * swapped with CSS, so the right one shows before hydration and screen readers hear one name.
 * `surface="dark"` forces the on-dark artwork on brand-black panels in either theme.
 */
export function Logo({
  className,
  surface = 'theme',
  priority = false
}: {
  className?: string
  surface?: 'theme' | 'dark'
  priority?: boolean
}) {
  if (surface === 'dark') {
    return <Image src={fullOnDark} alt="CloudPilot" priority={priority} className={cn('h-8 w-auto', className)} />
  }
  return (
    <>
      <Image src={fullOnLight} alt="CloudPilot" priority={priority} className={cn('h-8 w-auto dark:hidden', className)} />
      <Image
        src={fullOnDark}
        alt="CloudPilot"
        priority={priority}
        className={cn('hidden h-8 w-auto dark:block', className)}
      />
    </>
  )
}

/** The cloud-and-arrow mark alone (decorative unless given a label). */
export function LogoMark({ className, label }: { className?: string; label?: string }) {
  return <Image src={mark} alt={label ?? ''} className={cn('size-8', className)} />
}
