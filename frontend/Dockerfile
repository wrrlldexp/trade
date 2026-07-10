FROM node:20-alpine

WORKDIR /app

# Сначала только манифесты для кеша слоя зависимостей
COPY package.json package-lock.json* ./
RUN npm install

# Потом весь код
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
