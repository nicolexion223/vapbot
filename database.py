import os
import json
import psycopg2
from datetime import datetime, timedelta

DATABASE_URL = os.getenv("DATABASE_URL")

SABORES = [
    "Lemon Lime",
    "Pink Lemonade",
    "Strawberry Banana",
    "Peach Mango Pineapple",
    "Blueberry Ice",
    "Raspberry Watermelon",
    "Kiwi Passionfruit",
    "Blueberry Cherry Cranberry",
    "Strawberry Kiwi",
    "Blueberry Blackcurrant Ice",
    "Redbull",
    "Strawberry Watermelon",
    "Triple Cherry",
    "Black Ice Dragonfruit Strawberry",
    "Strawberry Vanilla Cola",
    "Love 66",
    "Peach Berry",
    "Grape Burst",
    "Black Berry Blueberry Ice",
    "Double Apple",
]

VENDEDORES = {
    "nico":  {"nombre": "Nico",  "telegram_id": None},
    "alex":  {"nombre": "Alex",  "telegram_id": None},
    "edu":   {"nombre": "Edu",   "telegram_id": None},
}


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def calcular_precio(cantidad: int) -> int:
    """
    1u = 12€
    2u = 20€
    3u = 32€ (20+12)
    4u = 40€ (20+20)
    ...
    Bloques de 2 a 20€, si sobra 1 → +12€
    Mayorista: 10u = 80€ (caja mezclada)
    """
    if cantidad <= 0:
        return 0
    pares = cantidad // 2
    resto = cantidad % 2
    return pares * 20 + resto * 12


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    c.execute("""
        INSERT INTO config (clave, valor) VALUES ('ubicacion', 'A convenir con el vendedor')
        ON CONFLICT (clave) DO NOTHING
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id SERIAL PRIMARY KEY,
            sabor TEXT UNIQUE NOT NULL,
            stock_nico INTEGER DEFAULT 0,
            stock_alex INTEGER DEFAULT 0,
            stock_edu  INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            cliente_id BIGINT,
            cliente_nombre TEXT,
            cliente_username TEXT,
            vendedor TEXT,
            sabores TEXT,
            cantidad INTEGER,
            tipo TEXT,
            precio INTEGER,
            pago TEXT,
            fecha TEXT,
            hora TEXT,
            estado TEXT DEFAULT 'pendiente',
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER,
            vendedor TEXT,
            sabor TEXT,
            cantidad INTEGER,
            precio INTEGER,
            fecha TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes_aprobados (
            telegram_id BIGINT PRIMARY KEY,
            nombre TEXT,
            username TEXT,
            aprobado_por TEXT,
            fecha_alta TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes_acceso (
            telegram_id BIGINT PRIMARY KEY,
            nombre TEXT,
            username TEXT,
            fecha TIMESTAMP DEFAULT NOW()
        )
    """)

    stock_inicial = {
        "Lemon Lime": 20,
        "Pink Lemonade": 20,
        "Strawberry Banana": 20,
        "Peach Mango Pineapple": 20,
        "Blueberry Ice": 10,
        "Raspberry Watermelon": 20,
        "Kiwi Passionfruit": 20,
        "Blueberry Cherry Cranberry": 10,
        "Strawberry Kiwi": 20,
        "Blueberry Blackcurrant Ice": 10,
        "Redbull": 10,
        "Strawberry Watermelon": 10,
        "Triple Cherry": 10,
        "Black Ice Dragonfruit Strawberry": 10,
        "Strawberry Vanilla Cola": 10,
        "Love 66": 10,
        "Peach Berry": 20,
        "Grape Burst": 10,
        "Black Berry Blueberry Ice": 10,
        "Double Apple": 10,
    }

    for sabor in SABORES:
        total = stock_inicial.get(sabor, 10)
        sn = round(total * 0.4)
        sa = round(total * 0.2)
        se = total - sn - sa
        c.execute("""
            INSERT INTO stock (sabor, stock_nico, stock_alex, stock_edu)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (sabor) DO NOTHING
        """, (sabor, sn, sa, se))

    conn.commit()
    conn.close()


def get_config(clave: str, default: str = "") -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT valor FROM config WHERE clave=%s", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def set_config(clave: str, valor: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO config (clave, valor) VALUES (%s, %s)
        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
    """, (clave, valor))
    conn.commit()
    conn.close()


def get_stock_total(sabor: str) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT stock_nico, stock_alex, stock_edu FROM stock WHERE sabor=%s", (sabor,))
    row = c.fetchone()
    conn.close()
    if not row:
        return 0
    return row[0] + row[1] + row[2]


def get_stock_vendedor(sabor: str, vendedor: str) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def get_todo_stock():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT sabor, stock_nico, stock_alex, stock_edu,
               (stock_nico + stock_alex + stock_edu) as total
        FROM stock ORDER BY sabor
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def descontar_stock(sabor: str, vendedor: str, cantidad: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
    row = c.fetchone()
    if not row or row[0] < cantidad:
        conn.close()
        return False
    c.execute(f"UPDATE stock SET stock_{vendedor} = stock_{vendedor} - %s WHERE sabor=%s",
              (cantidad, sabor))
    conn.commit()
    conn.close()
    return True


def registrar_venta_manual(vendedor: str, carrito: list):
    conn = get_conn()
    c = conn.cursor()
    total_uds = sum(cant for _, cant in carrito)
    precio_total = calcular_precio(total_uds)
    alertas = []
    precios_acum = 0
    try:
        for i, (sabor, cant) in enumerate(carrito):
            c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
            row = c.fetchone()
            if not row or row[0] < cant:
                conn.rollback()
                conn.close()
                return False, sabor
            c.execute(
                f"UPDATE stock SET stock_{vendedor} = stock_{vendedor} - %s WHERE sabor=%s",
                (cant, sabor)
            )
            if i == len(carrito) - 1:
                precio_item = precio_total - precios_acum
            else:
                precio_item = round(precio_total * cant / total_uds)
            precios_acum += precio_item
            c.execute(
                "INSERT INTO ventas (vendedor, sabor, cantidad, precio, fecha) VALUES (%s,%s,%s,%s,%s)",
                (vendedor, sabor, cant, precio_item, datetime.now().isoformat())
            )
            c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
            restante = c.fetchone()[0]
            if restante <= 3:
                alertas.append(f"⚠️ {sabor}: solo quedan {restante} uds")
        conn.commit()
        conn.close()
        return True, alertas
    except Exception:
        conn.rollback()
        conn.close()
        raise


def registrar_venta_mayorista_manual(vendedor: str, sabores_lista: list):
    from collections import Counter
    counts = list(Counter(sabores_lista).items())
    conn = get_conn()
    c = conn.cursor()
    precio_total = 80
    alertas = []
    precios_acum = 0
    try:
        for i, (sabor, cant) in enumerate(counts):
            c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
            row = c.fetchone()
            if not row or row[0] < cant:
                conn.rollback()
                conn.close()
                return False, sabor
            c.execute(
                f"UPDATE stock SET stock_{vendedor} = stock_{vendedor} - %s WHERE sabor=%s",
                (cant, sabor)
            )
            if i == len(counts) - 1:
                precio_item = precio_total - precios_acum
            else:
                precio_item = round(precio_total * cant / 10)
            precios_acum += precio_item
            c.execute(
                "INSERT INTO ventas (vendedor, sabor, cantidad, precio, fecha) VALUES (%s,%s,%s,%s,%s)",
                (vendedor, sabor, cant, precio_item, datetime.now().isoformat())
            )
            c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
            restante = c.fetchone()[0]
            if restante <= 3:
                alertas.append(f"⚠️ {sabor}: solo quedan {restante} uds")
        conn.commit()
        conn.close()
        return True, alertas
    except Exception:
        conn.rollback()
        conn.close()
        raise


def crear_pedido(cliente_id, cliente_nombre, cliente_username,
                 vendedor, sabores_lista, cantidad, tipo,
                 precio, pago, fecha, hora):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO pedidos
        (cliente_id, cliente_nombre, cliente_username, vendedor,
         sabores, cantidad, tipo, precio, pago, fecha, hora)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        cliente_id, cliente_nombre, cliente_username, vendedor,
        json.dumps(sabores_lista, ensure_ascii=False),
        cantidad, tipo, precio, pago, fecha, hora
    ))
    pedido_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return pedido_id


def get_pedidos_pendientes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, cliente_nombre, vendedor, sabores, cantidad,
               tipo, precio, pago, fecha, hora, estado
        FROM pedidos WHERE estado='pendiente'
        ORDER BY creado_en DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def confirmar_pedido(pedido_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT vendedor, sabores, cantidad, tipo, precio FROM pedidos WHERE id=%s", (pedido_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    vendedor, sabores_json, cantidad, tipo, precio = row
    sabores = json.loads(sabores_json)

    if tipo == 'normal' and sabores and sabores[0] != "Caja mezclada":
        sabor = sabores[0]
        c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
        stock_row = c.fetchone()
        if not stock_row or stock_row[0] < cantidad:
            conn.close()
            return False
        c.execute(f"UPDATE stock SET stock_{vendedor} = stock_{vendedor} - %s WHERE sabor=%s",
                  (cantidad, sabor))
        c.execute("""
            INSERT INTO ventas (pedido_id, vendedor, sabor, cantidad, precio, fecha)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (pedido_id, vendedor, sabor, cantidad, precio, datetime.now().isoformat()))

    c.execute("UPDATE pedidos SET estado='confirmado' WHERE id=%s", (pedido_id,))
    conn.commit()
    conn.close()
    return True


def get_pedido(pedido_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, cliente_id, cliente_nombre, vendedor, tipo, precio,
               sabores, cantidad, pago, fecha, hora
        FROM pedidos WHERE id=%s
    """, (pedido_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "cliente_id": row[1], "cliente_nombre": row[2],
        "vendedor": row[3], "tipo": row[4], "precio": row[5],
        "sabores": row[6], "cantidad": row[7], "pago": row[8],
        "fecha": row[9], "hora": row[10],
    }


def confirmar_pedido_mayorista(pedido_id: int, vendedor: str, sabores_elegidos: list):
    from collections import Counter
    conn = get_conn()
    c = conn.cursor()
    counts = Counter(sabores_elegidos)
    alertas = []
    try:
        for sabor, cnt in counts.items():
            c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
            row = c.fetchone()
            if not row or row[0] < cnt:
                conn.rollback()
                conn.close()
                return False, sabor
            c.execute(
                f"UPDATE stock SET stock_{vendedor} = stock_{vendedor} - %s WHERE sabor=%s",
                (cnt, sabor)
            )
            c.execute(
                "INSERT INTO ventas (pedido_id, vendedor, sabor, cantidad, precio, fecha) VALUES (%s,%s,%s,%s,%s,%s)",
                (pedido_id, vendedor, sabor, cnt, cnt * 8, datetime.now().isoformat())
            )
            c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
            restante = c.fetchone()[0]
            if restante <= 3:
                alertas.append(f"⚠️ {sabor}: solo quedan {restante} uds")
        c.execute(
            "UPDATE pedidos SET sabores=%s, estado='confirmado' WHERE id=%s",
            (json.dumps(sabores_elegidos, ensure_ascii=False), pedido_id)
        )
        conn.commit()
        conn.close()
        return True, alertas
    except Exception:
        conn.rollback()
        conn.close()
        raise


def ventas_periodo(vendedor=None, periodo='hoy'):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now()

    if periodo == 'semana':
        start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        date_cond, date_params = "fecha >= %s", [start]
    elif periodo == 'mes':
        date_cond, date_params = "fecha LIKE %s", [f"{now.strftime('%Y-%m')}%"]
    else:
        date_cond, date_params = "fecha LIKE %s", [f"{now.strftime('%Y-%m-%d')}%"]

    if vendedor:
        c.execute(f"""
            SELECT sabor, SUM(cantidad), SUM(precio)
            FROM ventas WHERE vendedor=%s AND {date_cond}
            GROUP BY sabor ORDER BY SUM(cantidad) DESC
        """, [vendedor] + date_params)
    else:
        c.execute(f"""
            SELECT sabor, SUM(cantidad), SUM(precio)
            FROM ventas WHERE {date_cond}
            GROUP BY sabor ORDER BY SUM(cantidad) DESC
        """, date_params)

    rows = c.fetchall()
    conn.close()
    return rows


def stats_por_vendedor(periodo='hoy'):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now()

    if periodo == 'semana':
        start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        date_cond, date_params = "fecha >= %s", [start]
    elif periodo == 'mes':
        date_cond, date_params = "fecha LIKE %s", [f"{now.strftime('%Y-%m')}%"]
    else:
        date_cond, date_params = "fecha LIKE %s", [f"{now.strftime('%Y-%m-%d')}%"]

    c.execute(f"""
        SELECT vendedor, SUM(cantidad), SUM(precio)
        FROM ventas WHERE {date_cond}
        GROUP BY vendedor ORDER BY SUM(precio) DESC
    """, date_params)

    rows = c.fetchall()
    conn.close()
    return rows


def ventas_hoy(vendedor: str = None):
    conn = get_conn()
    c = conn.cursor()
    hoy = datetime.now().strftime("%Y-%m-%d")
    if vendedor:
        c.execute("""
            SELECT sabor, SUM(cantidad), SUM(precio)
            FROM ventas WHERE vendedor=%s AND fecha LIKE %s
            GROUP BY sabor
        """, (vendedor, f"{hoy}%"))
    else:
        c.execute("""
            SELECT sabor, SUM(cantidad), SUM(precio)
            FROM ventas WHERE fecha LIKE %s
            GROUP BY sabor
        """, (f"{hoy}%",))
    rows = c.fetchall()
    conn.close()
    return rows


# ─── LISTA BLANCA DE CLIENTES ────────────────────────────────────────────────

def cliente_aprobado(telegram_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM clientes_aprobados WHERE telegram_id=%s", (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def aprobar_cliente(telegram_id: int, nombre: str, username: str, aprobado_por: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO clientes_aprobados (telegram_id, nombre, username, aprobado_por)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO NOTHING
        """, (telegram_id, nombre, username, aprobado_por))
        conn.commit()
        insertado = c.rowcount > 0
    finally:
        conn.close()
    return insertado


def bloquear_cliente(telegram_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM clientes_aprobados WHERE telegram_id=%s", (telegram_id,))
    conn.commit()
    eliminado = c.rowcount > 0
    conn.close()
    return eliminado


def rechazar_pedido(pedido_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE pedidos SET estado='rechazado' WHERE id=%s AND estado='pendiente'", (pedido_id,))
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def añadir_stock(sabor: str, vendedor: str, cantidad: int) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        f"UPDATE stock SET stock_{vendedor} = stock_{vendedor} + %s WHERE sabor=%s",
        (cantidad, sabor)
    )
    c.execute(f"SELECT stock_{vendedor} FROM stock WHERE sabor=%s", (sabor,))
    nuevo = c.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo


def get_clientes_aprobados():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id, nombre, username, aprobado_por, fecha_alta
        FROM clientes_aprobados ORDER BY fecha_alta DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


# ─── SOLICITUDES DE ACCESO ───────────────────────────────────────────────────

def registrar_solicitud(telegram_id: int, nombre: str, username: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO solicitudes_acceso (telegram_id, nombre, username)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET nombre=EXCLUDED.nombre, username=EXCLUDED.username
    """, (telegram_id, nombre, username))
    conn.commit()
    conn.close()


def get_solicitud(telegram_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id, nombre, username, fecha FROM solicitudes_acceso WHERE telegram_id=%s",
              (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row


def eliminar_solicitud(telegram_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM solicitudes_acceso WHERE telegram_id=%s", (telegram_id,))
    conn.commit()
    conn.close()
