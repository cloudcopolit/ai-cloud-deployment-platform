import { redirect } from 'next/navigation'

/* The proxy sends signed-out visitors of /dashboard to /login. */
export default function Home() {
  redirect('/dashboard')
}
