import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { steps } from '@/app/constants'

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t bg-muted/50 py-6">
      <div className="mx-auto  px-4 sm:px-6">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">How It Works</h2>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((item, i) => (
            <Card key={i} className="bg-muted/20">
              <CardHeader>
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-background shadow-sm ring-1 ring-border text-primary text-lg font-bold">
                  {item.step}
                </div>
                <CardTitle className="text-lg">{item.title}</CardTitle>
                <CardDescription className="leading-relaxed">{item.desc}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
