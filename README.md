# Car Maintenance System

A Django-based web application for managing a car maintenance garage/workshop.  
The system helps track clients, cars, workers, and maintenance visits in an organized way.

## Overview

Car Maintenance System is designed for garages that need a simple internal tool to store customer information, vehicle details, and maintenance history. Users can search for cars using the VIN, plate number, client phone number, or client name.

The interface is built in Arabic with RTL support and uses Bootstrap for styling.

## Features

- Add and manage clients
- Add and manage cars for each client
- Search cars by:
  - VIN
  - Plate number
  - Client phone number
  - Client name
- View detailed car information
- Track maintenance visit history
- Add service/repair visits for each car
- Record:
  - KM at visit
  - Assigned worker/technician
  - Work description
  - Parts used
  - Cost
  - Notes
- Manage garage workers/technicians
- Prevent deleting the default worker
- Automatically update the car’s current KM when a new visit has a higher KM value
- Arabic RTL user interface
- Responsive layout using Bootstrap

## Tech Stack

- Python
- Django
- SQLite
- HTML
- CSS
- Bootstrap 5

## Project Structure

```text
Car_Maintenance/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── garage/
│   ├── migrations/
│   ├── templates/
│   │   └── garage/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── manage.py
├── requirements.txt
└── README.md
