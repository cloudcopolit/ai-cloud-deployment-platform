'lucide-react'
import { Shield } from 'lucide-react'

import GithubButton from './github-button'

export function Hero() {
  return (
    <section id="product" className="relative overflow-hidden p-6 flex justify-center items-center">
      {/* Text Content */}
      <div className="flex flex-col justify-center items-center text-center ">
        <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl lg:text-[64px]  xl:text-8xl lg:leading-[1.1] text-balance">
          From GitHub to AWS.
          <span className="text-primary"> Your Cloud, Engineered by AI.</span>
        </h1>

        <p className="mt-3 xl:text-xl text-base text-muted-foreground font-medium text-balance text-center xl:w-1/2">
          Connect your repository and let CloudPilot prepare deployment plans for you.
        </p>

        <GithubButton buttonClass="mt-5 w-50 h-15 font-bold text-lg" iconClass="size-7!" />

        <div className="mt-8 flex items-center gap-2 text-sm text-muted-foreground">
          <Shield className="h-4 w-4 text-emerald-600" />
          <span>Your code stays yours. Your infrastructure stays under control</span>
        </div>
      </div>
    </section>
  )
}
