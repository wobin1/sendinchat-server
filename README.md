# SendInChat Backend API

A high-performance, secure, and reusable Fintech/Chat application backend built with FastAPI, PostgreSQL, and async/await patterns.

## Features

- **User Authentication**: JWT-based authentication with bcrypt password hashing
- **P2P Fund Transfers**: Secure transaction processing with ACID guarantees
- **Real-time Chat**: WebSocket support for instant messaging
- **Async/Await**: Full async support for high performance
- **Type Safety**: Pydantic schemas for request/response validation
- **Layered Architecture**: Clean separation with routers, services, and data layers

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with asyncpg (raw SQL queries)
- **Authentication**: JWT (python-jose) + bcrypt
- **Server**: Uvicorn
- **Connection Pooling**: asyncpg connection pool

## Project Structure

```
sendinchat-server/
├── app/
│   ├── core/
│   │   ├── config.py          # Application settings
│   │   └── security.py        # Password hashing & JWT
│   ├── db/
│   │   └── database.py        # asyncpg connection pool & raw SQL
│   ├── users/
│   │   ├── models.py          # User model
│   │   ├── schemas.py         # User schemas
│   │   ├── service.py         # Business logic
│   │   └── routers.py         # Auth endpoints
│   ├── packages/
│   │   ├── fintech/
│   │   │   ├── models.py      # Transaction model
│   │   │   ├── schemas.py     # Transfer schemas
│   │   │   ├── service.py     # Business logic
│   │   │   └── routers.py     # Fintech endpoints
│   │   └── chat/
│   │       ├── service.py     # Business logic
│   │       └── routers.py     # Chat & WebSocket endpoints
│   └── main.py                # Application entry point
├── requirements.txt
├── schema.sql             # Database schema reference
└── .env.example
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/sendinchat
SECRET_KEY=your-secret-key-here
```

### 3. Setup Database

Create a PostgreSQL database:

```bash
createdb sendinchat
```

### 4. Run the Application

```bash
# From the sendinchat-server directory
python -m uvicorn app.main:app --reload

# Or run directly
python app/main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /users/register` - Register a new user
- `POST /users/token` - Login and get JWT token
- `GET /users/me` - Get current user info

### Fintech
- `POST /fintech/transfer` - Execute P2P fund transfer (requires auth)
- `GET /fintech/transactions` - Get all user transactions (requires auth)
- `GET /fintech/transactions/sent` - Get sent transactions (requires auth)
- `GET /fintech/transactions/received` - Get received transactions (requires auth)
- `GET /fintech/transactions/{id}` - Get specific transaction (requires auth)

### Chat
- `POST /chat/send_message` - Send a text message (requires auth)
- `GET /chat/messages/{chat_id}` - Get chat messages (requires auth)
- `POST /chat/create_room` - Create a chat room (requires auth)
- `WS /chat/ws/{chat_id}` - WebSocket connection for real-time chat

## Usage Examples

### 1. Register a User

```bash
curl -X POST "http://localhost:8000/users/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "john_doe", "password": "secure123"}'
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/users/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john_doe&password=secure123"
```

### 3. Transfer Funds

```bash
curl -X POST "http://localhost:8000/fintech/transfer" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sender_id": 1, "receiver_id": 2, "amount": 100.50}'
```

### 4. WebSocket Chat

```javascript
const ws = new WebSocket('ws://localhost:8000/chat/ws/1');
ws.onmessage = (event) => console.log(JSON.parse(event.data));
ws.send('Hello, World!');
```

## Development Notes

### Database Schema

This MVP uses raw SQL with asyncpg. The schema is automatically created on startup via `init_db()`. 

For reference, see `schema.sql` which contains the complete database schema with indexes and constraints.

To manually create the schema:
```bash
psql -d sendinchat -f schema.sql
```

### Security Considerations

- Change `SECRET_KEY` in production (use `openssl rand -hex 32`)
- Update CORS origins in `main.py` to specific domains
- Use environment variables for all sensitive data
- Implement rate limiting for production
- Add input validation and sanitization

### Testing

To add tests, install pytest:

```bash
pip install pytest pytest-asyncio httpx
```

## MVP Limitations

This is an MVP implementation with the following limitations:

1. **Fintech**: Transaction processing is a dummy implementation (logs only)
2. **Chat**: Messages are not persisted to database
3. **WebSocket**: No authentication on WebSocket connections
4. **Balance**: No user balance tracking
5. **Validation**: Minimal business logic validation

## Next Steps

- [ ] Implement actual payment processing
- [ ] Add chat message persistence
- [ ] Implement WebSocket authentication
- [ ] Add user balance management
- [ ] Create comprehensive test suite
- [ ] Add API rate limiting
- [ ] Implement database migrations (e.g., with custom SQL scripts)
- [ ] Add logging and monitoring
- [ ] Deploy to production environment
- [ ] Add connection pool monitoring and health checks

## License

MIT
