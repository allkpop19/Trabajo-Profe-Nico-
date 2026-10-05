-- JOIN: lista utilizada en la pantalla de tickets.
SELECT t.id,t.title,t.status,t.priority,u.name AS requester,d.name AS department,
       s.name AS specialty,tech.name AS technician
FROM mt_tickets t
JOIN mt_users u ON u.id=t.requester_id
JOIN mt_departments d ON d.id=u.department_id
JOIN mt_specialties s ON s.id=t.specialty_id
LEFT JOIN mt_users tech ON tech.id=t.technician_id
ORDER BY t.created_at DESC,t.id DESC;

-- GROUP BY: resumen utilizado en el panel principal.
SELECT s.name AS specialty,COUNT(t.id) AS total,
       SUM(CASE WHEN t.status IN ('abierto','en_progreso') THEN 1 ELSE 0 END) AS pending
FROM mt_specialties s LEFT JOIN mt_tickets t ON t.specialty_id=s.id
GROUP BY s.id,s.name ORDER BY total DESC,s.name;

-- Historial registrado por la aplicación y el procedimiento.
SELECT ticket_id,action,old_status,new_status,changed_at
FROM mt_ticket_history ORDER BY id DESC;

-- Ejemplo: reemplazar los ids con valores existentes.
-- CALL mt_assign_ticket(1,1);
