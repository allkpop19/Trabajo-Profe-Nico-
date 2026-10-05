"""Consultas parametrizadas. La interfaz no contiene SQL."""
from copy import deepcopy
from functools import wraps
from threading import Lock
from time import monotonic
from app.db import transaction, AppError, data_revision
from app.validation import clean_text, validate_email, validate_ticket, STATUSES, PRIORITIES

TICKET_SELECT = """
SELECT t.*,u.name AS requester,d.name AS department,s.name AS specialty,tech.name AS technician
FROM mt_tickets t
JOIN mt_users u ON u.id=t.requester_id
JOIN mt_departments d ON d.id=u.department_id
JOIN mt_specialties s ON s.id=t.specialty_id
LEFT JOIN mt_users tech ON tech.id=t.technician_id
"""

TICKET_LIST_SELECT = TICKET_SELECT.replace("t.*", "t.id,t.title,t.status,t.priority,t.requester_id,t.specialty_id,t.technician_id,t.created_at,t.version")


def cached_read(function):
    """Caché breve; todas las escrituras de la aplicación la invalidan."""
    @wraps(function)
    def wrapper(self, *args, **kwargs):
        key = (function.__name__, args, tuple(sorted(kwargs.items())))
        revision = data_revision()
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and entry[0] == revision and entry[1] > monotonic():
                return deepcopy(entry[2])
        result = function(self, *args, **kwargs)
        with self._cache_lock:
            if len(self._cache) >= 64:
                self._cache.clear()
            self._cache[key] = (revision, monotonic() + 10, deepcopy(result))
        return result
    return wrapper


def ticket_filters(query, status, priority, specialty):
    clauses, values = [], []
    if query.strip():
        clauses.append("(t.title LIKE %s OR t.description LIKE %s OR u.name LIKE %s OR tech.name LIKE %s)")
        values.extend([f"%{query.strip()}%"] * 4)
    for column, value in (("t.status", status), ("t.priority", priority), ("t.specialty_id", specialty)):
        if value:
            clauses.append(f"{column}=%s")
            values.append(value)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), values


class Repository:
    def __init__(self):
        self._cache = {}
        self._cache_lock = Lock()

    def refresh(self):
        with self._cache_lock:
            self._cache.clear()

    def tickets(self, query="", status="", priority="", specialty=""):
        where, values = ticket_filters(query, status, priority, specialty)
        with transaction(read_only=True) as cursor:
            cursor.execute(TICKET_SELECT + where
                           + " ORDER BY FIELD(t.priority,'critica','alta','media','baja'),t.created_at DESC,t.id DESC", values)
            return cursor.fetchall()

    @cached_read
    def ticket_page(self, query="", status="", priority="", specialty="", page=0, page_size=25):
        where, values = ticket_filters(query, status, priority, specialty)
        page = max(0, int(page))
        page_size = min(50, max(1, int(page_size)))
        select = TICKET_LIST_SELECT.replace("SELECT ", "SELECT COUNT(*) OVER() AS filtered_total,", 1)
        with transaction(read_only=True) as cursor:
            cursor.execute(select + where
                + " ORDER BY FIELD(t.priority,'critica','alta','media','baja'),t.created_at DESC,t.id DESC LIMIT %s OFFSET %s",
                values + [page_size, page * page_size])
            rows = cursor.fetchall()
            total = rows[0]["filtered_total"] if rows else 0
            if not rows and page:
                cursor.execute("SELECT COUNT(*) AS total FROM " + TICKET_SELECT.split("FROM ", 1)[1] + where, values)
                total = cursor.fetchone()["total"]
            return rows, total

    def ticket(self, ticket_id):
        with transaction(read_only=True) as cursor:
            cursor.execute(TICKET_SELECT + " WHERE t.id=%s", (ticket_id,))
            result = cursor.fetchone()
            if not result:
                raise AppError("El ticket ya no existe.")
            return result

    def save_ticket(self, data, ticket_id=None, version=None):
        data = validate_ticket(data)
        fields = (data["title"], data["description"], data["requester_id"], data["specialty_id"], data["priority"])
        with transaction() as cursor:
            cursor.execute("SELECT id FROM mt_users WHERE id=%s AND active=1", (data["requester_id"],))
            if not cursor.fetchone():
                raise AppError("El solicitante debe estar activo.")
            if ticket_id:
                cursor.execute("SELECT * FROM mt_tickets WHERE id=%s FOR UPDATE", (ticket_id,))
                old = cursor.fetchone()
                if not old or old["version"] != version:
                    raise AppError("Este ticket cambió en otra sesión. Actualiza la lista antes de editarlo.")
                transitions = {"abierto": {"abierto"}, "en_progreso": {"en_progreso", "resuelto"},
                               "resuelto": {"resuelto", "en_progreso", "cerrado"}, "cerrado": set()}
                if data["status"] not in transitions[old["status"]]:
                    raise AppError("Transición no permitida. Los tickets cerrados no se modifican; para iniciar la atención, asigna un técnico.")
                resolved_at = old["resolved_at"]
                if data["status"] == "en_progreso":
                    resolved_at = None
                elif data["status"] == "resuelto" and old["status"] != "resuelto":
                    cursor.execute("SELECT NOW() AS now")
                    resolved_at = cursor.fetchone()["now"]
                cursor.execute("""UPDATE mt_tickets SET title=%s,description=%s,requester_id=%s,
                    specialty_id=%s,priority=%s,status=%s,solution=%s,resolved_at=%s,version=version+1 WHERE id=%s AND version=%s""",
                    fields + (data["status"], data["solution"], resolved_at, ticket_id, version))
                if cursor.rowcount != 1:
                    raise AppError("Este ticket cambió en otra sesión. Actualiza la lista antes de editarlo.")
                cursor.execute("""INSERT INTO mt_ticket_history(ticket_id,action,old_status,new_status,old_technician_id,new_technician_id)
                    VALUES(%s,%s,%s,%s,%s,%s)""", (ticket_id,"estado" if old["status"] != data["status"] else "edicion",
                    old["status"], data["status"], old["technician_id"], old["technician_id"]))
                return ticket_id
            if data.get("status", "abierto") != "abierto":
                raise AppError("Un ticket nuevo debe estar abierto.")
            cursor.execute("""INSERT INTO mt_tickets(title,description,requester_id,specialty_id,priority)
                VALUES(%s,%s,%s,%s,%s)""", fields)
            new_id = cursor.lastrowid
            cursor.execute("INSERT INTO mt_ticket_history(ticket_id,action,new_status) VALUES(%s,'creacion','abierto')", (new_id,))
            return new_id

    def delete_ticket(self, ticket_id, version):
        with transaction() as cursor:
            cursor.execute("DELETE FROM mt_tickets WHERE id=%s AND version=%s AND status='abierto' AND technician_id IS NULL", (ticket_id, version))
            if cursor.rowcount != 1:
                raise AppError("Solo se eliminan tickets abiertos sin asignar. El ticket también puede haber cambiado; actualiza la lista.")

    def assign(self, ticket_id, technician_id):
        with transaction() as cursor:
            cursor.callproc("mt_assign_ticket", (ticket_id, technician_id))
            while cursor.nextset():
                pass

    def history(self, ticket_id):
        with transaction(read_only=True) as cursor:
            cursor.execute("""SELECT h.*,old.name AS old_technician,new.name AS new_technician
                FROM mt_ticket_history h
                LEFT JOIN mt_users old ON old.id=h.old_technician_id
                LEFT JOIN mt_users new ON new.id=h.new_technician_id
                WHERE h.ticket_id=%s ORDER BY h.id DESC""", (ticket_id,))
            return cursor.fetchall()

    @cached_read
    def dashboard(self):
        with transaction(read_only=True) as cursor:
            cursor.execute("SELECT status,priority,COUNT(*) AS total FROM mt_tickets GROUP BY status,priority")
            counts, priorities = {}, {}
            for row in cursor.fetchall():
                counts[row["status"]] = counts.get(row["status"], 0) + row["total"]
                if row["status"] in ("abierto", "en_progreso"):
                    priorities[row["priority"]] = priorities.get(row["priority"], 0) + row["total"]
            cursor.execute("""SELECT s.name AS specialty,COUNT(t.id) AS total,
                SUM(CASE WHEN t.status IN ('abierto','en_progreso') THEN 1 ELSE 0 END) AS pending
                FROM mt_specialties s LEFT JOIN mt_tickets t ON t.specialty_id=s.id
                GROUP BY s.id,s.name ORDER BY total DESC,s.name""")
            summary = cursor.fetchall()
            cursor.execute(TICKET_LIST_SELECT + " ORDER BY t.created_at DESC,t.id DESC LIMIT 5")
            recent = cursor.fetchall()
            return counts, summary, priorities, recent

    @cached_read
    def catalog(self, kind):
        if kind not in ("departments", "specialties"):
            raise AppError("Catálogo no válido.")
        with transaction(read_only=True) as cursor:
            cursor.execute(f"SELECT * FROM mt_{kind} ORDER BY name")
            return cursor.fetchall()

    def save_catalog(self, kind, name, item_id=None):
        if kind not in ("departments", "specialties"):
            raise AppError("Catálogo no válido.")
        name = clean_text(name, "El nombre", 2, 80)
        with transaction() as cursor:
            if item_id:
                cursor.execute(f"UPDATE mt_{kind} SET name=%s WHERE id=%s", (name, item_id))
            else:
                cursor.execute(f"INSERT INTO mt_{kind}(name) VALUES(%s)", (name,))
                return cursor.lastrowid

    def delete_catalog(self, kind, item_id):
        if kind not in ("departments", "specialties"):
            raise AppError("Catálogo no válido.")
        with transaction() as cursor:
            cursor.execute(f"DELETE FROM mt_{kind} WHERE id=%s", (item_id,))

    @cached_read
    def users(self, active_only=False):
        with transaction(read_only=True) as cursor:
            cursor.execute("""SELECT u.*,d.name AS department,tech.user_id IS NOT NULL AS is_technician
                FROM mt_users u JOIN mt_departments d ON d.id=u.department_id
                LEFT JOIN mt_technicians tech ON tech.user_id=u.id"""
                + (" WHERE u.active=1" if active_only else "") + " ORDER BY u.name")
            return cursor.fetchall()

    def save_user(self, name, email, department_id, active=True, user_id=None):
        name = clean_text(name, "El nombre", 2, 100)
        email = validate_email(email)
        if not department_id:
            raise AppError("Selecciona un departamento.")
        with transaction() as cursor:
            if user_id:
                cursor.execute("UPDATE mt_users SET name=%s,email=%s,department_id=%s,active=%s WHERE id=%s",
                               (name, email, department_id, active, user_id))
                return user_id
            cursor.execute("INSERT INTO mt_users(name,email,department_id,active) VALUES(%s,%s,%s,%s)",
                           (name, email, department_id, active))
            return cursor.lastrowid

    def delete_user(self, user_id):
        with transaction() as cursor:
            cursor.execute("DELETE FROM mt_users WHERE id=%s", (user_id,))

    @cached_read
    def technicians(self, specialty_id=None):
        with transaction(read_only=True) as cursor:
            cursor.execute("""SELECT u.id,u.name,u.email,u.active,
                GROUP_CONCAT(s.name ORDER BY s.name SEPARATOR ', ') AS specialties
                FROM mt_technicians tech JOIN mt_users u ON u.id=tech.user_id
                LEFT JOIN mt_technician_specialties ts ON ts.technician_id=tech.user_id
                LEFT JOIN mt_specialties s ON s.id=ts.specialty_id"""
                + (" WHERE u.active=1 AND EXISTS (SELECT 1 FROM mt_technician_specialties eligible WHERE eligible.technician_id=u.id AND eligible.specialty_id=%s)" if specialty_id else "")
                + " GROUP BY u.id,u.name,u.email,u.active ORDER BY u.name", (specialty_id,) if specialty_id else ())
            return cursor.fetchall()

    @cached_read
    def technician_specialties(self, user_id):
        with transaction(read_only=True) as cursor:
            cursor.execute("SELECT specialty_id FROM mt_technician_specialties WHERE technician_id=%s", (user_id,))
            return {row["specialty_id"] for row in cursor.fetchall()}

    def save_technician(self, user_id, specialty_ids):
        if not user_id or not specialty_ids:
            raise AppError("Selecciona un usuario y al menos una especialidad.")
        with transaction() as cursor:
            cursor.execute("SELECT user_id FROM mt_technicians WHERE user_id=%s", (user_id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO mt_technicians(user_id) VALUES(%s)", (user_id,))
            cursor.execute("SELECT specialty_id FROM mt_technician_specialties WHERE technician_id=%s", (user_id,))
            existing = {row["specialty_id"] for row in cursor.fetchall()}
            desired = {int(value) for value in specialty_ids}
            for specialty in existing - desired:
                cursor.execute("DELETE FROM mt_technician_specialties WHERE technician_id=%s AND specialty_id=%s", (user_id, specialty))
            for specialty in desired - existing:
                cursor.execute("INSERT INTO mt_technician_specialties(technician_id,specialty_id) VALUES(%s,%s)", (user_id, specialty))

    def delete_technician(self, user_id):
        with transaction() as cursor:
            cursor.execute("DELETE FROM mt_technicians WHERE user_id=%s", (user_id,))
