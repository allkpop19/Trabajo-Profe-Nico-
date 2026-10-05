"""Una conexión por operación, transacciones cortas y errores comprensibles."""
from contextlib import contextmanager
import logging
import pymysql
from app.config import connection_options


class AppError(Exception):
    """Error apto para mostrar al usuario sin exponer credenciales."""


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
def transaction():
    connection = None
    try:
        connection = pymysql.connect(**connection_options(), cursorclass=pymysql.cursors.DictCursor)
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except pymysql.MySQLError as error:
        if connection:
            connection.rollback()
        logging.warning("Operación de base fallida, código %s", error.args[0] if error.args else "desconocido")
        raise AppError(readable_error(error)) from error
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()
