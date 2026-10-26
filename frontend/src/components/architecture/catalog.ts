import { AWS_ICONS, type AwsIconKey } from '@/lib/aws-icons/manifest'
import type { PlanComponent } from '@/lib/api/schemas'

/** Where a component sits in the diagram (left to right, then the services row). */
export type Zone = 'edge' | 'ingress' | 'compute' | 'data' | 'regional' | 'frame'

type Entry = { label: string; zone: Zone; icon?: AwsIconKey }

/* ArchitecturePlan component types → diagram placement and official icon. Types missing here
   (or without an official icon) are drawn as a neutral box and logged in WORKLOG.md §8. */
const CATALOG: Record<string, Entry> = {
  route53: { label: 'Route 53', zone: 'edge', icon: 'route53' },
  cloudfront: { label: 'CloudFront', zone: 'edge', icon: 'cloudfront' },
  api_gateway: { label: 'API Gateway', zone: 'edge', icon: 'api_gateway' },
  waf: { label: 'AWS WAF', zone: 'edge', icon: 'waf' },
  acm: { label: 'Certificate Manager', zone: 'edge', icon: 'acm' },
  alb: { label: 'Application Load Balancer', zone: 'ingress', icon: 'alb' },
  ecs_service: { label: 'ECS on Fargate', zone: 'compute', icon: 'ecs_service' },
  lambda: { label: 'Lambda', zone: 'compute', icon: 'lambda' },
  rds: { label: 'RDS', zone: 'data', icon: 'rds' },
  elasticache: { label: 'ElastiCache', zone: 'data', icon: 'elasticache' },
  documentdb: { label: 'DocumentDB', zone: 'data', icon: 'documentdb' },
  msk: { label: 'MSK (Kafka)', zone: 'data', icon: 'msk' },
  amazon_mq: { label: 'Amazon MQ', zone: 'data', icon: 'amazon_mq' },
  opensearch: { label: 'OpenSearch', zone: 'data', icon: 'opensearch' },
  s3: { label: 'S3', zone: 'regional', icon: 's3' },
  sqs: { label: 'SQS', zone: 'regional', icon: 'sqs' },
  dynamodb: { label: 'DynamoDB', zone: 'regional', icon: 'dynamodb' },
  ecr: { label: 'ECR', zone: 'regional', icon: 'ecr' },
  secrets_manager: { label: 'Secrets Manager', zone: 'regional', icon: 'secrets_manager' },
  cloudwatch: { label: 'CloudWatch', zone: 'regional', icon: 'cloudwatch' },
  vpc: { label: 'VPC', zone: 'frame', icon: 'vpc' }
}

export type NodeInfo = {
  label: string
  /** Official AWS service name, or the raw type for unknown components. */
  service: string
  zone: Zone
  iconSrc: string | null
}

export function describe(component: PlanComponent): NodeInfo {
  const entry = CATALOG[component.type]
  if (!entry) {
    return { label: component.id, service: component.type.replaceAll('_', ' '), zone: 'data', iconSrc: null }
  }
  const icon = entry.icon ? AWS_ICONS[entry.icon] : undefined
  return { label: entry.label, service: icon?.title ?? entry.label, zone: entry.zone, iconSrc: icon?.src ?? null }
}

export const ENTRY_TYPES = new Set(['route53', 'cloudfront', 'api_gateway', 'alb'])

export type Edge = { from: string; to: string; kind: 'request' | 'dependency' }

/**
 * Links drawn on the diagram. Only what the plan states: "B depends on A" is drawn A → B. The
 * VPC is drawn as a frame, so links to it are implied. Users reach the entry components that no
 * other entry component sits in front of.
 */
export function edgesOf(components: PlanComponent[]): Edge[] {
  const byId = new Map(components.map((c) => [c.id, c]))
  const edges: Edge[] = []
  for (const c of components) {
    for (const dep of c.depends_on) {
      const d = byId.get(dep)
      if (!d || d.type === 'vpc' || c.type === 'vpc') continue
      edges.push({ from: d.id, to: c.id, kind: ENTRY_TYPES.has(d.type) ? 'request' : 'dependency' })
    }
  }
  const fedByEntry = new Set(
    edges.filter((e) => ENTRY_TYPES.has(byId.get(e.from)?.type ?? '')).map((e) => e.to)
  )
  for (const c of components) {
    if (ENTRY_TYPES.has(c.type) && !fedByEntry.has(c.id)) edges.push({ from: 'users', to: c.id, kind: 'request' })
  }
  return edges
}
