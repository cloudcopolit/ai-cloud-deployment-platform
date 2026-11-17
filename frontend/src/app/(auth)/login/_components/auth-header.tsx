import Link from 'next/link'
import Image from 'next/image'
import lightModeLogo from '@/../public/logos/logo-full-on-light.svg'
import darkModeLogo from '@/../public/logos/logo-full-on-dark.svg'
export function AuthHeader() {
  return (
    <header className="h-20 w-full border-b bg-white">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Image
          src={lightModeLogo}
          width={150}
          alt="lightModeLogo"
          className="dark:hidden h-auto w-37.5"
        />
        <Image
          src={darkModeLogo}
          width={150}
          alt="darkModeLogo"
          className="dark:block hidden h-auto"
        />

        {/* Link */}
        <Link
          href="/"
          className="text-sm font-light text-muted-foreground hover:text-foreground transition-colors"
        >
          Back to Home
        </Link>
      </div>
    </header>
  )
}
