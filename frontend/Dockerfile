FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY proxy.inc /etc/nginx/proxy.inc
COPY --from=build /app/dist /usr/share/nginx/html
