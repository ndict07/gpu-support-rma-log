# GPU Support RMA Log GUI

カスタマーサポート向けの社内用ログ管理WEB GUIです。

このMVPは、Googleスプレッドシートで管理している台帳情報とは重複管理せず、RMA番号に紐づくテキストログだけを保存・検索します。

## Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

ブラウザで `http://localhost:5173` を開きます。

WSLからまとめて起動する場合:

```bash
bash scripts/start-backend.sh
bash scripts/start-frontend.sh
```

## API

- `POST /rma-threads`
- `GET /board?rma=RMA-001&rma_match=partial&keyword=artifact`
- `GET /rma-threads?rma=RMA-001&rma_match=partial&keyword=artifact`
- `GET /rma-threads/{rma_number}`
- `PATCH /rma-threads/{rma_number}`
- `DELETE /rma-threads/{rma_number}`
- `GET /rma-threads/{rma_number}/messages`
- `POST /rma-threads/{rma_number}/messages`
- `PATCH /messages/{message_id}`
- `DELETE /messages/{message_id}`

`POST /rma-threads/{rma_number}/messages` は `multipart/form-data` です。
`type`、`content`、任意の `attachment` を送れます。添付は画像または動画のみ対応し、ファイル本体は `backend/uploads` に保存されます。
