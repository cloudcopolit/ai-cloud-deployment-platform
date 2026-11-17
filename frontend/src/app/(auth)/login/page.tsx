import { AuthHeader } from './_components/auth-header'
import { ConnectCard } from './_components/connect-card'

export default function ConnectGithubPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <AuthHeader />

      <main className="flex flex-1 items-center justify-center p-4 sm:p-8">
        <ConnectCard />
      </main>
    </div>
  )
}
