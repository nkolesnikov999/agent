# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requrements.txt

# Открываем порт (если нужен веб-сервер, например http.server)
EXPOSE 8043

# Команда запуска по умолчанию (замени на своё при необходимости)
CMD ["python", "main.py"]