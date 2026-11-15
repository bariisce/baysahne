# Admin panel (Next.js standalone output).
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Origin that serves media (API in local-storage mode, or the S3/CDN public URL). Baked into the CSP header.
ARG MEDIA_PUBLIC_ORIGIN=""
# Where /api and /media are proxied. Next.js resolves rewrites at BUILD time, so this is a build arg.
ARG BACKEND_INTERNAL_URL=http://api:8100
ENV MEDIA_PUBLIC_ORIGIN=$MEDIA_PUBLIC_ORIGIN BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3100 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3100
CMD ["node", "server.js"]
