import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { controls } from '@/app/constants'

export function Control() {
  return (
    <section id="control" className="border-t bg-muted/50 py-6">
      <div className="mx-auto px-4 sm:px-6 ">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Control</h2>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {controls.map((item, i) => (
            <Card key={i} className="bg-muted/20">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-background shadow-sm ring-1 ring-border">
                  <item.icon className="h-6 w-6 text-primary" />
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
