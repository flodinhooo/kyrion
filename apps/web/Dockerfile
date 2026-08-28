FROM node:22-alpine AS dependencies

WORKDIR /workspace
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS build

WORKDIR /workspace
RUN corepack enable
COPY --from=dependencies /workspace/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN addgroup --system --gid 10001 kyrion \
    && adduser --system --uid 10001 --ingroup kyrion kyrion

COPY --from=build --chown=kyrion:kyrion /workspace/public ./public
COPY --from=build --chown=kyrion:kyrion /workspace/.next/standalone ./
COPY --from=build --chown=kyrion:kyrion /workspace/.next/static ./.next/static

USER kyrion
EXPOSE 3000
CMD ["node", "server.js"]
