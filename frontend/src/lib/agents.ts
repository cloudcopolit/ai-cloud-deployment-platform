import type { CapabilityLevel } from '@/components/app/states'

export type AgentKey = 'ORCHESTRATOR' | 'ANALYSIS' | 'ARCHITECTURE' | 'DEPLOYMENT'

export type AgentProfile = {
  key: AgentKey
  name: string
  /** One line: what it is for. */
  tagline: string
  avatar: string
  does: string[]
  never: string[]
  /** How real this agent is in this build (kept in step with WORKLOG.md). */
  level: CapabilityLevel
  levelNote: string
  /** Deployment is deliberately not an AI agent: language models never change infrastructure. */
  isAi: boolean
}

/* The roster from project_context/06-ai-orchestration.md, plus the deterministic deployment engine. */
export const AGENTS: Record<AgentKey, AgentProfile> = {
  ORCHESTRATOR: {
    key: 'ORCHESTRATOR',
    name: 'Orchestrator',
    tagline: 'Runs the workflow and checks every result.',
    avatar: '/icons/agents/orchestrator.svg',
    does: [
      'Decides which agent runs next',
      'Validates each output against a strict schema',
      'Enforces time limits, retries and cancellation'
    ],
    never: ['Reads repository code itself', 'Makes architecture choices'],
    level: 'REAL',
    levelNote: 'LangGraph state machine run by the background worker.',
    isAi: false
  },
  ANALYSIS: {
    key: 'ANALYSIS',
    name: 'Analysis agent',
    tagline: 'Reads the repository and explains what it found.',
    avatar: '/icons/agents/code-analyzer.svg',
    does: [
      'Detects languages, frameworks, services and ports',
      'Finds databases, caches, queues and env variable names',
      'Reports committed secrets by path and kind, never the value',
      'Asks you when something is ambiguous'
    ],
    never: ['Runs code from your repository', 'Follows instructions written inside your repository'],
    level: 'REAL',
    levelNote:
      'Deterministic detectors on real GitHub content. The language-model step stays MOCKED-ONLY until an API key is configured.',
    isAi: true
  },
  ARCHITECTURE: {
    key: 'ARCHITECTURE',
    name: 'Architect agent',
    tagline: 'Proposes an AWS architecture with reasons, risks and cost.',
    avatar: '/icons/agents/architect.svg',
    does: [
      'Chooses AWS services for each detected component',
      'Explains every component, assumption and risk',
      'Estimates the monthly cost'
    ],
    never: ['Writes Terraform', 'Approves or deploys anything'],
    level: 'SIMULATED',
    levelNote:
      'Prototype: a fixed container-on-ECS template with illustrative costs. The real agent (pattern catalog, AWS Price List costs) is WORKLOG slice S4.',
    isAi: true
  },
  DEPLOYMENT: {
    key: 'DEPLOYMENT',
    name: 'Deployment engine',
    tagline: 'Applies an approved plan, step by step.',
    avatar: '/icons/agents/deployment.svg',
    does: [
      'Renders Terraform from a fixed, reviewed module library',
      'Shows the plan and cost change before approval',
      'Applies only the exact plan an ADMIN or OWNER approved'
    ],
    never: ['Uses a language model', 'Stores long-lived AWS credentials'],
    level: 'MISSING',
    levelNote: 'Designed (WORKLOG slice S5), not built yet.',
    isAi: false
  }
}

export const AGENT_ORDER: AgentKey[] = ['ORCHESTRATOR', 'ANALYSIS', 'ARCHITECTURE', 'DEPLOYMENT']

export function agentFor(type: string): AgentProfile | undefined {
  return (AGENTS as Record<string, AgentProfile>)[type]
}
