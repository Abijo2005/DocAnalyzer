# Stage 1: Compile React TypeScript assets
FROM node:20-alpine AS build-stage

WORKDIR /app

# Copy package descriptors and install packages
COPY package*.json ./
RUN npm install

# Copy source assets
COPY . .

# Set default API endpoint during build time
# Browsers will call backend running on host port 8000
ENV VITE_API_BASE_URL=http://localhost:8000/api/v1

RUN npm run build

# Stage 2: Expose static distribution via Nginx
FROM nginx:alpine

# Copy compiled assets from Stage 1
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Overwrite default Nginx routing rules
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
