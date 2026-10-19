import sqlite3
from datetime import date
import pandas as pd

DB = "movimientos.db"   # SQLite creará este archivo solo


def conectar():
    return sqlite3.connect(DB)


# ---------- CREACIÓN DE TABLAS ----------
def crear_tabla():
    with conectar() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS prestamos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha       TEXT NOT NULL,
                persona     TEXT NOT NULL,
                descripcion TEXT,
                monto       REAL NOT NULL,
                pagado      REAL NOT NULL DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS presupuesto (
                categoria TEXT PRIMARY KEY,
                valor     REAL NOT NULL         -- presupuesto del mes
            )
        """)


def cargar_ejemplos():
    """Carga SOLO las categorías de tu Excel, y solo si el presupuesto está vacío.
    Ya no carga movimientos de ejemplo: empiezas en cero."""
    presupuesto = [
        ("Pasajes Transmilenio", 213000),
        ("Pasajes de bus",       144000),
        ("Comida dulces",        200000),
        ("Familia",              100000),
        ("Barbería",              46000),
        ("Uñas",                  40000),
        ("Gato",                  50000),
        ("Cancha y cerveza",      50000),
        ("Caja café",            111000),
        ("Disney+",               10000),
        ("prestamos",             50000),
    ]
    with conectar() as con:
        if con.execute("SELECT COUNT(*) FROM presupuesto").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO presupuesto (categoria, valor) VALUES (?, ?)",
                presupuesto,
            )


# ---------- QUINCENAS ----------
def periodo(fecha_txt):
    """
    Devuelve (mes_control, quincena) de una fecha 'AAAA-MM-DD'.
      1ª quincena: del 30 del mes anterior al 14   -> quincena 1
      2ª quincena: del 15 al 29                    -> quincena 2
    Ejemplo: 2026-10-15 -> ('2026-10', 2) | 2026-09-30 -> ('2026-10', 1)
    """
    d = date.fromisoformat(fecha_txt)
    if d.day >= 30:                       # el 30 y 31 abren la 1ª quincena del mes siguiente
        anio, mes = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        return f"{anio}-{mes:02d}", 1
    return f"{d.year}-{d.month:02d}", (2 if d.day >= 15 else 1)


def _todos():
    """Todos los movimientos, con columnas extra: mes_control y quincena."""
    with conectar() as con:
        df = pd.read_sql("SELECT * FROM movimientos", con)
    pq = df["fecha"].map(periodo)
    df["mes_control"] = pq.map(lambda x: x[0])
    df["quincena"] = pq.map(lambda x: x[1])
    df["mes_calendario"] = df["fecha"].str[:7]      # mes normal: del 1 al 30/31
    return df


# ---------- ESCRITURA: INSERT / UPDATE / DELETE ----------
def insertar_movimiento(fecha, descripcion, categoria, metodo, tipo, monto):
    with conectar() as con:
        con.execute(
            """INSERT INTO movimientos
               (fecha, descripcion, categoria, metodo, tipo, monto)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fecha, descripcion, categoria, metodo, tipo, monto),
        )


def actualizar_movimiento(id_, fecha, descripcion, categoria, metodo, tipo, monto):
    with conectar() as con:
        con.execute(
            """UPDATE movimientos
               SET fecha = ?, descripcion = ?, categoria = ?,
                   metodo = ?, tipo = ?, monto = ?
               WHERE id = ?""",
            (fecha, descripcion, categoria, metodo, tipo, monto, id_),
        )


def eliminar_movimiento(id_):
    with conectar() as con:
        con.execute("DELETE FROM movimientos WHERE id = ?", (id_,))


def guardar_presupuesto(categoria, valor):
    """Crea la categoría o, si ya existe, le cambia el valor."""
    with conectar() as con:
        con.execute(
            """INSERT INTO presupuesto (categoria, valor) VALUES (?, ?)
               ON CONFLICT(categoria) DO UPDATE SET valor = excluded.valor""",
            (categoria, valor),
        )


# ---------- LECTURA ----------
def listar_presupuesto():
    with conectar() as con:
        return pd.read_sql(
            "SELECT categoria, valor FROM presupuesto ORDER BY rowid", con
        )


def meses_disponibles():
    """Meses de control con movimientos ('AAAA-MM'), del más reciente al más antiguo."""
    df = _todos()
    return sorted(df["mes_control"].unique().tolist(), reverse=True)


def movimientos_del_mes(mes):
    df = _todos()
    df = df[df["mes_control"] == mes]
    return df.sort_values(["fecha", "id"], ascending=False)


def ultimos_movimientos(limite=4):
    with conectar() as con:
        return pd.read_sql(
            "SELECT * FROM movimientos ORDER BY fecha DESC, id DESC LIMIT ?",
            con,
            params=(limite,),
        )


def totales(mes):
    """Devuelve (ingresos, gastos) del mes de control indicado."""
    df = _todos()
    d = df[df["mes_control"] == mes]
    ingresos = d.loc[d["tipo"] == "Ingreso", "monto"].sum()
    gastos = d.loc[d["tipo"] == "Gasto", "monto"].sum()
    return ingresos, gastos


def gastos_por_categoria(mes):
    df = _todos()
    d = df[(df["mes_control"] == mes) & (df["tipo"] == "Gasto")]
    r = (d.groupby("categoria", as_index=False)["monto"].sum()
           .rename(columns={"monto": "total"})
           .sort_values("total", ascending=False))
    return r


def control_quincenas(mes):
    """
    Cruza presupuesto con gastos (igual que tu Excel).
    Columnas: categoria, valor, estimado_1, ejecutado_1, dif_1,
              estimado_2, ejecutado_2, dif_2, total_mes, dif_mes
    """
    df = _todos()
    g = df[(df["mes_control"] == mes) & (df["tipo"] == "Gasto")]
    e1 = g[g["quincena"] == 1].groupby("categoria")["monto"].sum()
    e2 = g[g["quincena"] == 2].groupby("categoria")["monto"].sum()

    c = listar_presupuesto()
    c["ejecutado_1"] = c["categoria"].map(e1).fillna(0)
    c["ejecutado_2"] = c["categoria"].map(e2).fillna(0)
    c["estimado_1"] = c["valor"] / 2
    c["estimado_2"] = c["valor"] / 2
    c["dif_1"] = c["estimado_1"] - c["ejecutado_1"]
    c["dif_2"] = c["estimado_2"] - c["ejecutado_2"]
    c["total_mes"] = c["ejecutado_1"] + c["ejecutado_2"]
    c["dif_mes"] = c["valor"] - c["total_mes"]
    return c[["categoria", "valor", "estimado_1", "ejecutado_1", "dif_1",
              "estimado_2", "ejecutado_2", "dif_2", "total_mes", "dif_mes"]]


def historial():
    """Resumen de TODO lo guardado: una fila por MES CALENDARIO (del 1 al 30/31)."""
    df = _todos()
    if df.empty:
        return pd.DataFrame(columns=["mes", "ingreso", "gasto", "saldo"])
    df["ingreso"] = df["monto"].where(df["tipo"] == "Ingreso", 0)
    df["gasto"] = df["monto"].where(df["tipo"] == "Gasto", 0)
    h = (df.groupby("mes_calendario", as_index=False)[["ingreso", "gasto"]].sum()
           .rename(columns={"mes_calendario": "mes"}))
    h["saldo"] = h["ingreso"] - h["gasto"]
    return h.sort_values("mes", ascending=False)


def movimientos_calendario(mes):
    """Todos los movimientos del mes calendario ('AAAA-MM'), del 1 al 30/31."""
    df = _todos()
    df = df[df["mes_calendario"] == mes]
    return df.sort_values(["fecha", "id"], ascending=False)


def gastos_categoria_calendario(mes):
    """Gastos del mes calendario agrupados por categoría."""
    df = _todos()
    d = df[(df["mes_calendario"] == mes) & (df["tipo"] == "Gasto")]
    return (d.groupby("categoria", as_index=False)["monto"].sum()
              .rename(columns={"monto": "total"})
              .sort_values("total", ascending=False))
    # ---------- PRÉSTAMOS (cuando yo presto plata) ----------
def insertar_prestamo(fecha, persona, descripcion, monto):
    with conectar() as con:
        con.execute(
            """INSERT INTO prestamos (fecha, persona, descripcion, monto)
               VALUES (?, ?, ?, ?)""",
            (fecha, persona, descripcion, monto),
        )


def listar_prestamos():
    with conectar() as con:
        return pd.read_sql(
            """SELECT *, (monto - pagado) AS pendiente
               FROM prestamos ORDER BY fecha DESC, id DESC""",
            con,
        )


def registrar_abono(id_, abono):
    """Suma un abono sin pasarse del monto prestado."""
    with conectar() as con:
        con.execute(
            "UPDATE prestamos SET pagado = MIN(monto, pagado + ?) WHERE id = ?",
            (abono, id_),
        )


def eliminar_prestamo(id_):
    with conectar() as con:
        con.execute("DELETE FROM prestamos WHERE id = ?", (id_,))
# ---------- PRÉSTAMOS (cuando yo presto plata) ----------
def insertar_prestamo(fecha, persona, descripcion, monto):
    with conectar() as con:
        con.execute(
            """INSERT INTO prestamos (fecha, persona, descripcion, monto)
               VALUES (?, ?, ?, ?)""",
            (fecha, persona, descripcion, monto),
        )


def listar_prestamos():
    with conectar() as con:
        return pd.read_sql(
            """SELECT *, (monto - pagado) AS pendiente
               FROM prestamos ORDER BY fecha DESC, id DESC""",
            con,
        )


def registrar_abono(id_, abono):
    """Suma un abono sin pasarse del monto prestado."""
    with conectar() as con:
        con.execute(
            "UPDATE prestamos SET pagado = MIN(monto, pagado + ?) WHERE id = ?",
            (abono, id_),
        )


def eliminar_prestamo(id_):
    with conectar() as con:
        con.execute("DELETE FROM prestamos WHERE id = ?", (id_,))