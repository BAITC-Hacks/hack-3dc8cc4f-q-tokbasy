# Career Quest

Career Quest is an iteration-one HR career development dashboard. It uses the
provided synthetic employee, skill, event, and activity datasets to present a
searchable team directory and employee development profiles.

## Run the backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn main:app --app-dir backend --reload
```

The API is available at `http://localhost:8000`; interactive documentation is
at `http://localhost:8000/docs`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. To use a different API address, set
`VITE_API_URL` in a local `.env` file.

## API endpoints

- `GET /health`
- `GET /api/employees`
- `GET /api/employees/{employee_id}`
- `GET /api/events`
- `GET /api/skills`
