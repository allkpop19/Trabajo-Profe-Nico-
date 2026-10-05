-- Datos ficticios de demostración; no son personas ni correos reales.
INSERT INTO mt_departments(name) VALUES ('Administración'),('Operaciones'),('Tecnología');
INSERT INTO mt_specialties(name) VALUES ('Redes'),('Hardware'),('Software'),('Accesos');
INSERT INTO mt_users(name,email,department_id) VALUES
('Kevin Carrera','kevin@example.test',(SELECT id FROM mt_departments WHERE name='Tecnología')),
('Valentina Soto','valentina@example.test',(SELECT id FROM mt_departments WHERE name='Administración')),
('Diego Rojas','diego@example.test',(SELECT id FROM mt_departments WHERE name='Operaciones')),
('Camila Torres','camila@example.test',(SELECT id FROM mt_departments WHERE name='Tecnología'));
INSERT INTO mt_technicians(user_id) SELECT id FROM mt_users WHERE email IN ('kevin@example.test','camila@example.test');
INSERT INTO mt_technician_specialties(technician_id,specialty_id)
SELECT u.id,s.id FROM mt_users u CROSS JOIN mt_specialties s
WHERE (u.email='kevin@example.test' AND s.name IN ('Redes','Hardware'))
OR (u.email='camila@example.test' AND s.name IN ('Software','Accesos'));
INSERT INTO mt_tickets(title,description,requester_id,specialty_id,priority) VALUES
('Sin conexión en sala de reuniones','El equipo de la sala no logra conectarse a la red corporativa.',
(SELECT id FROM mt_users WHERE email='valentina@example.test'),(SELECT id FROM mt_specialties WHERE name='Redes'),'alta'),
('Impresora de operaciones detenida','La impresora muestra un atasco aunque la bandeja está despejada.',
(SELECT id FROM mt_users WHERE email='diego@example.test'),(SELECT id FROM mt_specialties WHERE name='Hardware'),'media'),
('Aplicación de inventario no abre','El sistema de inventario muestra un error al iniciar sesión.',
(SELECT id FROM mt_users WHERE email='diego@example.test'),(SELECT id FROM mt_specialties WHERE name='Software'),'critica'),
('Solicitud de acceso a carpeta compartida','Se requiere acceso de lectura a la carpeta de reportes mensuales.',
(SELECT id FROM mt_users WHERE email='valentina@example.test'),(SELECT id FROM mt_specialties WHERE name='Accesos'),'baja');
INSERT INTO mt_ticket_history(ticket_id,action,new_status)
SELECT id,'creacion','abierto' FROM mt_tickets;
SET @mt_ticket=(SELECT id FROM mt_tickets WHERE title='Sin conexión en sala de reuniones');
SET @mt_tech=(SELECT id FROM mt_users WHERE email='kevin@example.test');
CALL mt_assign_ticket(@mt_ticket,@mt_tech);
SET @mt_ticket=(SELECT id FROM mt_tickets WHERE title='Aplicación de inventario no abre');
SET @mt_tech=(SELECT id FROM mt_users WHERE email='camila@example.test');
CALL mt_assign_ticket(@mt_ticket,@mt_tech);
