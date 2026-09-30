# uis/backoffice/Dockerfile — Panel admin Brasaland
FROM node:22-alpine

WORKDIR /app/uis/backoffice

# Copiar package.json e instalar dependencias en build time
COPY package.json ./
RUN npm install --no-audit --no-fund

# Exponer puerto de desarrollo
EXPOSE 3001

CMD ["npm", "run", "dev", "--", "-p", "3001"]