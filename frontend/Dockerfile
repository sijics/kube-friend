# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Build the React app into static files (HTML, CSS, JS).
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first — same Docker layer caching trick as the backend.
# npm ci only re-runs when package.json or package-lock.json changes.
COPY package.json package-lock.json* ./
RUN npm ci

# Copy the rest of the source and build
COPY . .
RUN npm run build
# Output: /app/dist/ — a folder of static HTML/CSS/JS files

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Use nginx to serve the static files. nginx is tiny and purpose-built for this.
FROM nginx:alpine

# Copy our custom nginx config (handles /api proxy + React Router fallback)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built static files from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
