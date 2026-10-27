# Frontend image. Stages:
#   deps    - all dependencies from the frozen lockfile
#   dev     - source + `next dev` (docker-compose.dev.yml mounts the source over it)
#   test    - source + `vitest run` (docker-compose.test.yml)
#   build   - production build; NEXT_PUBLIC_API_URL is inlined here
#   runtime - production dependencies + build output, runs as `node` (default target)
# Every stage that runs project code runs as the image's `node` user (uid 1000), never as root.

FROM node:24-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS base

ENV NEXT_TELEMETRY_DISABLED=1
# Same pnpm version as `packageManager` in package.json.
RUN npm install --global pnpm@12.4.1 && npm cache clean --force
WORKDIR /app


FROM base AS deps

# 1000 = the image's node user
RUN chown 1000:1000 /app
USER 1000
COPY --chown=1000:1000 package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile


FROM deps AS dev

COPY --chown=1000:1000 . .
EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]


FROM deps AS test

COPY --chown=1000:1000 . .
CMD ["pnpm", "test"]


FROM deps AS build

COPY --chown=1000:1000 . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN pnpm build


FROM base AS runtime

ENV NODE_ENV=production
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# pnpm skips an optional package whose download fails, and Next.js then tries to fetch its
# compiler into the read-only node_modules at start-up and hangs. Fail the build instead.
RUN pnpm install --frozen-lockfile --prod \
    && ls -d node_modules/.pnpm/@next+swc-* > /dev/null
COPY next.config.ts ./
COPY --from=build /app/public ./public
COPY --from=build --chown=1000:1000 /app/.next ./.next

USER 1000
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "--hostname", "0.0.0.0"]
