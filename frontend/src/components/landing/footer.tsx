import Link from 'next/link'

export function Footer() {
  return (
    <footer className="border-t py-12">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6 lg:px-8">
        <p className="text-sm text-muted-foreground">
          Copyrights © 2026 CloudPilot. All rights reserved
        </p>
        <div className="flex gap-6 text-sm text-muted-foreground">
          <Link href="#" className="hover:text-foreground transition-colors">
            Privacy Policy
          </Link>
          <Link href="#" className="hover:text-foreground transition-colors">
            Terms of Service
          </Link>
          <Link href="#" className="hover:text-foreground transition-colors">
            Help Center
          </Link>
        </div>
      </div>
    </footer>
  )
}
