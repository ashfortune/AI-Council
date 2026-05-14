# Base image
FROM node:20-slim AS base

WORKDIR /app

# Dependencies install
COPY package*.json ./
RUN npm install

# Source copy and build
COPY . .
RUN npm run build

# Production run stage
EXPOSE 3000
CMD ["npm", "run", "start"]
