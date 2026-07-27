FROM node:22-alpine

ARG NPM_REGISTRY

WORKDIR /website

COPY package.json package-lock.json ./
RUN if [ -n "${NPM_REGISTRY}" ]; then npm config set registry "${NPM_REGISTRY}"; fi
RUN npm ci

COPY . ./
RUN npm run build
