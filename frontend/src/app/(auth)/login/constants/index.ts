import { FileText, Layers, SlidersHorizontal, Terminal } from 'lucide-react'

export const permissions = [
  {
    title: 'Read Repository Information',
    desc: 'Access repository names, branches, and project directory structure.',
    icon: FileText
  },
  {
    title: 'Inspect Source Code',
    desc: 'Analyze application files, dependencies, frameworks, and build configurations.',
    icon: Terminal
  },
  {
    title: 'Access Deployment Configuration',
    desc: 'Read the files required to understand and prepare the deployment process.',
    icon: Layers
  },
  {
    title: 'Repository Access Control',
    desc: 'Allow users to select which repositories CloudPilot can access, where supported by GitHub.',
    icon: SlidersHorizontal
  }
]
