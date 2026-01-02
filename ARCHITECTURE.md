# Architecture Overview

## Layered Architecture

The application follows a clean **3-tier layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│         (Routers/Controllers)           │
│  - HTTP request/response handling       │
│  - Input validation (Pydantic schemas)  │
│  - Authentication/Authorization         │
│  - Error handling & HTTP status codes   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│         (Services)                      │
│  - Core business logic                  │
│  - Data validation & transformation     │
│  - Transaction management               │
│  - Logging & monitoring                 │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Data Access Layer               │
│         (Database/Models)               │
│  - Raw SQL queries (asyncpg)            │
│  - Connection pooling                   │
│  - Data models (plain Python classes)   │
│  - Database schema management           │
└─────────────────────────────────────────┘
```

## Directory Structure

```
app/
├── core/                   # Core application components
│   ├── config.py          # Configuration settings
│   └── security.py        # Security utilities (JWT, hashing)
│
├── db/                    # Database layer
│   └── database.py        # Connection pool & schema initialization
│
├── users/                 # User module
│   ├── models.py         # User data model
│   ├── schemas.py        # Pydantic schemas for validation
│   ├── service.py        # Business logic (authentication, user management)
│   └── routers.py        # HTTP endpoints (register, login, etc.)
│
├── packages/
│   ├── fintech/          # Fintech module
│   │   ├── models.py     # Transaction data model
│   │   ├── schemas.py    # Pydantic schemas
│   │   ├── service.py    # Business logic (transfers, queries)
│   │   └── routers.py    # HTTP endpoints (transfer, transactions)
│   │
│   └── chat/             # Chat module
│       ├── service.py    # Business logic (messages, rooms)
│       └── routers.py    # HTTP & WebSocket endpoints
│
└── main.py               # Application entry point
```

## Layer Responsibilities

### 1. Routers (Presentation Layer)

**Purpose**: Handle HTTP requests and responses

**Responsibilities**:
- Receive and validate incoming requests
- Call appropriate service layer functions
- Transform service responses to HTTP responses
- Handle HTTP-specific concerns (status codes, headers)
- Manage authentication/authorization at endpoint level

**Example**:
```python
@router.post("/register", response_model=UserOut)
async def register(
    user_data: UserCreate,
    conn: asyncpg.Connection = Depends(get_connection)
):
    try:
        user = await user_service.create_user(
            conn=conn,
            username=user_data.username,
            password=user_data.password
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 2. Services (Business Logic Layer)

**Purpose**: Implement core business logic

**Responsibilities**:
- Execute business rules and validations
- Coordinate database operations
- Manage transactions (ACID compliance)
- Perform data transformations
- Log business events
- Raise domain-specific exceptions

**Example**:
```python
async def create_user(conn: asyncpg.Connection, username: str, password: str) -> User:
    # Business validation
    existing_user = await get_user_by_username(conn, username)
    if existing_user:
        raise ValueError("Username already registered")
    
    # Business logic
    hashed_pwd = hash_password(password)
    
    # Database operation
    record = await conn.fetchrow(
        "INSERT INTO users (...) VALUES (...) RETURNING *",
        username, hashed_pwd, True
    )
    
    return User.from_record(record)
```

### 3. Models & Database (Data Access Layer)

**Purpose**: Represent and persist data

**Responsibilities**:
- Define data structures (models)
- Execute raw SQL queries
- Manage database connections
- Convert database records to Python objects
- Handle database-specific concerns

**Example**:
```python
class User:
    def __init__(self, id: int, username: str, ...):
        self.id = id
        self.username = username
    
    @classmethod
    def from_record(cls, record) -> "User":
        return cls(
            id=record["id"],
            username=record["username"],
            ...
        )
```

## Data Flow

### Request Flow (Example: User Registration)

```
1. HTTP POST /users/register
   ↓
2. Router: register() endpoint
   - Validates request body (Pydantic)
   - Gets database connection
   ↓
3. Service: create_user()
   - Checks if username exists
   - Hashes password
   - Calls database
   ↓
4. Database: Raw SQL INSERT
   - Inserts user record
   - Returns record
   ↓
5. Model: User.from_record()
   - Converts DB record to User object
   ↓
6. Service: Returns User object
   ↓
7. Router: Returns HTTP 201 with UserOut
```

## Key Design Patterns

### 1. Dependency Injection

Used for database connections and authentication:

```python
async def endpoint(
    conn: asyncpg.Connection = Depends(get_connection),
    current_user: User = Depends(get_current_user)
):
    # conn and current_user are injected
    pass
```

### 2. Repository Pattern (Implicit)

Services act as repositories, encapsulating data access:

```python
# Service layer provides clean interface to data
user = await user_service.get_user_by_username(conn, "john")
transactions = await fintech_service.get_user_transactions(conn, user_id)
```

### 3. Factory Pattern

Models use factory methods to create instances from database records:

```python
@classmethod
def from_record(cls, record) -> "User":
    return cls(id=record["id"], username=record["username"], ...)
```

### 4. Transaction Script Pattern

Services implement business logic as transaction scripts:

```python
async with conn.transaction():
    # Multiple operations in a single transaction
    await validate_sender(conn, sender_id)
    await validate_receiver(conn, receiver_id)
    await create_transaction_record(conn, ...)
```

## Benefits of This Architecture

### 1. Separation of Concerns
- Each layer has a single, well-defined responsibility
- Changes in one layer don't affect others
- Easy to understand and maintain

### 2. Testability
- Services can be tested independently
- Mock database connections for unit tests
- Test business logic without HTTP layer

### 3. Reusability
- Service functions can be called from multiple routers
- Business logic is not tied to HTTP
- Can add CLI, gRPC, or other interfaces easily

### 4. Maintainability
- Clear structure makes code easy to navigate
- Business logic is centralized in services
- Database queries are isolated from business logic

### 5. Scalability
- Services can be extracted into microservices
- Database layer can be swapped (e.g., different DB)
- Easy to add caching layer between service and database

## Module Guidelines

### When Creating a New Module

1. **Create the directory structure**:
   ```
   app/packages/mymodule/
   ├── __init__.py
   ├── models.py      # Data models
   ├── schemas.py     # Pydantic schemas
   ├── service.py     # Business logic
   └── routers.py     # HTTP endpoints
   ```

2. **Define the model** (models.py):
   - Plain Python class
   - Type hints for all fields
   - `from_record()` class method

3. **Define schemas** (schemas.py):
   - Pydantic models for request/response
   - Input validation rules

4. **Implement services** (service.py):
   - Business logic functions
   - Accept `conn: asyncpg.Connection` as first parameter
   - Use raw SQL for database operations
   - Raise `ValueError` for business rule violations
   - Log important events

5. **Create routers** (routers.py):
   - HTTP endpoint definitions
   - Use `Depends(get_connection)` for DB access
   - Use `Depends(get_current_user)` for auth
   - Call service layer functions
   - Handle exceptions → HTTP errors

6. **Register router** (main.py):
   ```python
   from app.packages.mymodule.routers import router as mymodule_router
   app.include_router(mymodule_router)
   ```

## Error Handling Strategy

### Service Layer
- Raise `ValueError` for business rule violations
- Raise `asyncpg.PostgresError` for database errors
- Log errors with context

### Router Layer
- Catch `ValueError` → HTTP 400 Bad Request
- Catch database errors → HTTP 500 Internal Server Error
- Catch not found → HTTP 404 Not Found
- Catch authorization failures → HTTP 403 Forbidden

## Testing Strategy

### Unit Tests (Services)
```python
async def test_create_user():
    mock_conn = Mock()
    user = await user_service.create_user(mock_conn, "john", "pass123")
    assert user.username == "john"
```

### Integration Tests (Routers)
```python
async def test_register_endpoint():
    response = await client.post("/users/register", json={...})
    assert response.status_code == 201
```

### End-to-End Tests
```python
async def test_full_transfer_flow():
    # Register users
    # Login
    # Transfer funds
    # Verify transaction
```

## Security Considerations

1. **Authentication**: JWT tokens verified in router layer
2. **Authorization**: Business rules enforced in service layer
3. **SQL Injection**: Parameterized queries prevent injection
4. **Password Security**: Bcrypt hashing in service layer
5. **Input Validation**: Pydantic schemas in router layer

## Performance Considerations

1. **Connection Pooling**: asyncpg pool for efficient connections
2. **Async/Await**: Non-blocking I/O throughout
3. **Pagination**: Limit/offset in query endpoints
4. **Indexes**: Database indexes on frequently queried columns
5. **Transaction Scope**: Keep transactions as short as possible
