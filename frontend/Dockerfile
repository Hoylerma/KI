# --- Stage 1: Build ---
FROM node:20-alpine AS build-stage
WORKDIR /app

# Abhängigkeiten kopieren und installieren
COPY package*.json ./
RUN npm install

# Gesamten Code kopieren und die App bauen
COPY . .
RUN npm run build

# --- Stage 2: Production ---
FROM nginx:stable-alpine
# Die gebauten Dateien von Stage 1 in den Nginx-Web-Ordner kopieren
COPY --from=build-stage /app/dist /usr/share/nginx/html


EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
