CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(225) NOT NULL
);

CREATE TABLE IF NOT EXISTS classrooms (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    room_number VARCHAR(20) NOT NULL,
    capacity INTEGER NOT NULL,
    room_type VARCHAR(50) NOT NULL,
	
	CONSTRAINT id_user_id UNIQUE (id, user_id),
	CONSTRAINT user_id_room_number UNIQUE (user_id, room_number),

	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    room_type VARCHAR(50) NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	CONSTRAINT user_id_name UNIQUE (user_id, name),

	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS teacher_constraints (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL,
	timeslot_id INTEGER NOT NULL,
	teacher_id INTEGER NOT NULL,
	constraint_type VARCHAR(50) NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	CONSTRAINT user_id_timeslot_id_teacher_id UNIQUE (user_id, timeslot_id, teacher_id),

	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),

	CONSTRAINT fk_timeslot FOREIGN KEY (timeslot_id, user_id) REFERENCES timeslots(id, user_id),
	CONSTRAINT fk_teacher FOREIGN KEY (teacher_id, user_id) REFERENCES teachers(id, user_id)
);

CREATE TABLE IF NOT EXISTS teacher_subjects (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL,
	teacher_id INTEGER NOT NULL,
	subject_id INTEGER NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	CONSTRAINT user_id_teacher_id_subject_id UNIQUE (user_id, teacher_id, subject_id),

	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),

	CONSTRAINT fk_teacher FOREIGN KEY (teacher_id, user_id) REFERENCES teachers(id, user_id),
	CONSTRAINT fk_subject FOREIGN KEY (subject_id, user_id) REFERENCES subjects(id, user_id)
);

CREATE TABLE IF NOT EXISTS timeslots (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL,
	day_of_week VARCHAR(20) NOT NULL,
	lesson_number INTEGER NOT NULL,
	start_time TIME NOT NULL,
	end_time TIME NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	
	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS teachers (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	phone VARCHAR(20), -- телефон указывать необязательно
	max_lessons_per_day INTEGER NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	
	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS groups (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	course INTEGER NOT NULL,
	speciality VARCHAR(100) NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	CONSTRAINT user_id_name_course UNIQUE (user_id, name, course),

	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS group_subject_limits (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL,
	group_id INTEGER NOT NULL,
	subject_id INTEGER NOT NULL,
	max_lessons_per_week INTEGER NOT NULL,

	CONSTRAINT id_user_id UNIQUE (id, user_id),
	CONSTRAINT user_id_group_id_subject_id UNIQUE (user_id, group_id, subject_id),

	CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),

	CONSTRAINT fk_group FOREIGN KEY (group_id, user_id) REFERENCES groups(id, user_id),
	CONSTRAINT fk_subject FOREIGN KEY (subject_id, user_id) REFERENCES subjects(id, user_id)
);

CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    classroom_id INTEGER NOT NULL,
    timeslot_id INTEGER NOT NULL,

    -- Защита от дублей внутри расписания
    CONSTRAINT no_groups UNIQUE (group_id, timeslot_id),
    CONSTRAINT no_teacher UNIQUE (teacher_id, timeslot_id),
    CONSTRAINT no_classroom UNIQUE (classroom_id, timeslot_id),

    --подключения FK
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),

    -- ЗАЩИТА ОТ ИСПОЛЬЗОВАНИЯ ЧУЖИХ РЕСУРСОВ (Критично!)
	-- Составные FK: гарантируют, что сущность принадлежит этому user_id
    CONSTRAINT fk_group FOREIGN KEY (group_id, user_id) REFERENCES groups(id, user_id),
	CONSTRAINT fk_subject FOREIGN KEY (subject_id, user_id) REFERENCES subjects(id, user_id),
    CONSTRAINT fk_teacher FOREIGN KEY (teacher_id, user_id) REFERENCES teachers(id, user_id),
    CONSTRAINT fk_classroom  FOREIGN KEY (classroom_id, user_id) REFERENCES classrooms(id, user_id),
    CONSTRAINT fk_timeslot FOREIGN KEY (timeslot_id, user_id) REFERENCES timeslots(id, user_id)
);