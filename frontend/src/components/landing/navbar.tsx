import Link from 'next/link'
import Image from 'next/image'
import lightModeLogo from '@/../public/logos/logo-full-on-light.svg'
import darkModeLogo from '@/../public/logos/logo-full-on-dark.svg'
import GithubButton from './github-button'

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-md">
      {/* max-w-7xl is exactly 1280px */}
      <div className="mx-auto flex h-16 items-center justify-between px-4 sm:px-6 ">
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
        <nav className="hidden md:flex items-center gap-8 text-lg font-medium text-muted-foreground">
          <Link href="#product" className="hover:text-foreground transition-colors">
            Product
          </Link>
          <Link href="#how-it-works" className="hover:text-foreground transition-colors">
            How it works
          </Link>
          <Link href="#features" className="hover:text-foreground transition-colors">
            Features
          </Link>
          <Link href="#control" className="hover:text-foreground transition-colors">
            Control
          </Link>
        </nav>
        <GithubButton buttonClass="w-30 h- md:w-40 md:h-12" />
      </div>
    </header>
  )
}
