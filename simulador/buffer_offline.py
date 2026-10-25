
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Ubicacion de la base de datos local.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "buffer_offline.db"


def conectar_bd():
    """Abre la base de datos local."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(DB_PATH, timeout=30)
    conexion.row_factory = sqlite3.Row

    return conexion


def inicializar_buffer():
    """Crea la tabla de lecturas pendientes si no existe."""
    with conectar_bd() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS lecturas_pendientes (
                id_lectura TEXT PRIMARY KEY,
                id_acopio TEXT NOT NULL,
                id_camara TEXT NOT NULL,
                topico TEXT NOT NULL,
                payload TEXT NOT NULL,
                fecha_guardado TEXT NOT NULL
            )
            """
        )


def guardar_lectura(lectura):
    """Guarda una lectura antes de intentar publicarla."""
    inicializar_buffer()

    campos_obligatorios = (
        "id_lectura",
        "id_acopio",
        "id_camara",
        "topico",
        "marca_tiempo",
    )

    for campo in campos_obligatorios:
        if campo not in lectura:
            raise ValueError(f"Falta el campo obligatorio: {campo}")

    payload = json.dumps(lectura, ensure_ascii=False)

    with conectar_bd() as conexion:
        conexion.execute(
            """
            INSERT OR IGNORE INTO lecturas_pendientes (
                id_lectura,
                id_acopio,
                id_camara,
                topico,
                payload,
                fecha_guardado
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lectura["id_lectura"],
                lectura["id_acopio"],
                lectura["id_camara"],
                lectura["topico"],
                payload,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def obtener_pendientes(id_acopio=None, limite=100):
    """Consulta lecturas pendientes en orden de llegada."""
    inicializar_buffer()

    if limite <= 0:
        raise ValueError("El limite debe ser mayor que cero")

    with conectar_bd() as conexion:
        if id_acopio is None:
            filas = conexion.execute(
                """
                SELECT payload
                FROM lecturas_pendientes
                ORDER BY fecha_guardado, rowid
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        else:
            filas = conexion.execute(
                """
                SELECT payload
                FROM lecturas_pendientes
                WHERE id_acopio = ?
                ORDER BY fecha_guardado, rowid
                LIMIT ?
                """,
                (id_acopio, limite),
            ).fetchall()

    return [json.loads(fila["payload"]) for fila in filas]


def eliminar_lectura(id_lectura):
    """Elimina una lectura de la cola local."""
    with conectar_bd() as conexion:
        conexion.execute(
            """
            DELETE FROM lecturas_pendientes
            WHERE id_lectura = ?
            """,
            (id_lectura,),
        )


def contar_pendientes(id_acopio=None):
    """Cuenta las lecturas que siguen guardadas."""
    inicializar_buffer()

    with conectar_bd() as conexion:
        if id_acopio is None:
            fila = conexion.execute(
                "SELECT COUNT(*) FROM lecturas_pendientes"
            ).fetchone()
        else:
            fila = conexion.execute(
                """
                SELECT COUNT(*)
                FROM lecturas_pendientes
                WHERE id_acopio = ?
                """,
                (id_acopio,),
            ).fetchone()

    return fila[0]
