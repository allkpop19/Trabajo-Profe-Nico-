"""Conexiones reutilizables y transacciones cortas sin compartir sockets."""
from contextlib import contextmanager
import logging
from queue import LifoQueue, Empty
from threading import BoundedSemaphore, Lock
from time import monotonic
import pymysql
from app.config import connection_options


class AppError(Exception):
    """Error apto para mostrar al usuario sin exponer credenciales."""


_connections = LifoQueue(maxsize=4)
_slots = BoundedSemaphore(4)
_revision_lock = Lock()
_revision = 0


def data_revision():
    with _revision_lock:
        return _revision


def invalidate_reads():
    global _revision
    with _revision_lock:
        _revision += 1


def _close(connection):
    try:
        connection.close()
    except pymysql.MySQLError:
        pass


def _checkout():
    try:
        connection, returned_at = _connections.get_nowait()
    except Empty:
        connection = None
    if connection:
        try:
            if not connection.open:
                raise pymysql.OperationalError(2006, "Conexión cerrada")
            if monotonic() - returned_at > 15:
                connection.ping(reconnect=False)
            return connection
        except pymysql.MySQLError:
            _close(connection)
    # Reintentar solo la apertura; nunca repetir escrituras tras un corte.
    for attempt in range(2):
        try:
            options = connection_options()
            options["autocommit"] = True
            return pymysql.connect(**options, cursorclass=pymysql.cursors.DictCursor)
        except pymysql.OperationalError as error:
            if attempt or error.args[0] not in (2003, 2006, 2013):
                raise


def readable_error(error):
    code = error.args[0] if error.args else None
    if code == 1644:
        return error.args[1]
    if code == 1062:
        return "Ya existe un registro con ese nombre o correo."
    if code in (1451, 1452):
        return "La operación afecta registros relacionados. Revisa las referencias o desactiva el usuario."
    if code in (3819, 4025, 1265, 1406, 1048):
        return "Los datos no cumplen las restricciones. Revisa los campos obligatorios y sus longitudes."
    if code in (1044, 1045):
        return "Acceso rechazado. Revisa el usuario, la contraseña y los permisos en el archivo .env."
    if code in (2003, 2013, 2006):
        return "No se pudo conectar al servidor. Revisa la red, el host y el puerto en .env."
    if code in (1146, 1305):
        return "La base no está preparada. Ejecuta python scripts/init_db.py."
    if code in (1213, 1205):
        return "Otro proceso está modificando estos datos. Intenta nuevamente."
    return "No se pudo completar la operación en la base de datos."


@contextmanager
def transaction(read_only=False):
    if not _slots.acquire(timeout=5):
        raise AppError("El servidor está ocupado. Intenta nuevamente en unos segundos.")
    connection = None
    reusable = True
    try:
        connection = _checkout()
        if not read_only:
            connection.begin()
        with connection.cursor() as cursor:
            yield cursor
        if not read_only:
            connection.commit()
            invalidate_reads()
    except pymysql.MySQLError as error:
        reusable = error.args[0] not in (2003, 2006, 2013)
        if connection and not read_only:
            try:
                connection.rollback()
            except pymysql.MySQLError:
                reusable = False
            invalidate_reads()
        logging.warning("Operación de base fallida, código %s", error.args[0] if error.args else "desconocido")
        raise AppError(readable_error(error)) from error
    except Exception:
        if connection and not read_only:
            try:
                connection.rollback()
            except pymysql.MySQLError:
                reusable = False
        raise
    finally:
        try:
            if connection:
                if reusable and connection.open:
                    _connections.put_nowait((connection, monotonic()))
                else:
                    _close(connection)
        finally:
            _slots.release()
