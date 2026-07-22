FROM node:20.20.2-bookworm-slim AS dependencies

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:20.20.2-bookworm-slim AS build

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app/apps/web

COPY --from=dependencies /app/apps/web/node_modules ./node_modules
COPY apps/web ./

ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

RUN npm run build

FROM node:20.20.2-bookworm-slim AS runtime

ENV HOSTNAME=0.0.0.0 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

WORKDIR /app

RUN groupadd --system --gid 10001 nextjs \
    && useradd --system --uid 10001 --gid nextjs --home-dir /app --shell /usr/sbin/nologin nextjs

COPY --from=build --chown=nextjs:nextjs /app/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nextjs /app/apps/web/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "const port=process.env.PORT||3000; fetch('http://127.0.0.1:'+port+'/health').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
