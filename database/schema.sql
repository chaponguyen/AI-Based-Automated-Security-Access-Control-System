-- Tài liệu tham khảo. Nguồn chính: backend/database/models.py + Alembic.
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  full_name VARCHAR(150) NOT NULL,
  age INTEGER NOT NULL,
  apartment_number VARCHAR(20) NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  created_at TIMESTAMP DEFAULT now()
);
CREATE TABLE face_embeddings (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  embedding FLOAT[] NOT NULL,
  quality FLOAT,
  model_version VARCHAR(30) NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);
CREATE TABLE access_logs (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  similarity FLOAT,
  liveness BOOLEAN,
  decision VARCHAR(10) NOT NULL,
  reason VARCHAR(80),
  timestamp TIMESTAMP DEFAULT now()
);
