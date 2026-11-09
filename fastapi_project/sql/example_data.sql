-- Выполнить в Query Tool базы telecom ПОСЛЕ первого запуска приложения.
-- Учебные данные. Повторный запуск не меняет существующих клиентов.
BEGIN;
INSERT INTO tarif (tarif_name, internet, count_minutes, count_sms, salary)
SELECT 'Учебный', 50, 500, 100, 600
WHERE NOT EXISTS (SELECT 1 FROM tarif WHERE tarif_name = 'Учебный');

INSERT INTO client (number_phone, id_tarif, lastname, firstname, patronymic_name,
                    date_birthday, pasport_serial, pasport_number, date_issue)
VALUES
('+79001234567', (SELECT min(id_tarif) FROM tarif WHERE tarif_name='Учебный'),
 'Иванов', 'Иван', 'Иванович', '1995-10-20', '0012', '000123', '2016-01-01'),
('88001234567', (SELECT min(id_tarif) FROM tarif WHERE tarif_name='Учебный'),
 'Петров', 'Петр', 'Петрович', '1990-05-15', '0013', '000124', '2015-12-31')
ON CONFLICT (number_phone) DO NOTHING;
COMMIT;
