-- MariaDB 10.6+ / MySQL 8.0.16+. Ejecutar en la base ya asignada.
-- Prefijo mt_ para mantener aisladas las tablas de este proyecto.
CREATE TABLE mt_departments (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    CONSTRAINT ck_mt_department_name CHECK (CHAR_LENGTH(TRIM(name)) >= 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mt_users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    department_id INT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_mt_user_department FOREIGN KEY (department_id) REFERENCES mt_departments(id),
    CONSTRAINT ck_mt_user_name CHECK (CHAR_LENGTH(TRIM(name)) >= 2),
    CONSTRAINT ck_mt_user_email CHECK (email LIKE '%_@_%._%'),
    CONSTRAINT ck_mt_user_active CHECK (active IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PK compartida: cada usuario tiene como máximo un perfil técnico (1:1).
CREATE TABLE mt_technicians (
    user_id INT UNSIGNED PRIMARY KEY,
    CONSTRAINT fk_mt_technician_user FOREIGN KEY (user_id) REFERENCES mt_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mt_specialties (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    CONSTRAINT ck_mt_specialty_name CHECK (CHAR_LENGTH(TRIM(name)) >= 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- N:M con PK compuesta: evita asignar dos veces la misma especialidad.
CREATE TABLE mt_technician_specialties (
    technician_id INT UNSIGNED NOT NULL,
    specialty_id INT UNSIGNED NOT NULL,
    PRIMARY KEY (technician_id, specialty_id),
    CONSTRAINT fk_mt_ts_technician FOREIGN KEY (technician_id) REFERENCES mt_technicians(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_mt_ts_specialty FOREIGN KEY (specialty_id) REFERENCES mt_specialties(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mt_tickets (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(140) NOT NULL,
    description TEXT NOT NULL,
    requester_id INT UNSIGNED NOT NULL,
    specialty_id INT UNSIGNED NOT NULL,
    technician_id INT UNSIGNED NULL,
    priority ENUM('baja','media','alta','critica') NOT NULL DEFAULT 'media',
    status ENUM('abierto','en_progreso','resuelto','cerrado') NOT NULL DEFAULT 'abierto',
    solution TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL,
    version INT UNSIGNED NOT NULL DEFAULT 1,
    CONSTRAINT fk_mt_ticket_requester FOREIGN KEY (requester_id) REFERENCES mt_users(id),
    CONSTRAINT fk_mt_ticket_specialty FOREIGN KEY (specialty_id) REFERENCES mt_specialties(id),
    CONSTRAINT fk_mt_ticket_technician FOREIGN KEY (technician_id) REFERENCES mt_technicians(user_id),
    -- Una asignación exige la combinación técnico/especialidad real en la N:M.
    CONSTRAINT fk_mt_ticket_skill FOREIGN KEY (technician_id, specialty_id)
        REFERENCES mt_technician_specialties(technician_id, specialty_id),
    CONSTRAINT ck_mt_ticket_title CHECK (CHAR_LENGTH(TRIM(title)) BETWEEN 5 AND 140),
    CONSTRAINT ck_mt_ticket_description CHECK (CHAR_LENGTH(TRIM(description)) >= 10),
    CONSTRAINT ck_mt_ticket_assignment CHECK (status='abierto' OR technician_id IS NOT NULL),
    CONSTRAINT ck_mt_ticket_solution CHECK (status NOT IN ('resuelto','cerrado') OR CHAR_LENGTH(TRIM(COALESCE(solution,''))) >= 10),
    INDEX ix_mt_ticket_status_priority (status, priority),
    INDEX ix_mt_ticket_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mt_ticket_history (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT UNSIGNED NOT NULL,
    action VARCHAR(30) NOT NULL,
    old_status VARCHAR(20) NULL,
    new_status VARCHAR(20) NOT NULL,
    old_technician_id INT UNSIGNED NULL,
    new_technician_id INT UNSIGNED NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mt_history_ticket FOREIGN KEY (ticket_id) REFERENCES mt_tickets(id) ON DELETE CASCADE,
    INDEX ix_mt_history_ticket_date (ticket_id, changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
