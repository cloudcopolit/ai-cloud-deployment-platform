import GithubButton from './github-button'

export function CTA() {
  return (
    <section className="bg-muted/50 py-6">
      <div className="mx-auto  px-4 sm:px-6 ">
        <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-primary/5 px-6 py-24 text-center shadow-sm sm:px-16">
          <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to Simplify Your Deployments?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
            Connect your GitHub repository and let CloudPilot handle your AWS infrastructure from
            commit to production.
          </p>
          <div className="mt-10 flex justify-center">
            <GithubButton buttonClass=" w-50 h-15 font-bold text-lg" iconClass="size-7!" />
          </div>
        </div>
      </div>
    </section>
  )
}
