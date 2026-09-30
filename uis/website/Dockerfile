# uis/website/Dockerfile — Frontend público Brasaland
FROM node:22-alpine

WORKDIR /app

# Copiar package.json e instalar dependencias en build time
COPY package.json ./
RUN npm install --no-audit --no-fund

# Exponer puerto de desarrollo
EXPOSE 3000

CMD ["npm", "run", "dev", "--", "-p", "3000"]