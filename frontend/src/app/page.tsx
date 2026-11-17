import { Navbar } from '@/components/landing/navbar'
import { Hero } from '@/components/landing/hero'
import { HowItWorks } from '@/components/landing/how-it-works'
import { Features } from '@/components/landing/features'
import { Control } from '@/components/landing/control'
import { CTA } from '@/components/landing/cta'
import { Footer } from '@/components/landing/footer'

export const metadata = {
  title: { absolute: 'CloudPilot · From GitHub repository to AWS architecture' }
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground  selection:bg-primary/20">
      <Navbar />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <Control />
        <CTA />
      </main>
      <Footer />
    </div>
  )
}
