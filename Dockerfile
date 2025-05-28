# ベースイメージにPythonスリム版を使用
FROM python:3.12-slim

# uvのインストール（pip経由）
RUN pip install --no-cache-dir uv

# 作業ディレクトリ作成
WORKDIR /app

# pyproject.toml と uv.lock をコピー（依存関係のインストール用）
COPY pyproject.toml uv.lock ./

COPY translations/ ./translations/

# 依存関係のインストール（--production で本番依存のみに絞れる）
RUN uv sync

# ソースコードをコピー
COPY src/ ./src/

# エントリーポイントを指定
CMD ["uv", "run", "python", "src/main.py"]
