# Application Layers Diagram

## Complete Request Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT                                   │
│                    (Browser/Mobile App)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP Request
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                           │
│                        (Routers)                                 │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   users/     │  │  fintech/    │  │   chat/      │         │
│  │ routers.py   │  │ routers.py   │  │ routers.py   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  Responsibilities:                                               │
│  • Receive HTTP requests                                        │
│  • Validate input (Pydantic schemas)                            │
│  • Handle authentication/authorization                          │
│  • Call service layer                                           │
│  • Transform responses to HTTP                                  │
│  • Map exceptions to HTTP status codes                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Function Call
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                          │
│                        (Services)                                │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   users/     │  │  fintech/    │  │   chat/      │         │
│  │ service.py   │  │ service.py   │  │ service.py   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  Responsibilities:                                               │
│  • Implement business rules                                     │
│  • Validate business logic                                      │
│  • Coordinate database operations                               │
│  • Manage transactions (ACID)                                   │
│  • Transform data                                               │
│  • Log business events                                          │
│  • Raise domain exceptions                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQL Query
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                           │
│                    (Database + Models)                           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   users/     │  │  fintech/    │  │     db/      │         │
│  │  models.py   │  │  models.py   │  │ database.py  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  Responsibilities:                                               │
│  • Execute raw SQL queries                                      │
│  • Manage connection pool                                       │
│  • Define data models                                           │
│  • Convert DB records to objects                                │
│  • Handle database-specific concerns                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ TCP Connection
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       PostgreSQL Database                        │
│                                                                  │
│  Tables: users, transactions                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure (Example: Users)

```
app/users/
│
├── models.py           ┌─────────────────────────────────┐
│                       │ class User:                      │
│                       │   def __init__(...)              │
│                       │   @classmethod                   │
│                       │   def from_record(record)        │
│                       └─────────────────────────────────┘
│
├── schemas.py          ┌─────────────────────────────────┐
│                       │ class UserCreate(BaseModel):     │
│                       │   username: str                  │
│                       │   password: str                  │
│                       │                                  │
│                       │ class UserOut(BaseModel):        │
│                       │   id: int                        │
│                       │   username: str                  │
│                       └─────────────────────────────────┘
│
├── service.py          ┌─────────────────────────────────┐
│                       │ async def create_user(...)       │
│                       │ async def get_user_by_id(...)    │
│                       │ async def authenticate_user(...) │
│                       │ async def update_password(...)   │
│                       └─────────────────────────────────┘
│
└── routers.py          ┌─────────────────────────────────┐
                        │ @router.post("/register")        │
                        │ @router.post("/token")           │
                        │ @router.get("/me")               │
                        └─────────────────────────────────┘
```

## Data Flow Example: User Registration

```
1. Client
   │
   │ POST /users/register
   │ {"username": "john", "password": "secret"}
   │
   ↓
2. Router (routers.py)
   │
   │ • Validates input with UserCreate schema
   │ • Gets database connection
   │ • Calls service layer
   │
   ↓
3. Service (service.py)
   │
   │ • Checks if username exists
   │ • Hashes password
   │ • Calls database
   │
   ↓
4. Database (database.py)
   │
   │ • Executes: INSERT INTO users (...)
   │ • Returns record
   │
   ↓
5. Model (models.py)
   │
   │ • User.from_record(record)
   │ • Creates User object
   │
   ↓
6. Service (service.py)
   │
   │ • Logs event
   │ • Returns User object
   │
   ↓
7. Router (routers.py)
   │
   │ • Converts User to UserOut schema
   │ • Returns HTTP 201 with JSON
   │
   ↓
8. Client
   │
   │ Receives: {"id": 1, "username": "john", "is_active": true}
```

## Cross-Cutting Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                    CROSS-CUTTING CONCERNS                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Security   │  │   Logging    │  │   Config     │         │
│  │ security.py  │  │   (logger)   │  │  config.py   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  • JWT token generation/verification                            │
│  • Password hashing (bcrypt)                                    │
│  • Application configuration                                    │
│  • Structured logging                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Dependency Flow

```
main.py
  │
  ├─→ users/routers.py
  │     │
  │     ├─→ users/service.py
  │     │     │
  │     │     ├─→ users/models.py
  │     │     ├─→ db/database.py
  │     │     └─→ core/security.py
  │     │
  │     └─→ users/schemas.py
  │
  ├─→ fintech/routers.py
  │     │
  │     ├─→ fintech/service.py
  │     │     │
  │     │     ├─→ fintech/models.py
  │     │     └─→ db/database.py
  │     │
  │     └─→ fintech/schemas.py
  │
  └─→ chat/routers.py
        │
        ├─→ chat/service.py
        │     │
        │     └─→ db/database.py
        │
        └─→ (no schemas yet)
```

## Communication Patterns

### Synchronous (HTTP REST)
```
Client → Router → Service → Database → Service → Router → Client
```

### Asynchronous (WebSocket)
```
Client ←→ WebSocket Handler ←→ In-Memory Store
                                      ↓
                                  Service
                                      ↓
                                  Database
```

## Error Flow

```
Database Error
  │
  ↓
Service Layer
  │ Catches DB error
  │ Logs error
  │ Raises ValueError or re-raises
  │
  ↓
Router Layer
  │ Catches ValueError → HTTP 400
  │ Catches DB error → HTTP 500
  │ Catches NotFound → HTTP 404
  │
  ↓
Client
  │ Receives HTTP error response
  │ {"detail": "Error message"}
```

## Key Principles

1. **Single Responsibility**: Each layer has one job
2. **Dependency Rule**: Dependencies point inward (router → service → database)
3. **Separation of Concerns**: HTTP, business logic, and data access are separate
4. **Testability**: Each layer can be tested independently
5. **Reusability**: Service functions can be called from anywhere
6. **Maintainability**: Clear structure, easy to navigate and modify
