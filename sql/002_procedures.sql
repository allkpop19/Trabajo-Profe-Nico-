-- La aplicación controla COMMIT/ROLLBACK. No inicia una transacción anidada.
DELIMITER $$
CREATE PROCEDURE mt_assign_ticket(IN p_ticket_id INT UNSIGNED, IN p_technician_id INT UNSIGNED)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_specialty INT UNSIGNED DEFAULT NULL;
    DECLARE v_status VARCHAR(20);
    DECLARE v_technician INT UNSIGNED;
    -- Serializa dos intentos de asignar el mismo ticket.
    SELECT specialty_id,status,technician_id INTO v_specialty,v_status,v_technician
    FROM mt_tickets WHERE id=p_ticket_id FOR UPDATE;
    IF v_specialty IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El ticket no existe';
    END IF;
    IF v_status NOT IN ('abierto','en_progreso') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Solo se asignan tickets abiertos o en progreso';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM mt_technician_specialties ts
        JOIN mt_users u ON u.id=ts.technician_id
        WHERE ts.technician_id=p_technician_id AND ts.specialty_id=v_specialty AND u.active=1
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El tecnico no esta activo o no tiene la especialidad';
    END IF;
    UPDATE mt_tickets SET technician_id=p_technician_id,status='en_progreso',version=version+1 WHERE id=p_ticket_id;
    INSERT INTO mt_ticket_history(ticket_id,action,old_status,new_status,old_technician_id,new_technician_id)
    VALUES(p_ticket_id,'asignacion',v_status,'en_progreso',v_technician,p_technician_id);
END$$
DELIMITER ;
