import aiosqlite
from datetime import datetime
from config import DATABASE_PATH

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""        CREATE TABLE IF NOT EXISTS watched_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            product_name TEXT,
            last_price REAL,
            currency TEXT,
            last_checked TIMESTAMP
        );
        """)
        await db.execute("""        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            price REAL,
            currency TEXT,
            FOREIGN KEY(item_id) REFERENCES watched_items(id)
        );
        """)
        await db.commit()

async def add_item(guild_id, channel_id, url, product_name, price, currency):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO watched_items (guild_id, channel_id, url, product_name, last_price, currency, last_checked) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, url, product_name, price, currency, datetime.utcnow())
        )
        await db.commit()
        cur = await db.execute("SELECT id FROM watched_items WHERE url = ?", (url,))
        row = await cur.fetchone()
        if row:
            item_id = row[0]
            await db.execute("INSERT INTO price_history (item_id, price, currency) VALUES (?, ?, ?)", (item_id, price, currency))
            await db.commit()
            return item_id
    return None

async def remove_item_by_url_or_name(guild_id, query):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT id FROM watched_items WHERE guild_id = ? AND url = ?", (guild_id, query))
        row = await cur.fetchone()
        if row:
            await db.execute("DELETE FROM watched_items WHERE id = ?", (row[0],))
            await db.commit()
            return True
        cur = await db.execute("SELECT id FROM watched_items WHERE guild_id = ? AND product_name LIKE ?", (guild_id, f"%{query}%"))
        row = await cur.fetchone()
        if row:
            await db.execute("DELETE FROM watched_items WHERE id = ?", (row[0],))
            await db.commit()
            return True
    return False

async def get_all_items():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT id, guild_id, channel_id, url, product_name, last_price, currency FROM watched_items")
        return await cur.fetchall()

async def update_price(item_id, new_price, currency):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE watched_items SET last_price = ?, currency = ?, last_checked = ? WHERE id = ?",
                         (new_price, currency, datetime.utcnow(), item_id))
        await db.execute("INSERT INTO price_history (item_id, price, currency) VALUES (?, ?, ?)", (item_id, new_price, currency))
        await db.commit()

async def get_min_price(item_id):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT price, checked_at, currency FROM price_history WHERE item_id = ? ORDER BY price ASC, checked_at ASC LIMIT 1", (item_id,))
        row = await cur.fetchone()
        if row:
            return row[0], row[1], row[2]
        return None, None, None
