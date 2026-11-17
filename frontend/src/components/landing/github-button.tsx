import React from 'react'
import { Button } from '../ui/button'
import Link from 'next/link'
import Image from 'next/image'
import githubIcon from '@/../public/icons/brands/github.svg'
function GithubButton({ buttonClass, iconClass }: { buttonClass?: string; iconClass?: string }) {
  return (
    <Button className={` ${buttonClass}`} asChild>
      <Link href="/login">
        Log in <span className="hidden md:block"> with Github</span>
        <Image
          src={githubIcon}
          width={20}
          height={20}
          alt="github icon"
          className={`invert dark:invert ${iconClass}`}
        />
      </Link>
    </Button>
  )
}

export default GithubButton
