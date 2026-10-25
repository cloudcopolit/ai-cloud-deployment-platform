import { redirect } from 'next/navigation'

/* There are no CloudPilot passwords: accounts are created on first GitHub sign-in. */
export default function RegisterPage() {
  redirect('/login')
}
