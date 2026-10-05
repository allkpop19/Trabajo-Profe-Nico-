# Mesa TI avance de base de datos

Autor: Kevin Carrera.

Esta copia corresponde a la etapa del proyecto con el modelo de datos y la capa de acceso a MySQL implementados. Se obtuvo del commit bfa2a65 del proyecto principal.

## Implementado

- Siete tablas de negocio con relaciones 1:1, 1:N y N:M.
- Claves primarias, claves foráneas y restricciones CHECK.
- Procedimiento almacenado de asignación de tickets.
- Datos ficticios de demostración y consultas JOIN y GROUP BY.
- Configuración por variables de entorno.
- Capa de consultas, operaciones CRUD, validaciones y transacciones.
- Instalador de la base de datos.

## Pendiente

- Crear main.py y la interfaz Flet.
- Conectar los formularios, listas, filtros y mensajes a las operaciones de la base.
- Verificar las operaciones desde la interfaz.
- Agregar una captura de la aplicación y completar el README final.

Esta etapa todavía no contiene una aplicación gráfica ejecutable. No utiliza triggers, conforme al alcance acordado.

## Preparar el entorno

Desde PowerShell dentro de esta carpeta:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Configura .env con tus credenciales y el puerto 5434. La copia incluye solamente el ejemplo de configuración, sin credenciales reales.

```powershell
.\.venv\Scripts\python.exe scripts\inspect_connection.py
.\.venv\Scripts\python.exe scripts\init_db.py
```

Si utilizas la misma base preparada en el proyecto principal, el instalador detectará las migraciones ya aplicadas y conservará los datos.

## Registrar este avance

El repositorio Git de esta carpeta está inicializado, sin commits. Para crear el primer commit:

```powershell
git add .
git commit -m "feat: implementar base de datos y operaciones de soporte TI"
```

Después continúa el trabajo en esta misma carpeta y registra los siguientes cambios en nuevos commits.
