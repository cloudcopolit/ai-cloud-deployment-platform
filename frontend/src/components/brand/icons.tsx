import { cn } from '@/lib/utils'

type SpritePrefix = 'ui' | 'cloud' | 'aws' | 'k8s' | 'docker'

/**
 * An icon from the CloudPilot sprite (public/icons/sprite.svg). It inherits the text color and
 * is decorative: put the meaning in nearby text. The stroke style sits on the sprite's root
 * <svg>, which a <use> of another file does not inherit, so it is repeated here.
 */
export function SpriteIcon({ name, className }: { name: `${SpritePrefix}-${string}`; className?: string }) {
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn('size-5 shrink-0', className)}
    >
      <use href={`/icons/sprite.svg#${name}`} />
    </svg>
  )
}

/* Official colors from public/icons/brands/brand-colors.css. Logos missing here are monochrome
   (they follow the text color, which keeps dark mode readable). */
const BRAND_COLORS: Record<string, string> = {
  react: '#61DAFB',
  python: '#3776AB',
  postgresql: '#4169E1',
  fastapi: '#009688',
  docker: '#2496ED',
  kubernetes: '#326CE5',
  githubactions: '#2088FF',
  terraform: '#844FBA',
  nginx: '#009639',
  redis: '#FF4438',
  vite: '#646CFF',
  typescript: '#3178C6',
  javascript: '#F7DF1E',
  nodedotjs: '#5FA04E',
  aws: '#FF9900'
}

/**
 * A technology logo from public/icons/brands, drawn as a CSS mask so it takes its brand color
 * (or the text color) without inlining the SVG. An empty label makes it decorative.
 */
export function TechLogo({ name, label, className }: { name: string; label: string; className?: string }) {
  const url = `url(/icons/brands/${name}.svg)`
  return (
    <span
      {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true })}
      className={cn('inline-block size-6 shrink-0', className)}
      style={{
        backgroundColor: BRAND_COLORS[name] ?? 'currentColor',
        maskImage: url,
        WebkitMaskImage: url,
        maskSize: 'contain',
        WebkitMaskSize: 'contain',
        maskRepeat: 'no-repeat',
        WebkitMaskRepeat: 'no-repeat',
        maskPosition: 'center',
        WebkitMaskPosition: 'center'
      }}
    />
  )
}
