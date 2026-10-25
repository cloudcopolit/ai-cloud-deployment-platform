import type { AgentTask } from '@/lib/api/schemas'

type SpriteName = `ui-${string}`

export type StepCopy = {
  /** Before it runs ("Read the repository"). */
  planned: string
  /** While it runs, shown with a shimmer ("Reading the repository"). */
  running: string
  /** After it ran ("Read the repository"). */
  done: string
  icon: SpriteName
}

/* The Analysis agent's steps in the order ai/src/cloudpilot_ai/analysis/agent.py runs them. */
export const ANALYSIS_PLAN = [
  'read_repository',
  'detect_languages_and_frameworks',
  'detect_containers_and_config',
  'detect_env_ports_health',
  'scan_for_secrets',
  'resolve_ambiguity_with_llm',
  'assemble_report'
] as const

/** Steps an agent is known to run, so pending ones can be listed before they start. */
export const AGENT_PLANS: Record<string, readonly string[]> = { ANALYSIS: ANALYSIS_PLAN }

const COPY: Record<string, StepCopy> = {
  read_repository: {
    planned: 'Read the repository',
    running: 'Reading the repository',
    done: 'Read the repository',
    icon: 'ui-folder'
  },
  detect_languages_and_frameworks: {
    planned: 'Detect languages and frameworks',
    running: 'Detecting languages and frameworks',
    done: 'Detected languages and frameworks',
    icon: 'ui-file-code'
  },
  detect_containers_and_config: {
    planned: 'Inspect Dockerfiles, Compose and config',
    running: 'Inspecting Dockerfiles, Compose and config',
    done: 'Inspected Dockerfiles, Compose and config',
    icon: 'ui-box'
  },
  detect_env_ports_health: {
    planned: 'Find ports, env variables and health routes',
    running: 'Finding ports, env variables and health routes',
    done: 'Found ports, env variables and health routes',
    icon: 'ui-network'
  },
  scan_for_secrets: {
    planned: 'Scan for committed secrets',
    running: 'Scanning for committed secrets',
    done: 'Scanned for committed secrets',
    icon: 'ui-key'
  },
  resolve_ambiguity_with_llm: {
    planned: 'Ask a language model about anything ambiguous',
    running: 'Asking a language model about ambiguities',
    done: 'Asked a language model about ambiguities',
    icon: 'ui-sparkles'
  },
  assemble_report: {
    planned: 'Assemble and validate the report',
    running: 'Assembling and validating the report',
    done: 'Assembled and validated the report',
    icon: 'ui-checklist'
  }
}

export function stepCopy(taskType: string): StepCopy {
  const words = taskType.replaceAll('_', ' ')
  const label = words.charAt(0).toUpperCase() + words.slice(1)
  return COPY[taskType] ?? { planned: label, running: label, done: label, icon: 'ui-workflow' }
}

const n = (v: unknown) => (typeof v === 'number' ? v : null)
const plural = (count: number, word: string, many = `${word}s`) => `${count} ${count === 1 ? word : many}`
const list = (v: unknown) => (Array.isArray(v) ? v.map(String) : [])

/**
 * One readable line from a step's output summary (server data, rendered as plain text).
 * Unknown shapes fall back to "key: value" pairs so nothing the agent reported is hidden.
 */
export function summarizeStep(task: Pick<AgentTask, 'task_type' | 'status' | 'output'>): string | null {
  const o = task.output
  if (!o || Object.keys(o).length === 0) return null
  if (task.status === 'SKIPPED' && typeof o.reason === 'string') return `Skipped: ${o.reason}`
  const parts: string[] = []
  switch (task.task_type) {
    case 'read_repository': {
      const listed = n(o.files_listed)
      const read = n(o.files_read)
      if (listed !== null) parts.push(`Listed ${plural(listed, 'file')}`)
      if (read !== null) parts.push(`read ${read}`)
      if (n(o.unreadable)) parts.push(`${o.unreadable} unreadable`)
      if (o.truncated === true) parts.push('listing truncated')
      return parts.join(', ')
    }
    case 'detect_languages_and_frameworks': {
      const fw = list(o.frameworks)
      parts.push(fw.length ? fw.join(', ') : 'No framework detected')
      if (n(o.dependencies) !== null) parts.push(plural(n(o.dependencies)!, 'dependency', 'dependencies'))
      if (n(o.service_candidates) !== null) parts.push(plural(n(o.service_candidates)!, 'service candidate'))
      return parts.join(' · ')
    }
    case 'detect_containers_and_config': {
      if (n(o.dockerfiles) !== null) parts.push(plural(n(o.dockerfiles)!, 'Dockerfile'))
      if (n(o.config_files) !== null) parts.push(plural(n(o.config_files)!, 'config file'))
      const stores = list(o.data_stores)
      parts.push(stores.length ? `data stores: ${stores.join(', ')}` : 'no data stores')
      return parts.join(' · ')
    }
    case 'detect_env_ports_health': {
      if (n(o.ports_found) !== null) parts.push(plural(n(o.ports_found)!, 'port'))
      if (n(o.env_var_names) !== null) parts.push(plural(n(o.env_var_names)!, 'env variable name'))
      if (n(o.health_routes) !== null) parts.push(plural(n(o.health_routes)!, 'health route'))
      return parts.join(' · ')
    }
    case 'scan_for_secrets': {
      const found = n(o.possible_secrets)
      if (found === null) break
      return found === 0 ? 'No committed secrets found' : `${plural(found, 'possible secret')} (file and kind only)`
    }
    case 'assemble_report': {
      if (n(o.services) !== null) parts.push(plural(n(o.services)!, 'service'))
      if (n(o.blockers) !== null) parts.push(plural(n(o.blockers)!, 'blocker'))
      if (n(o.warnings) !== null) parts.push(plural(n(o.warnings)!, 'warning'))
      if (n(o.missing_info)) parts.push(plural(n(o.missing_info)!, 'question') + ' for you')
      if (typeof o.recommendation === 'string') parts.push(`recommends ${o.recommendation.replaceAll('_', ' ')}`)
      return parts.join(' · ')
    }
  }
  return Object.entries(o)
    .filter(([, v]) => v !== null && v !== undefined && typeof v !== 'object')
    .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${String(v)}`)
    .join(' · ')
}
