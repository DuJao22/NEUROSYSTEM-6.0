# Sistema de Controle de Pacientes Neuropsicológicos

## Overview

This is a comprehensive web-based patient management system specifically designed for neuropsychology practices. The system manages the complete patient journey from simplified registration (name, CPF, carteirinha, WhatsApp, location) through session scheduling and service type registration. The system separates session creation from service type registration for cleaner workflow, with doctors only registering service types (neuropsychological test or consultation) without seeing monetary values.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes and Bug Fixes (August 12, 2025)

### Critical Bug Fixes Applied
- **JSON Serialization Error Fixed**: Resolved "Object of type Row is not JSON serializable" error by implementing proper Row-to-dictionary conversion throughout the application
- **Template Syntax Error Fixed**: Corrected missing `{% endblock %}` tag in `admin_dashboard.html` that was causing Jinja2 template compilation failures
- **Database Column Reference Error Fixed**: Eliminated references to non-existent `e.porcentagem` column (should be `e.porcentagem_participacao`)
- **Template Variable Error Fixed**: Added proper default values for template variables to prevent 'dict object has no attribute' errors in error handling scenarios
- **Password Status Display Fixed**: Corrected template references from `senha.aprovada` to `senha.aprovada_admin` across all patient and admin templates to properly display approval status
- **Authentication System Restored**: Reset medical staff passwords to 'admin123' and verified patient login system with CPF-based authentication

### Code Quality Improvements
- **New Utility Module**: Created `sql_utils.py` with helper functions for safe SQL Row object conversion and data type handling
- **Systematic Row Object Conversion**: Updated all route handlers in `admin.py`, `medico.py`, `equipe.py`, and `relatorios.py` to properly convert SQLite Row objects to JSON-serializable dictionaries
- **Enhanced Error Handling**: Improved error handling throughout route handlers with proper fallback values and default objects
- **Template Safety**: All templates now receive properly serialized data that can be safely converted to JSON for JavaScript operations

### System Stability Enhancements
- **Eliminated Cached Error Sources**: Removed Python bytecode cache to prevent old column reference errors
- **Comprehensive Template Validation**: Verified all critical templates (admin, medico, equipe, relatorios dashboards) have proper syntax
- **Database Initialization Logging**: Added better logging for database initialization process
- **Application Startup Reliability**: Application now starts consistently without template or serialization errors

## System Architecture

### Backend Framework
- **Flask Application**: Monolithic web application using Flask as the primary framework with Blueprint-based modular routing
- **SQLite3 Database**: Local SQLite3 database for data persistence using raw SQL queries without ORM
- **Session-based Authentication**: Server-side session management with role-based access control (admin, medico, admin_equipe, paciente)
- **File Upload System**: Secure PDF document upload with sanitization and local filesystem storage
- **Appointment Scheduling System**: Complete appointment management with automatic confirmation availability (1 day before) and patient confirmation workflow

### Database Design
- **Core Tables**: medicos (doctors), pacientes (patients), sessoes (sessions), senhas (insurance codes), laudos (reports), equipes (teams), faturamento (billing)
- **Appointment Tables**: agendamentos (appointments), confirmacoes_consulta (appointment confirmations)
- **Raw SQL Queries**: Direct sqlite3 module usage for all database operations (no ORM)
- **Unique Constraints**: CPF field enforces unique patient registration to prevent duplicates
- **Foreign Key Relationships**: Relational structure linking patients to doctors, sessions to patients, teams to doctors, appointments to confirmations

### Authentication & Authorization
- **Multi-tier Access Control**: Four user types with distinct permissions and dashboard views
- **Patient Portal**: CPF-based login system allowing patients to access their documents and session history
- **Werkzeug Password Hashing**: Secure password storage for medical staff
- **Session Management**: Flask sessions for maintaining user state across requests

### Frontend Architecture
- **Jinja2 Template Engine**: Server-side rendering with template inheritance and modular components
- **Bootstrap 5 Framework**: Responsive dark-themed UI with custom CSS enhancements
- **Chart.js Integration**: Dashboard visualizations for financial analytics and statistics
- **Modal-based Forms**: Dynamic form interactions for data entry and management

### Financial Management System - NEUROPSYCHOLOGY CLINIC MODEL
- **Insurance Password Revenue**: Clinic receives payment from insurance based on patient's "senha" (authorization code), each with specific value
- **Team Percentage System**: Medical teams receive percentage of insurance revenue, team pays their own doctors internally
- **External Doctor Payment**: Independent doctors (not in teams) receive per-session payment, guaranteed 8 sessions even if patient completes early
- **Revenue Separation**: Team doctors and external doctors have separate payment calculations to avoid mixing revenue streams
- **Session Completion Rules**: If patient finishes before 8 sessions, external doctors still receive payment for remaining sessions

### Data Management
- **Simplified Patient Registration**: Only essential fields (name, CPF, carteirinha, WhatsApp, location)
- **Separated Session Management**: Session creation (date, observations) separate from service type registration
- **Service Type Registration**: Doctors register service types without seeing values - automatic assignment (R$800 for neuropsychological test, R$80 for consultation)
- **Two-Password Approval System**: Laudo delivery requires approval of both passwords: Teste Neuropsicológico (R$800) and Consulta/Sessão (R$80)
- **Admin Approval Workflow**: All service types require admin approval before billing and laudo delivery
- **Document Security**: Patients can only access their own documents with proper validation
- **Location Tracking**: Service location management (Belo Horizonte, Contagem, Divinópolis)
- **Automatic Laudo Liberation**: System automatically liberates laudo delivery when both required passwords are approved

### Appointment Scheduling System
- **Doctor Scheduling**: Doctors can schedule next appointments with date/time and observations
- **Automatic Confirmation Trigger**: System automatically enables patient confirmation 1 day before appointment
- **Patient Confirmation Interface**: Patients can confirm attendance or cancel with optional reason
- **Multi-tier Notifications**: System tracks confirmations for doctors, team admins, and general admin
- **Admin Overview Dashboard**: Complete view of all appointment confirmations with statistics and filtering
- **Real-time Updates**: Appointment confirmations are processed immediately with status tracking
- **Historical Tracking**: Full history of confirmed and cancelled appointments with timestamps

## External Dependencies

### Cloud Services
- **SQLiteCloud**: Cloud-hosted SQLite database service for data persistence and scalability

### CDN Libraries
- **Bootstrap 5**: CSS framework loaded from CDN for responsive UI components
- **Font Awesome 6**: Icon library for consistent iconography throughout the application
- **Chart.js**: JavaScript charting library for dashboard analytics and visualizations

### Python Libraries
- **Flask**: Core web framework for application structure and routing
- **Werkzeug**: Security utilities for password hashing and file upload handling
- **sqlite3**: Database connectivity (Python standard library)

### File Storage
- **Local Filesystem**: Document storage in `/uploads` directory for patient reports and files
- **PDF Processing**: File validation and secure handling for patient documents