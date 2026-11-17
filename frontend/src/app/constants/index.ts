import {
  Activity,
  Cpu,
  GitBranch,
  Server,
  Terminal,
  Layers,
  Shield,
  FileText,
  Users
} from 'lucide-react'

export const steps = [
  {
    step: '01',
    title: 'Connect GitHub',
    desc: 'Select your existing repository and branch with one click.',
    icon: GitBranch
  },
  {
    step: '02',
    title: 'AI Analyzes',
    desc: 'Specialized agents understand your application and runtime dependencies.',
    icon: Cpu
  },
  {
    step: '03',
    title: 'Provision & Deploy',
    desc: 'Review your AWS architecture and deploy securely using Terraform and Ansible.',
    icon: Server
  },
  {
    step: '04',
    title: 'Monitor & Heal',
    desc: 'Detect incidents, diagnose failures, and recover infrastructure automatically.',
    icon: Activity
  }
]

export const features = [
  {
    title: 'Intelligent Code Analysis',
    desc: 'Automatically detect frameworks, dependencies, ports, environment configurations, and application requirements without manual setup files.',
    icon: Terminal
  },
  {
    title: 'Automated AWS Infrastructure',
    desc: 'Generate secure, scalable production infrastructure using battle-tested Terraform modules and Ansible playbooks tailored to your stack.',
    icon: Layers
  },
  {
    title: 'Real-Time Monitoring',
    desc: 'Track application health, performance bottlenecks, container logs, and cloud resource metrics from a unified developer dashboard.',
    icon: Activity
  },
  {
    title: 'AI Self-Healing',
    desc: 'Diagnose unexpected production incidents and execute safe recovery actions autonomously, with optional human approval workflows.',
    icon: Cpu
  }
]

export const controls = [
  {
    title: 'Secure AWS Access',
    desc: 'Role-based access control and least-privilege IAM permissions ensure your AWS environment remains fully secured.',
    icon: Shield
  },
  {
    title: 'Human-in-the-Loop',
    desc: 'Sensitive infrastructure changes, scaling limits, and destructive updates always require explicit team member approval.',
    icon: Users
  },
  {
    title: 'Transparent Operations',
    desc: 'Review every generated infrastructure plan, deployment log, and AI-driven recovery action before and after execution.',
    icon: FileText
  }
]
