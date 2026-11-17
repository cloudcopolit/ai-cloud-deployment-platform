import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // Note: Depending on how your backend routes are structured,
        // you might need to append '/api' to the destination like this:
        // destination: `${process.env.BACKEND_API_URL}/api/:path*`
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`
      }
    ]
  },
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      '*.css': {
        loaders: ['@tailwindcss/turbopack'],
        as: '*.css'
      }
    }
  }
}

export default nextConfig
