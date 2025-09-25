import asyncpg


async def connect_db():
    return await asyncpg.connect(
        dsn="postgresql://postgres:QWuKvFfHgWeIepwAXslgMgygnwSEQTnL@postgres.railway.internal:5432/railway")


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
        CREATE TABLE IF NOT EXISTS pending_users (
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
        CREATE TABLE IF NOT EXISTS pending_workers (
            worker_id BIGINT PRIMARY KEY,
            phone TEXT NOT NULL,
            username TEXT,
            name TEXT,
            region TEXT,
            city TEXT,
            profession TEXT
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
            time TEXT,
            budget BIGINT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            chosen_worker BIGINT REFERENCES workers(worker_id),
            media_type TEXT,
            media_file_id TEXT
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS pending_orders (
            order_id BIGINT PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            name TEXT,
            region TEXT,
            city TEXT,
            service TEXT,
            description TEXT,
            time TEXT,
            budget BIGINT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            chosen_worker BIGINT,
            media_type TEXT,
            media_file_id TEXT
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            order_id BIGINT REFERENCES orders(order_id) ON DELETE CASCADE,
            worker_id BIGINT REFERENCES workers(worker_id) ON DELETE CASCADE,
            price BIGINT,
            proposed_time TEXT,
            PRIMARY KEY (order_id, worker_id)
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            user_id BIGINT UNIQUE
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            admin_id BIGINT PRIMARY KEY
        );
    ''')


async def load_from_db(conn, users_db, pending_users, workers_db, pending_workers, orders, offers, chosen_orders,
                       blocked_users, admins):
    # Load blocked users first
    blocked_rows = await conn.fetch('SELECT * FROM blocked_users')
    for row in blocked_rows:
        if row['username']:
            blocked_users.add(row['username'].lower())
        if row['user_id']:
            blocked_users.add(row['user_id'])

    users = await conn.fetch('SELECT * FROM users')
    for row in users:
        username_lower = (row['username'] or "").lower()
        if row['user_id'] not in blocked_users and username_lower not in blocked_users:
            users_db[row['user_id']] = dict(row)

    pending_users_rows = await conn.fetch('SELECT * FROM pending_users')
    for row in pending_users_rows:
        username_lower = (row['username'] or "").lower()
        if row['user_id'] not in blocked_users and username_lower not in blocked_users:
            pending_users[row['user_id']] = dict(row)

    workers = await conn.fetch('SELECT * FROM workers')
    for row in workers:
        username_lower = (row['username'] or "").lower()
        if row['worker_id'] not in blocked_users and username_lower not in blocked_users:
            workers_db[row['worker_id']] = dict(row)

    pending_workers_rows = await conn.fetch('SELECT * FROM pending_workers')
    for row in pending_workers_rows:
        username_lower = (row['username'] or "").lower()
        if row['worker_id'] not in blocked_users and username_lower not in blocked_users:
            pending_workers[row['worker_id']] = dict(row)

    orders_query = await conn.fetch('SELECT * FROM orders')
    for row in orders_query:
        media = []
        if row['media_type'] and row['media_file_id']:
            media = [{'type': row['media_type'], 'file_id': row['media_file_id']}]
        orders[row['order_id']] = {
            **dict(row),
            'location': (row['latitude'], row['longitude']),
            'workers_accepted': set(),
            'media': media
        }
        if row['chosen_worker']:
            chosen_orders.add(row['order_id'])

    pending_orders_query = await conn.fetch('SELECT * FROM pending_orders')
    for row in pending_orders_query:
        media = []
        if row['media_type'] and row['media_file_id']:
            media = [{'type': row['media_type'], 'file_id': row['media_file_id']}]
        orders[row['order_id']] = {
            **dict(row),
            'location': (row['latitude'], row['longitude']),
            'workers_accepted': set(),
            'media': media
        }

    offers_query = await conn.fetch('SELECT * FROM offers')
    for row in offers_query:
        if row['order_id'] not in offers:
            offers[row['order_id']] = {}

        offers[row['order_id']][row['worker_id']] = {
            'price': row['price'],
            'proposed_time': row.get('proposed_time')
        }
        if row['order_id'] in orders:
            orders[row['order_id']]['workers_accepted'].add(row['worker_id'])

    for row in await conn.fetch('SELECT * FROM admins'):
        admins.add(row['admin_id'])


async def save_user(conn, user_id, data):
    await conn.execute('''
        INSERT INTO users (user_id, phone, username, region, city)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id) DO UPDATE
        SET phone=$2, username=$3, region=$4, city=$5
    ''', user_id, data['phone'], data.get('username'), data.get('region'), data.get('city'))


async def save_pending_user(conn, user_id, data):
    await conn.execute('''
        INSERT INTO pending_users (user_id, phone, username, region, city)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id) DO UPDATE
        SET phone=$2, username=$3, region=$4, city=$5
    ''', user_id, data['phone'], data.get('username'), data.get('region'), data.get('city'))


async def delete_pending_user(conn, user_id):
    await conn.execute('DELETE FROM pending_users WHERE user_id=$1', user_id)


async def delete_user(conn, user_id):
    await conn.execute('DELETE FROM users WHERE user_id=$1', user_id)


async def save_worker(conn, worker_id, data):
    await conn.execute('''
        INSERT INTO workers (worker_id, phone, username, name, region, city, profession, approved)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (worker_id) DO UPDATE SET
            phone=$2, username=$3, name=$4,
            region=$5, city=$6, profession=$7, approved=$8
    ''', worker_id, data.get('phone'), data.get('username'),
                       data.get('name'), data.get('region'), data.get('city'),
                       data.get('profession'), data.get('approved', False))


async def save_pending_worker(conn, worker_id, data):
    await conn.execute('''
        INSERT INTO pending_workers (worker_id, phone, username, name, region, city, profession)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (worker_id) DO UPDATE SET
            phone=$2, username=$3, name=$4,
            region=$5, city=$6, profession=$7
    ''', worker_id, data.get('phone'), data.get('username'),
                       data.get('name'), data.get('region'), data.get('city'),
                       data.get('profession'))


async def delete_pending_worker(conn, worker_id):
    await conn.execute('DELETE FROM pending_workers WHERE worker_id=$1', worker_id)


async def delete_worker(conn, worker_id):
    await conn.execute('''
        UPDATE orders
        SET chosen_worker = NULL
        WHERE chosen_worker=$1
    ''', worker_id)

    await conn.execute('DELETE FROM workers WHERE worker_id=$1', worker_id)


async def save_order(conn, order_id, data):
    media_type = None
    media_file_id = None
    if data.get('media'):
        if data['media']:
            first_media = data['media'][0]
            media_type = first_media['type']
            media_file_id = first_media['file_id']

    await conn.execute('''
        INSERT INTO orders (order_id,user_id,username,name,region,city,
                            service,description,time,budget,latitude,longitude,
                            chosen_worker,media_type,media_file_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        ON CONFLICT (order_id) DO UPDATE SET
            user_id=$2, username=$3, name=$4, region=$5, city=$6,
            service=$7, description=$8, time=$9, budget=$10,
            latitude=$11, longitude=$12, chosen_worker=$13,
            media_type=$14, media_file_id=$15
    ''', order_id, data['user_id'], data.get('username'), data['name'],
                       data['region'], data['city'], data['service'], data['description'],
                       data.get('time'), data['budget'], data['location'][0], data['location'][1],
                       data.get('chosen_worker'), media_type, media_file_id)


async def save_pending_order(conn, order_id, data):
    media_type = None
    media_file_id = None
    if data.get('media'):
        if data['media']:
            first_media = data['media'][0]
            media_type = first_media['type']
            media_file_id = first_media['file_id']

    await conn.execute('''
        INSERT INTO pending_orders (order_id,user_id,username,name,region,city,
                            service,description,time,budget,latitude,longitude,
                            chosen_worker,media_type,media_file_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        ON CONFLICT (order_id) DO UPDATE SET
            user_id=$2, username=$3, name=$4, region=$5, city=$6,
            service=$7, description=$8, time=$9, budget=$10,
            latitude=$11, longitude=$12, chosen_worker=$13,
            media_type=$14, media_file_id=$15
    ''', order_id, data['user_id'], data.get('username'), data['name'],
                       data['region'], data['city'], data['service'], data['description'],
                       data.get('time'), data['budget'], data['location'][0], data['location'][1],
                       data.get('chosen_worker'), media_type, media_file_id)


async def delete_order(conn, order_id):
    await conn.execute('DELETE FROM orders WHERE order_id=$1', order_id)


async def save_offer(conn, order_id, worker_id, price=None, proposed_time=None):
    await conn.execute('''
        INSERT INTO offers (order_id, worker_id, price, proposed_time)
        VALUES ($1, $2, COALESCE($3, 0), $4)
        ON CONFLICT (order_id, worker_id) DO UPDATE SET
            price = COALESCE(EXCLUDED.price, offers.price),
            proposed_time = COALESCE(EXCLUDED.proposed_time, offers.proposed_time)
    ''', order_id, worker_id, price, proposed_time)


async def add_blocked(conn, identifier):
    if isinstance(identifier, int):
        await conn.execute('''
            INSERT INTO blocked_users (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        ''', identifier)
    else:
        username = identifier.lower()
        await conn.execute('''
            INSERT INTO blocked_users (username) VALUES ($1)
            ON CONFLICT (username) DO NOTHING
        ''', username)


async def delete_blocked(conn, identifier):
    if isinstance(identifier, int):
        await conn.execute('DELETE FROM blocked_users WHERE user_id=$1', identifier)
    else:
        username = identifier.lower()
        await conn.execute('DELETE FROM blocked_users WHERE username=$1', username)


async def add_admin(conn, admin_id):
    await conn.execute('INSERT INTO admins (admin_id) VALUES ($1) ON CONFLICT DO NOTHING', admin_id)


async def remove_admin(conn, admin_id):
    await conn.execute('DELETE FROM admins WHERE admin_id=$1', admin_id)


async def get_user(conn, user_id):
    return dict(await conn.fetchrow('SELECT * FROM users WHERE user_id=$1', user_id) or {})


async def get_worker(conn, worker_id):
    return dict(await conn.fetchrow('SELECT * FROM workers WHERE worker_id=$1', worker_id) or {})


async def get_order(conn, order_id):
    return dict(await conn.fetchrow('SELECT * FROM orders WHERE order_id=$1', order_id) or {})


async def update_user(conn, user_id, **kwargs):
    await _update_dynamic(conn, "users", "user_id", user_id, kwargs)


async def update_worker(conn, worker_id, **kwargs):
    await _update_dynamic(conn, "workers", "worker_id", worker_id, kwargs)


async def update_order(conn, order_id, **kwargs):
    await _update_dynamic(conn, "orders", "order_id", order_id, kwargs)


async def _update_dynamic(conn, table, key, key_val, fields: dict):
    if not fields:
        return
    set_parts = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_parts.append(f"{k}=${i}")
        values.append(v)
    query = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {key}=${len(values) + 1}"
    values.append(key_val)
    await conn.execute(query, *values)
