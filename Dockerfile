FROM node:26-bookworm AS web
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi 'uvicorn[standard]' sqlalchemy pydantic
COPY backend ./backend
COPY --from=web /src/frontend/dist ./frontend_dist
EXPOSE 8000
CMD ["uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8000"]
