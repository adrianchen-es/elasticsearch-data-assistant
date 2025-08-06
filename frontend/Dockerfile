## Frontend
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./
#RUN npm install -D compression-webpack-plugin terser-webpack-plugin
RUN npm install -D compression-webpack-plugin

# Copy source code
COPY . .

# Build the app
RUN npm install -D compression-webpack-plugin terser-webpack-plugin
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built app
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]