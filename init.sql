-- Script de inicialización de MySQL
-- Se ejecuta automáticamente al crear el contenedor

CREATE DATABASE IF NOT EXISTS songqueue
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE songqueue;
