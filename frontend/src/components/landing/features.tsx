import { features } from '@/app/constants'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Features() {
  return (
    <section id="features" className="border-t py-6">
      <div className="mx-auto px-4 sm:px-6">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Features</h2>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {features.map((item, i) => (
            <Card key={i} className="shadow-sm">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                  <item.icon className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-xl">{item.title}</CardTitle>
                <CardDescription className="text-sm leading-relaxed">{item.desc}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
