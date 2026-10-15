# Frontend image. Stages:
#   deps    - all dependencies from the frozen lockfile
#   dev     - source + `next dev` (docker-compose.dev.yml mounts the source over it)
#   test    - source + `vitest run` (docker-compose.test.yml)
#   build   - production build; NEXT_PUBLIC_API_URL is inlined here
#   runtime - production dependencies + build output, runs as `node` (default target)

FROM node:24-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS base

ENV NEXT_TELEMETRY_DISABLED=1
# Same pnpm version as `packageManager` in package.json.
RUN npm install --global pnpm@12.4.1 && npm cache clean --force
WORKDIR /app


FROM base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile


FROM deps AS dev

COPY . .
EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]


FROM deps AS test

COPY . .
CMD ["pnpm", "test"]


FROM deps AS build

COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN pnpm build


FROM base AS runtime

ENV NODE_ENV=production
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --prod
COPY next.config.ts ./
COPY --from=build /app/public ./public
COPY --from=build --chown=1000:1000 /app/.next ./.next

USER 1000
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "--hostname", "0.0.0.0"]
