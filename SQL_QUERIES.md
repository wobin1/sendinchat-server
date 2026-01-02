# Raw SQL Queries Reference

This document contains all the raw SQL queries used in the application for reference and debugging.

## User Queries

### Register User
```sql
INSERT INTO users (username, hashed_password, is_active)
VALUES ($1, $2, $3)
RETURNING id, username, hashed_password, is_active, created_at
```

### Find User by Username
```sql
SELECT id, username, hashed_password, is_active, created_at 
FROM users 
WHERE username = $1
```

### Check Username Exists
```sql
SELECT id 
FROM users 
WHERE username = $1
```

### Get User by ID
```sql
SELECT id, username, hashed_password, is_active, created_at 
FROM users 
WHERE id = $1
```

## Transaction Queries

### Create Transaction
```sql
INSERT INTO transactions (sender_id, receiver_id, amount, status)
VALUES ($1, $2, $3, $4)
RETURNING id, sender_id, receiver_id, amount, status, created_at
```

### Get Transaction by ID
```sql
SELECT id, sender_id, receiver_id, amount, status, created_at
FROM transactions
WHERE id = $1
```

### Get User Transactions (Sent)
```sql
SELECT id, sender_id, receiver_id, amount, status, created_at
FROM transactions
WHERE sender_id = $1
ORDER BY created_at DESC
LIMIT $2 OFFSET $3
```

### Get User Transactions (Received)
```sql
SELECT id, sender_id, receiver_id, amount, status, created_at
FROM transactions
WHERE receiver_id = $1
ORDER BY created_at DESC
LIMIT $2 OFFSET $3
```

### Get All User Transactions
```sql
SELECT id, sender_id, receiver_id, amount, status, created_at
FROM transactions
WHERE sender_id = $1 OR receiver_id = $1
ORDER BY created_at DESC
LIMIT $2 OFFSET $3
```

## Future: Chat Message Queries

### Insert Message (for future implementation)
```sql
INSERT INTO messages (chat_id, sender_id, content)
VALUES ($1, $2, $3)
RETURNING id, chat_id, sender_id, content, created_at
```

### Get Chat Messages (for future implementation)
```sql
SELECT id, chat_id, sender_id, content, created_at
FROM messages
WHERE chat_id = $1
ORDER BY created_at ASC
LIMIT $2 OFFSET $3
```

## Database Maintenance Queries

### Count Users
```sql
SELECT COUNT(*) FROM users
```

### Count Transactions
```sql
SELECT COUNT(*) FROM transactions
```

### Get Transaction Statistics
```sql
SELECT 
    status,
    COUNT(*) as count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount
FROM transactions
GROUP BY status
```

### Get User Transaction Summary
```sql
SELECT 
    u.id,
    u.username,
    COUNT(CASE WHEN t.sender_id = u.id THEN 1 END) as sent_count,
    COUNT(CASE WHEN t.receiver_id = u.id THEN 1 END) as received_count,
    SUM(CASE WHEN t.sender_id = u.id THEN t.amount ELSE 0 END) as total_sent,
    SUM(CASE WHEN t.receiver_id = u.id THEN t.amount ELSE 0 END) as total_received
FROM users u
LEFT JOIN transactions t ON u.id = t.sender_id OR u.id = t.receiver_id
GROUP BY u.id, u.username
```

## Query Parameters

All queries use PostgreSQL's parameterized query syntax with `$1`, `$2`, etc. to prevent SQL injection.

### Example Usage in asyncpg:

```python
# Single row
record = await conn.fetchrow(
    "SELECT * FROM users WHERE username = $1",
    username
)

# Multiple rows
records = await conn.fetch(
    "SELECT * FROM transactions WHERE sender_id = $1 LIMIT $2",
    user_id,
    limit
)

# Execute without return
await conn.execute(
    "INSERT INTO users (username, hashed_password) VALUES ($1, $2)",
    username,
    hashed_password
)
```

## Transaction Blocks

For ACID compliance, wrap multiple queries in a transaction:

```python
async with conn.transaction():
    # All queries here are atomic
    await conn.execute("UPDATE users SET balance = balance - $1 WHERE id = $2", amount, sender_id)
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE id = $2", amount, receiver_id)
    await conn.execute("INSERT INTO transactions (...) VALUES (...)")
    # Automatically commits if no exception, rolls back on error
```
