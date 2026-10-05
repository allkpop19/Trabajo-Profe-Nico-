"""Interfaz Flet en español con formularios, filtros y confirmaciones."""
import logging
from functools import wraps
from threading import RLock
import flet as ft
from app.db import AppError
from app.repository import Repository
from app.validation import LABELS, PRIORITIES, STATUSES

INK = "#14283F"
MUTED = "#627388"
BLUE = "#246BFD"
BG = "#F3F6FA"
LINE = "#E3EAF2"
STATUS_COLOR = {"abierto": ("#FFF2DD", "#A66507"), "en_progreso": ("#E7EFFF", "#215FD2"),
                "resuelto": ("#E3F5EE", "#147957"), "cerrado": ("#EDF0F4", "#627388")}


def main(page: ft.Page):
    page.title = "Mesa TI | Soporte técnico"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=BLUE, font_family="Segoe UI")
    page.bgcolor = BG
    page.padding = 0
    repo = Repository()
    current = {"view": "Resumen", "ticket_page": 0}
    ui_lock = RLock()
    body = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20)
    heading = ft.Text(size=28, weight=ft.FontWeight.W_700, color=INK)
    subtitle = ft.Text(color=MUTED, size=13)
    connection_badge = ft.Text("Conectando", size=12, color=MUTED)
    search = ft.TextField(hint_text="Buscar título, descripción o persona", prefix_icon=ft.Icons.SEARCH,
                          expand=True, bgcolor="white", border_color=LINE, text_size=13)
    state_filter = ft.Dropdown(label="Estado", width=155, value="", options=[ft.dropdown.Option("", "Todos")]
                               + [ft.dropdown.Option(x, LABELS[x]) for x in STATUSES])
    priority_filter = ft.Dropdown(label="Prioridad", width=145, value="", options=[ft.dropdown.Option("", "Todas")]
                                  + [ft.dropdown.Option(x, LABELS[x]) for x in PRIORITIES])
    specialty_filter = ft.Dropdown(label="Especialidad", width=180, value="")

    def notify(message, error=False):
        page.open(ft.SnackBar(ft.Text(message, color="white"), bgcolor="#B83434" if error else "#147957"))

    def safe(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            try:
                with ui_lock:
                    return function(*args, **kwargs)
            except AppError as error:
                notify(str(error), True)
            except Exception:
                logging.exception("Error inesperado en la interfaz")
                notify("Ocurrió un error inesperado. Puedes volver a intentar la operación.", True)
        return wrapper

    def panel(control, padding=20):
        return ft.Container(control, bgcolor="white", border_radius=14,
                            border=ft.border.all(1, LINE), padding=padding)

    def badge(status):
        bg, color = STATUS_COLOR[status]
        return ft.Container(ft.Text(LABELS[status], size=11, weight=ft.FontWeight.W_600, color=color),
                            bgcolor=bg, padding=ft.padding.symmetric(8, 5), border_radius=20)

    def button(label, action, icon=None):
        return ft.FilledButton(label, icon=icon, on_click=safe(action), bgcolor=BLUE, color="white", height=40)

    def dialog(title, controls, on_save=None, width=520):
        form_error = ft.Text(color="#B83434", size=12, visible=False)
        result = ft.AlertDialog(modal=True, title=ft.Text(title, color=INK, weight=ft.FontWeight.W_600),
                                content=ft.Container(ft.Column(controls + [form_error], tight=True, scroll=ft.ScrollMode.AUTO, spacing=14),
                                                     width=width, height=min(520, max(100, 70 * sum(c.visible is not False for c in controls)))),
                                actions=[ft.TextButton("Cancelar" if on_save else "Cerrar", on_click=lambda e: page.close(result))])
        if on_save:
            @safe
            def save(e):
                if not result.open:
                    return
                try:
                    on_save()
                except AppError as error:
                    form_error.value = str(error)
                    if not form_error.visible:
                        result.content.height = min(520, result.content.height + 45)
                    form_error.visible = True
                    page.update()
                    return
                page.close(result)
                render()
                notify("Cambios guardados correctamente.")
            result.actions.append(button("Guardar", save, ft.Icons.CHECK))
        page.open(result)
        return result

    def confirm(title, message, action):
        result = ft.AlertDialog(modal=True, title=ft.Text(title), content=ft.Text(message))
        @safe
        def accept(e):
            if not result.open:
                return
            action()
            page.close(result)
            render()
            notify("Registro eliminado correctamente.")
        result.actions = [ft.TextButton("Cancelar", on_click=lambda e: page.close(result)),
                          ft.TextButton("Eliminar", on_click=accept, style=ft.ButtonStyle(color="#B83434"))]
        page.open(result)

    def dropdown(label, records, value=None, **kwargs):
        return ft.Dropdown(label=label, value=str(value) if value is not None else None,
                           options=[ft.dropdown.Option(str(r["id"]), r["name"]) for r in records], **kwargs)

    @safe
    def ticket_form(ticket=None):
        item = repo.ticket(ticket["id"]) if ticket else {}
        if item.get("status") == "cerrado":
            raise AppError("Un ticket cerrado solo permite consultar sus datos.")
        title = ft.TextField(label="Título", value=item.get("title", ""), max_length=140)
        description = ft.TextField(label="Descripción del problema", value=item.get("description", ""), multiline=True, min_lines=2, max_lines=4)
        users = repo.users(active_only=True)
        if item and not any(u["id"] == item["requester_id"] for u in users):
            users += [u for u in repo.users() if u["id"] == item["requester_id"]]
        requester = dropdown("Solicitante", users, item.get("requester_id"), expand=True)
        specialty = dropdown("Especialidad requerida", repo.catalog("specialties"), item.get("specialty_id"), expand=True,
                             disabled=bool(item.get("technician_id")))
        priority = ft.Dropdown(label="Prioridad", value=item.get("priority", "media"),
                               options=[ft.dropdown.Option(x, LABELS[x]) for x in PRIORITIES], expand=True)
        allowed = {"abierto": ["abierto"], "en_progreso": ["en_progreso", "resuelto"],
                   "resuelto": ["resuelto", "en_progreso", "cerrado"]}
        status = ft.Dropdown(label="Estado", value=item.get("status", "abierto"), expand=True,
                             options=[ft.dropdown.Option(x, LABELS[x]) for x in allowed[item.get("status", "abierto")]])
        solution = ft.TextField(label="Solución aplicada", value=item.get("solution") or "", multiline=True,
                               min_lines=2, max_lines=4, visible=bool(item))
        def save():
            repo.save_ticket(dict(title=title.value, description=description.value, requester_id=requester.value,
                                  specialty_id=specialty.value, priority=priority.value, status=status.value,
                                  solution=solution.value), item.get("id"), item.get("version"))
        controls = [title, description, ft.Row([requester, specialty]), ft.Row([priority, status]), solution]
        if item.get("technician_id"):
            controls.append(ft.Text(f"Técnico asignado: {item['technician']}", color=MUTED, size=12))
        elif item:
            controls.append(ft.Text("Asigna un técnico desde la lista para iniciar la atención.", color=MUTED, size=12))
        dialog(f"Editar ticket #{item['id']:04d}" if item else "Nuevo ticket", controls, save, 600)

    @safe
    def assignment(ticket):
        candidates = repo.technicians(ticket["specialty_id"])
        if not candidates:
            raise AppError("No hay técnicos activos con esta especialidad. Agrégalos en Técnicos.")
        technician = dropdown("Técnico disponible", candidates, ticket.get("technician_id"))
        def save_assignment():
            if not technician.value:
                raise AppError("Selecciona un técnico.")
            repo.assign(ticket["id"], int(technician.value))
        dialog(f"Asignar ticket #{ticket['id']:04d}", [ft.Text(ticket["title"], weight=ft.FontWeight.W_600),
                ft.Text(f"Especialidad: {ticket['specialty']}", color=MUTED), technician],
                save_assignment)

    @safe
    def detail(ticket):
        item = repo.ticket(ticket["id"])
        history = repo.history(item["id"])
        controls = [badge(item["status"]), ft.Text(item["title"], size=19, weight=ft.FontWeight.W_600),
                    ft.Text(item["description"]), ft.Text(f"Solicitante: {item['requester']} · {item['department']}"),
                    ft.Text(f"Especialidad: {item['specialty']} · Técnico: {item['technician'] or 'Sin asignar'}"),
                    ft.Text(f"Prioridad: {LABELS[item['priority']]} · Creado: {item['created_at']:%d/%m/%Y %H:%M}"),
                    ft.Text(f"Solución: {item['solution'] or 'Pendiente'}"),
                    ft.Divider(color=LINE), ft.Text("Historial de atención", weight=ft.FontWeight.W_600)]
        for h in history:
            labels = {"creacion": "Creación", "asignacion": "Asignación", "estado": "Cambio de estado", "edicion": "Edición"}
            change = f"{LABELS.get(h['old_status'], 'Nuevo')} → {LABELS[h['new_status']]}"
            tech = f" · {h['new_technician']}" if h["new_technician"] else ""
            controls.append(ft.Text(f"{h['changed_at']:%d/%m %H:%M}  {labels[h['action']]} · {change}{tech}", size=12, color=MUTED))
        dialog(f"Ticket #{item['id']:04d}", controls, width=660)

    def icon_action(icon, tooltip, callback, disabled=False):
        return ft.IconButton(icon, tooltip=tooltip, icon_size=19, icon_color=MUTED, on_click=safe(callback), disabled=disabled)

    def ticket_table(rows, compact=False):
        if not rows:
            return panel(ft.Column([ft.Icon(ft.Icons.INBOX_OUTLINED, size=38, color=MUTED),
                                   ft.Text("No hay tickets que coincidan", size=18, color=INK),
                                   ft.Text("Cambia los filtros o registra una solicitud.", color=MUTED)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        columns = ["Ticket y solicitud", "Solicitante", "Especialidad", "Prioridad", "Estado", "Técnico", "Acciones"]
        result = []
        for ticket in rows:
            actions = ft.Row([
                icon_action(ft.Icons.VISIBILITY_OUTLINED, "Ver detalle e historial", lambda e, t=ticket: detail(t)),
                icon_action(ft.Icons.EDIT_OUTLINED, "Editar ticket", lambda e, t=ticket: ticket_form(t), ticket["status"] == "cerrado"),
                icon_action(ft.Icons.PERSON_ADD_ALT_1, "Asignar técnico", lambda e, t=ticket: assignment(t), ticket["status"] not in ("abierto", "en_progreso")),
                icon_action(ft.Icons.DELETE_OUTLINE, "Eliminar ticket", lambda e, t=ticket: confirm("Eliminar ticket", "Se eliminarán la solicitud y su historial de creación. Esta acción no se puede deshacer.",
                            lambda: repo.delete_ticket(t["id"], t["version"])), ticket["status"] != "abierto" or bool(ticket["technician_id"]))
            ], spacing=0)
            result.append(ft.DataRow(cells=[
                ft.DataCell(ft.Container(ft.Column([ft.Text(f"#{ticket['id']:04d}", size=11, color=BLUE, weight=ft.FontWeight.W_600),
                    ft.Text(ticket["title"], size=12, color=INK, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)], spacing=4), width=245)),
                ft.DataCell(ft.Text(ticket["requester"], size=12)), ft.DataCell(ft.Text(ticket["specialty"], size=12)),
                ft.DataCell(ft.Text(LABELS[ticket["priority"]], size=12, color="#B83434" if ticket["priority"] == "critica" else INK)),
                ft.DataCell(badge(ticket["status"])), ft.DataCell(ft.Text(ticket["technician"] or "Sin asignar", size=12, color=MUTED)), ft.DataCell(actions)]))
        table = ft.DataTable(columns=[ft.DataColumn(ft.Text(c, size=11, weight=ft.FontWeight.W_600, color=MUTED)) for c in columns],
                            rows=result, heading_row_color="#F8FAFD", data_row_min_height=72, data_row_max_height=78,
                            horizontal_margin=16, column_spacing=18, divider_thickness=0.5)
        return panel(ft.Row([table], scroll=ft.ScrollMode.AUTO), 0)

    # Mantener los mismos controles evita perder clics mientras cambia la lista.
    ticket_filters_panel = panel(ft.Column([
        ft.Row([search, button("Buscar", lambda e: apply_filters(), ft.Icons.SEARCH),
                button("Nuevo ticket", lambda e: ticket_form(), ft.Icons.ADD)]),
        ft.Row([state_filter, priority_filter, specialty_filter,
                ft.TextButton("Limpiar filtros", on_click=lambda e: clear_filters())], wrap=True)
    ]))

    def render_dashboard():
        heading.value = "Tu mesa de soporte, en orden"
        subtitle.value = "Un vistazo a las solicitudes y a la carga de atención del equipo."
        counts, summary, priorities, recent = repo.dashboard()
        cards = []
        for state, icon in (("abierto", ft.Icons.INBOX_OUTLINED), ("en_progreso", ft.Icons.TIMELAPSE),
                            ("resuelto", ft.Icons.TASK_ALT), ("cerrado", ft.Icons.INVENTORY_2_OUTLINED)):
            bg, color = STATUS_COLOR[state]
            cards.append(ft.Container(panel(ft.Column([ft.Row([ft.Text(LABELS[state], color=MUTED, size=13),
                ft.Container(ft.Icon(icon, color=color, size=19), bgcolor=bg, padding=7, border_radius=10)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(str(counts.get(state, 0)), size=34, weight=ft.FontWeight.W_700, color=INK)], spacing=8)), col={"xs": 6, "md": 3}))
        body.controls.append(ft.ResponsiveRow(cards))
        summary_rows = [ft.DataRow(cells=[ft.DataCell(ft.Text(r["specialty"])), ft.DataCell(ft.Text(str(r["total"]))),
                        ft.DataCell(ft.Text(str(r["pending"] or 0)))]) for r in summary]
        summary_table = ft.DataTable(columns=[ft.DataColumn(ft.Text(x, weight=ft.FontWeight.W_600, size=12)) for x in ("Especialidad", "Total", "Pendientes")], rows=summary_rows)
        body.controls.append(ft.ResponsiveRow([
            ft.Container(panel(ft.Column([ft.Text("Carga por especialidad", size=17, weight=ft.FontWeight.W_600, color=INK), summary_table])), col={"xs": 12, "md": 7}),
            ft.Container(panel(ft.Column([ft.Text("Atención prioritaria", size=17, weight=ft.FontWeight.W_600, color=INK),
                ft.Text(str(priorities.get("critica", 0)), size=40, weight=ft.FontWeight.W_700, color="#B83434"),
                ft.Text("tickets críticos pendientes", color=MUTED), ft.Text("Asigna cada solicitud a un técnico con la especialidad adecuada.", color=MUTED, size=13),
                button("Ver todos los tickets", lambda e: navigate("Tickets"), ft.Icons.ARROW_FORWARD)])), col={"xs": 12, "md": 5})]))
        body.controls.append(ft.Row([ft.Text("Solicitudes recientes", size=18, weight=ft.FontWeight.W_600, color=INK),
                                     button("Nuevo ticket", lambda e: ticket_form(), ft.Icons.ADD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        body.controls.append(ticket_table(recent))

    def render_tickets():
        heading.value = "Tickets de soporte"
        subtitle.value = "Registra, asigna y da seguimiento a cada solicitud."
        specialty_filter.options = [ft.dropdown.Option("", "Todas")] + [ft.dropdown.Option(str(r["id"]), r["name"]) for r in repo.catalog("specialties")]
        body.controls.append(ticket_filters_panel)
        filters = (search.value or "", state_filter.value or "", priority_filter.value or "", specialty_filter.value or "")
        rows, total = repo.ticket_page(*filters, page=current["ticket_page"])
        if not rows and total and current["ticket_page"]:
            current["ticket_page"] = max(0, (total - 1) // 25)
            rows, total = repo.ticket_page(*filters, page=current["ticket_page"])
        noun = "solicitud encontrada" if total == 1 else "solicitudes encontradas"
        body.controls.append(ft.Text(f"{total} {noun}", size=12, color=MUTED))
        body.controls.append(ticket_table(rows))
        if total > 25:
            body.controls.append(ft.Row([
                ft.TextButton("Anterior", on_click=safe(lambda e: change_page(-1)), disabled=current["ticket_page"] == 0),
                ft.Text(f"Página {current['ticket_page'] + 1} de {(total + 24) // 25}", size=12, color=MUTED),
                ft.TextButton("Siguiente", on_click=safe(lambda e: change_page(1)), disabled=(current["ticket_page"] + 1) * 25 >= total)
            ], alignment=ft.MainAxisAlignment.CENTER))

    @safe
    def user_form(item=None):
        item = item or {}
        name = ft.TextField(label="Nombre", value=item.get("name", ""), max_length=100)
        email = ft.TextField(label="Correo electrónico", value=item.get("email", ""), max_length=160)
        department = dropdown("Departamento", repo.catalog("departments"), item.get("department_id"))
        active = ft.Switch(label="Usuario activo", value=bool(item.get("active", True)))
        dialog("Editar usuario" if item else "Nuevo usuario", [name, email, department, active],
               lambda: repo.save_user(name.value, email.value, department.value, active.value, item.get("id")))

    def render_users():
        heading.value = "Usuarios y solicitantes"
        subtitle.value = "Cada persona pertenece a un departamento y puede tener un perfil técnico."
        body.controls.append(ft.Row([ft.Text("Personas de la organización", size=18, color=INK),
                                     button("Nuevo usuario", lambda e: user_form(), ft.Icons.PERSON_ADD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        rows = []
        for user in repo.users():
            rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(user["name"])), ft.DataCell(ft.Text(user["email"])),
                ft.DataCell(ft.Text(user["department"])), ft.DataCell(ft.Text("Sí" if user["is_technician"] else "No")),
                ft.DataCell(ft.Text("Activo" if user["active"] else "Inactivo")), ft.DataCell(ft.Row([
                    icon_action(ft.Icons.EDIT_OUTLINED, "Editar usuario", lambda e, u=user: user_form(u)),
                    icon_action(ft.Icons.DELETE_OUTLINE, "Eliminar usuario", lambda e, u=user: confirm("Eliminar usuario", "Si tiene tickets o un perfil técnico, la base protegerá sus referencias. Puedes desactivarlo desde Editar.", lambda: repo.delete_user(u["id"])))], spacing=0))]))
        table = ft.DataTable(columns=[ft.DataColumn(ft.Text(x, size=12, weight=ft.FontWeight.W_600)) for x in ("Nombre", "Correo", "Departamento", "Técnico", "Estado", "Acciones")], rows=rows)
        body.controls.append(panel(ft.Row([table], scroll=ft.ScrollMode.AUTO), 10))

    @safe
    def technician_form(item=None):
        item = item or {}
        users = repo.users(active_only=True)
        if item and not any(u["id"] == item["id"] for u in users):
            users += [u for u in repo.users() if u["id"] == item["id"]]
        user = dropdown("Usuario", users, item.get("id"), disabled=bool(item))
        selected = repo.technician_specialties(item["id"]) if item else set()
        checks = [ft.Checkbox(label=s["name"], value=s["id"] in selected, data=s["id"]) for s in repo.catalog("specialties")]
        dialog("Editar perfil técnico" if item else "Nuevo perfil técnico", [user, ft.Text("Especialidades que puede atender", color=MUTED)] + checks,
               lambda: repo.save_technician(int(user.value) if user.value else None, [c.data for c in checks if c.value]))

    def render_technicians():
        heading.value = "Equipo técnico"
        subtitle.value = "Perfiles y especialidades disponibles para asignar solicitudes."
        body.controls.append(ft.Row([ft.Text("Técnicos y sus especialidades", size=18, color=INK),
            button("Nuevo técnico", lambda e: technician_form(), ft.Icons.PERSON_ADD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        cards = []
        for item in repo.technicians():
            cards.append(ft.Container(panel(ft.Column([
                ft.Row([ft.CircleAvatar(content=ft.Text(item["name"][0], color=BLUE), bgcolor="#E7EFFF"),
                        ft.Column([ft.Text(item["name"], weight=ft.FontWeight.W_600, color=INK), ft.Text(item["email"], size=12, color=MUTED)])]),
                ft.Text(item["specialties"] or "Sin especialidades", size=13, color=INK),
                ft.Text("Activo" if item["active"] else "Inactivo", size=12, color=MUTED),
                ft.Row([ft.TextButton("Editar especialidades", on_click=safe(lambda e, t=item: technician_form(t))),
                    icon_action(ft.Icons.DELETE_OUTLINE, "Eliminar perfil técnico", lambda e, t=item: confirm("Eliminar perfil técnico", "El usuario se conserva. Solo se elimina el perfil si no tiene tickets asignados.", lambda: repo.delete_technician(t["id"])))])])), col={"xs": 12, "md": 6}))
        body.controls.append(ft.ResponsiveRow(cards) if cards else ft.Text("Aún no hay técnicos registrados."))

    @safe
    def catalog_form(kind, item=None):
        item = item or {}
        name = ft.TextField(label="Nombre", value=item.get("name", ""), max_length=80)
        dialog("Editar registro" if item else "Nuevo registro", [name], lambda: repo.save_catalog(kind, name.value, item.get("id")))

    def render_catalogs():
        heading.value = "Catálogos de soporte"
        subtitle.value = "Organiza los departamentos y las especialidades del equipo."
        cards = []
        for kind, label in (("departments", "Departamentos"), ("specialties", "Especialidades")):
            controls = [ft.Row([ft.Text(label, size=18, color=INK, weight=ft.FontWeight.W_600),
                icon_action(ft.Icons.ADD, f"Agregar {label.lower()}", lambda e, k=kind: catalog_form(k))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)]
            for record in repo.catalog(kind):
                controls.append(ft.Row([ft.Text(record["name"], expand=True),
                    icon_action(ft.Icons.EDIT_OUTLINED, "Editar registro", lambda e, k=kind, r=record: catalog_form(k, r)),
                    icon_action(ft.Icons.DELETE_OUTLINE, "Eliminar registro", lambda e, k=kind, r=record: confirm("Eliminar registro", "La base impedirá eliminarlo si tiene registros relacionados.", lambda: repo.delete_catalog(k, r["id"])))], spacing=0))
            cards.append(ft.Container(panel(ft.Column(controls)), col={"xs": 12, "md": 6}))
        body.controls.append(ft.ResponsiveRow(cards))

    @safe
    def render(force=False):
        if force:
            repo.refresh()
        body.controls.clear()
        try:
            {"Resumen": render_dashboard, "Tickets": render_tickets, "Usuarios": render_users,
             "Técnicos": render_technicians, "Catálogos": render_catalogs}[current["view"]]()
            connection_badge.value = "Base de datos conectada"
            connection_badge.color = "#147957"
        except AppError as error:
            connection_badge.value = "Conexión no disponible"
            connection_badge.color = "#B83434"
            body.controls = [panel(ft.Column([ft.Icon(ft.Icons.CLOUD_OFF, color=MUTED, size=40),
                ft.Text("No se pudieron cargar los datos", size=20, color=INK), ft.Text(str(error), color=MUTED),
                button("Reintentar conexión", lambda e: render(force=True), ft.Icons.REFRESH)]))]
        page.update()

    def navigate(view):
        current["view"] = view
        for name, control in nav_buttons.items():
            control.bgcolor = "#E7EFFF" if name == view else None
        render()

    @safe
    def clear_filters():
        search.value = ""
        state_filter.value = priority_filter.value = specialty_filter.value = ""
        apply_filters()

    def apply_filters():
        current["ticket_page"] = 0
        render()

    def change_page(delta):
        current["ticket_page"] = max(0, current["ticket_page"] + delta)
        render()

    search.on_submit = safe(lambda e: apply_filters())
    for field in (state_filter, priority_filter, specialty_filter):
        field.on_change = safe(lambda e: apply_filters())
    nav_buttons = {}
    for name, icon in (("Resumen", ft.Icons.GRID_VIEW_ROUNDED), ("Tickets", ft.Icons.CONFIRMATION_NUMBER_OUTLINED),
                       ("Usuarios", ft.Icons.PEOPLE_OUTLINE), ("Técnicos", ft.Icons.ENGINEERING_OUTLINED), ("Catálogos", ft.Icons.FOLDER_OUTLINED)):
        nav_buttons[name] = ft.Container(ft.Row([ft.Icon(icon, size=20, color=BLUE if name == "Resumen" else MUTED),
            ft.Text(name, size=13, color=INK, weight=ft.FontWeight.W_500)]), padding=13, border_radius=10,
            bgcolor="#E7EFFF" if name == "Resumen" else None, on_click=safe(lambda e, n=name: navigate(n)))
    sidebar = ft.Container(ft.Column([
        ft.Row([ft.Container(ft.Icon(ft.Icons.SUPPORT_AGENT, color="white", size=23), bgcolor=BLUE, padding=9, border_radius=12),
                ft.Column([ft.Text("Mesa TI", size=22, color=INK, weight=ft.FontWeight.W_700), ft.Text("SOPORTE INTERNO", size=9, color=MUTED)], spacing=2)]),
        ft.Container(height=23), *nav_buttons.values(), ft.Container(expand=True),
        ft.Container(ft.Column([ft.Text("Kevin Carrera", size=13, weight=ft.FontWeight.W_600, color=INK),
            ft.Text("Proyecto de soporte TI", size=11, color=MUTED)]), padding=10)
    ], spacing=6, expand=True), width=210, bgcolor="white", padding=22, border=ft.border.only(right=ft.BorderSide(1, LINE)))
    header = ft.Row([ft.Column([heading, subtitle], spacing=6, expand=True),
                     ft.Column([connection_badge, ft.TextButton("Actualizar", icon=ft.Icons.REFRESH, on_click=safe(lambda e: render(force=True)))], horizontal_alignment=ft.CrossAxisAlignment.END)], vertical_alignment=ft.CrossAxisAlignment.START)
    content = ft.Container(ft.Column([header, body], expand=True, spacing=26), padding=28, expand=True)
    page.add(ft.Row([sidebar, content], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH))
    with ui_lock:
        render()
