
async def create_tables(conn):
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            phone TEXT NOT NULL,
            username TEXT,
            region TEXT,
            city TEXT
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            worker_id BIGINT PRIMARY KEY,
            phone TEXT NOT NULL,
            username TEXT,
            name TEXT,
            region TEXT,
            city TEXT,
            profession TEXT,
            approved BOOLEAN DEFAULT FALSE
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id BIGINT PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            username TEXT,
            name TEXT,
            region TEXT,
            city TEXT,
            service TEXT,
            description TEXT,
            budget BIGINT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            chosen_worker BIGINT REFERENCES workers(worker_id)
        );
    ''')

    await conn.execute('''
        ALTER TABLE orders ADD COLUMN IF NOT EXISTS media_type TEXT;
    ''')
    await conn.execute('''
        ALTER TABLE orders ADD COLUMN IF NOT EXISTS media_file_id TEXT;
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            order_id BIGINT REFERENCES orders(order_id) ON DELETE CASCADE,
            worker_id BIGINT REFERENCES workers(worker_id) ON DELETE CASCADE,
            price BIGINT NOT NULL,
            PRIMARY KEY (order_id, worker_id)
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            username TEXT PRIMARY KEY
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            admin_id BIGINT PRIMARY KEY
        );
    ''')


async def load_from_db(conn, users_db, workers_db, orders, offers, chosen_orders, blocked_users, admins):
    users = await conn.fetch('SELECT * FROM users')
    for row in users:
        users_db[row['user_id']] = {
            'phone': row['phone'],
            'username': row['username'],
            'region': row['region'],
            'city': row['city']
        }

    workers = await conn.fetch('SELECT * FROM workers')
    for row in workers:
        workers_db[row['worker_id']] = {
            'phone': row['phone'],
            'username': row['username'],
            'name': row['name'],
            'region': row['region'],
            'city': row['city'],
            'profession': row['profession'],
            'approved': row['approved']
        }

    orders_query = await conn.fetch('SELECT * FROM orders')
    for row in orders_query:
        orders[row['order_id']] = {
            'order_id': row['order_id'],
            'user_id': row['user_id'],
            'username': row['username'],
            'name': row['name'],
            'region': row['region'],
            'city': row['city'],
            'service': row['service'],
            'description': row['description'],
            'budget': row['budget'],
            'location': (row['latitude'], row['longitude']),
            'chosen_worker': row['chosen_worker'],
            'workers_accepted': set(),
            'media': {'type': row['media_type'], 'file_id': row['media_file_id']} if row.get('media_type') else None
        }
        if row['chosen_worker'] is not None:
            chosen_orders.add(row['order_id'])

    offers_query = await conn.fetch('SELECT * FROM offers')
    for row in offers_query:
        if row['order_id'] not in offers:
            offers[row['order_id']] = {}
        offers[row['order_id']][row['worker_id']] = row['price']
        if row['order_id'] in orders:
            orders[row['order_id']]['workers_accepted'].add(row['worker_id'])

    blocked = await conn.fetch('SELECT * FROM blocked_users')
    for row in blocked:
        blocked_users.add(row['username'])

    admin_rows = await conn.fetch('SELECT * FROM admins')
    for row in admin_rows:
        admins.add(row['admin_id'])

async def save_user(conn, user_id, data):
    await conn.execute('''
        INSERT INTO users (user_id, phone, username, region, city)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id) DO UPDATE
        SET phone = $2, username = $3, region = $4, city = $5
    ''', user_id, data['phone'], data.get('username'), data.get('region'), data.get('city'))

async def delete_user(conn, user_id):
    await conn.execute('DELETE FROM users WHERE user_id = $1', user_id)

async def save_worker(conn, worker_id, data):
    await conn.execute('''
        INSERT INTO workers (worker_id, phone, username, name, region, city, profession, approved)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (worker_id) DO UPDATE SET
            phone = $2, username = $3, name = $4,
            region = $5, city = $6, profession = $7, approved = $8
    ''', worker_id, data.get('phone'), data.get('username'),
         data.get('name'), data.get('region'),
         data.get('city'), data.get('profession'),
         data.get('approved', False))

async def delete_worker(conn, worker_id):
    await conn.execute('DELETE FROM workers WHERE worker_id = $1', worker_id)

async def save_order(conn, order_id, data):
    if data.get('media'):
        first_media = data['media'][0]
        media_type = first_media['type']
        media_file_id = first_media['file_id']
    else:
        media_type = None
        media_file_id = None

    await conn.execute('''
        INSERT INTO orders (order_id, user_id, username, name, region, city, service, description,
                            budget, latitude, longitude, chosen_worker, media_type, media_file_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (order_id) DO UPDATE SET
            user_id = $2, username = $3, name = $4, region = $5, city = $6,
            service = $7, description = $8, budget = $9,
            latitude = $10, longitude = $11, chosen_worker = $12,
            media_type = $13, media_file_id = $14
    ''',
        order_id,
        data['user_id'],
        data.get('username'),
        data['name'],
        data['region'],
        data['city'],
        data['service'],
        data['description'],
        data['budget'],
        data['location'][0],
        data['location'][1],
        data.get('chosen_worker'),
        media_type,
        media_file_id
    )


async def delete_order(conn, order_id):
    await conn.execute('DELETE FROM orders WHERE order_id = $1', order_id)


async def save_offer(conn, order_id, worker_id, price=None):
    if price is None:
        row = await conn.fetchrow("SELECT budget FROM orders WHERE order_id = $1", order_id)
        if row:
            price = row["budget"]
        else:
            raise ValueError("Order not found, cannot save offer")

    await conn.execute('''
                       INSERT INTO offers (order_id, worker_id, price)
                       VALUES ($1, $2, $3) ON CONFLICT (order_id, worker_id) DO
                       UPDATE SET price = $3
                       ''', order_id, worker_id, price)


async def add_blocked(conn, username):
    await conn.execute('''
        INSERT INTO blocked_users (username)
        VALUES ($1) ON CONFLICT DO NOTHING
    ''', username)

async def delete_blocked(conn, username):
    await conn.execute('DELETE FROM blocked_users WHERE username = $1', username)

async def add_admin(conn, admin_id):
    await conn.execute('''
        INSERT INTO admins (admin_id)
        VALUES ($1) ON CONFLICT DO NOTHING
    ''', admin_id)

async def remove_admin(conn, admin_id):
    await conn.execute('DELETE FROM admins WHERE admin_id = $1', admin_id)


async def get_user(conn, user_id):
    row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
    if row:
        return dict(row)
    return None


async def get_worker(conn, worker_id):
    row = await conn.fetchrow('SELECT * FROM workers WHERE worker_id = $1', worker_id)
    if row:
        return dict(row)
    return None


async def get_order(conn, order_id):
    row = await conn.fetchrow('SELECT * FROM orders WHERE order_id = $1', order_id)
    if row:
        return dict(row)
    return None


async def update_user(conn, user_id, **kwargs):
    fields = []
    values = []
    i = 1
    for key, value in kwargs.items():
        fields.append(f"{key} = ${i}")
        values.append(value)
        i += 1
    if not fields:
        return
    query = f'UPDATE users SET {', '.join(fields)} WHERE user_id = ${i}'
    values.append(user_id)
    await conn.execute(query, *values)


async def update_worker(conn, worker_id, **kwargs):
    fields = []
    values = []
    i = 1
    for key, value in kwargs.items():
        fields.append(f"{key} = ${i}")
        values.append(value)
        i += 1
    if not fields:
        return
    query = f'UPDATE workers SET {', '.join(fields)} WHERE worker_id = ${i}'
    values.append(worker_id)
    await conn.execute(query, *values)


async def update_order(conn, order_id, **kwargs):
    fields = []
    values = []
    i = 1
    for key, value in kwargs.items():
        fields.append(f"{key} = ${i}")
        values.append(value)
        i += 1
    if not fields:
        return
    query = f'UPDATE orders SET {', '.join(fields)} WHERE order_id = ${i}'
    values.append(order_id)
    await conn.execute(query, *values)