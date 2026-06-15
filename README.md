# Splitwise App 💰

A Django-based expense splitting application for managing shared expenses in groups (flatmates, friend groups, roommates, etc.) with intelligent CSV import, anomaly detection, and settlement tracking.

## Features

✨ **Group Management**
- Create and manage expense groups
- Track member join/leave dates
- Automatic membership validation

💰 **Expense Tracking**
- Add expenses with flexible split types (equal, unequal, percentage, share-based)
- Multi-currency support (USD to INR conversion)
- Refund handling (negative amounts)
- Transaction history and settlement calculation

📋 **Smart CSV Import**
- Intelligent anomaly detection (duplicates, date format issues, currency problems, etc.)
- Manual review workflow for flagged transactions
- Settlement detection (automatically distinguishes settlements from expenses)
- Membership date validation

📊 **Balance Calculation**
- Individual and group balance tracking
- Settlement suggestions
- Detailed balance breakdowns

🔐 **User Management**
- Account creation and authentication
- Role-based access to groups
- Secure password management

## Setup Instructions

### Prerequisites
- Python 3.8+
- Django 3.2+
- SQLite3

### Installation

1. **Clone/Download the Project**
   ```bash
   cd splitwise_app
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install django
   ```

4. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create Superuser (Admin)**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

7. **Access the App**
   - Web: http://127.0.0.1:8000
   - Admin: http://127.0.0.1:8000/admin

### Directory Structure

```
splitwise_app/
├── manage.py              # Django management script
├── db.sqlite3            # SQLite database
├── config/               # Django project configuration
│   ├── settings.py       # Settings & configuration
│   ├── urls.py          # URL routing
│   ├── wsgi.py          # WSGI configuration
│   └── asgi.py          # ASGI configuration
├── accounts/            # User authentication app
│   ├── models.py        # User models (extends Django User)
│   ├── views.py         # Login/signup views
│   ├── forms.py         # User forms
│   ├── urls.py          # Auth URLs
│   └── templates/       # Login/signup templates
├── expenses/            # Main expense tracking app
│   ├── models.py        # Expense, Group, Settlement models
│   ├── importer.py      # CSV import logic with anomaly detection
│   ├── balances.py      # Balance calculation engine
│   ├── views.py         # All view handlers
│   ├── forms.py         # Expense & group forms
│   ├── urls.py          # Expense URLs
│   ├── admin.py         # Django admin configuration
│   └── templates/       # HTML templates
├── templates/           # Base templates
├── static/             # Static files (CSS, JS, images)
├── data/               # CSV import data location
└── README.md           # This file
```

## Usage

### Creating a Group

1. Log in to your account
2. Click "New Group"
3. Enter group name
4. Add members through the group members page

### Adding Expenses

1. Navigate to a group
2. Click "Add Expense"
3. Fill in:
   - Description
   - Date
   - Amount & Currency
   - Paid by (who paid)
   - Split type (how to divide)
   - Members to split with
   - Optional notes
4. Save

### Recording Payments/Settlements

1. In a group, click "Record Payment"
2. Enter:
   - Who paid
   - Who received
   - Amount
   - Date
   - Optional notes
3. Save

### Importing CSV

1. Prepare CSV file with columns: `date`, `description`, `paid_by`, `amount`, `currency`, `split_type`, `split_with`, `split_details`, `notes`
2. In a group, click "Import CSV"
3. Upload the file
4. Review the import report
5. Approve or reject flagged transactions

## CSV Import Format

### Expected Columns

| Column | Type | Example | Required | Notes |
|--------|------|---------|----------|-------|
| date | String | 2026-06-15 or 15/06/2026 | ✓ | ISO or DD/MM/YYYY format |
| description | String | Grocery shopping | ✓ | Transaction description |
| paid_by | String | priya | ✓ | Username or alias |
| amount | Decimal | 500.50 | ✓ | Can include commas (1,000.50) |
| currency | String | INR, USD | ✗ | Default: INR |
| split_type | String | equal, unequal, percentage, share | ✗ | Default: equal |
| split_with | String | rohan; aisha; dev | ✓ | Semicolon-separated names |
| split_details | String | rohan 500; aisha 300 | ✗ | Format depends on split_type |
| notes | String | Costco trip | ✗ | Optional notes |

### Split Type Examples

**Equal Split:**
```
date,description,paid_by,amount,currency,split_with,split_type
2026-06-15,Dinner,priya,1200,INR,"rohan; aisha; dev",equal
```

**Unequal Split (amounts):**
```
split_details: rohan 500; aisha 400; dev 300
```

**Percentage Split:**
```
split_details: rohan 50; aisha 30; dev 20
```

**Share-based Split:**
```
split_details: rohan 2; aisha 1; dev 1
```

**Settlement (one recipient):**
```
date,description,paid_by,amount,currency,split_with
2026-06-15,Payment,rohan,1000,INR,aisha
```

## Database Schema

See [SCOPE.md](SCOPE.md) for detailed database schema and anomaly handling.

## Configuration

### Settings (`config/settings.py`)

Key settings you might want to adjust:

```python
# Time Zone
TIME_ZONE = 'Asia/Kolkata'  # Change as needed

# USD to INR Conversion Rate
USD_TO_INR_RATE = 87.00  # Update this as rates change

# Debug Mode (set to False for production)
DEBUG = True
```

## AI Tools Used

This project was developed with assistance from **GitHub Copilot** (Claude Haiku 4.5). 

For detailed information about AI usage, including prompts, issues encountered, and how they were resolved, see [AI_USAGE.md](AI_USAGE.md).

## Decision Log

For significant architectural and feature decisions made during development, see [DECISIONS.md](DECISIONS.md).

## Troubleshooting

### Migrations Not Applied

```bash
python manage.py makemigrations
python manage.py migrate
```

### Database Locked Error

Remove `db.sqlite3` and rerun migrations (note: this clears all data):

```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Import Not Working

1. Check CSV format matches the template
2. Verify column names are exact
3. Check date format is recognized (ISO or DD/MM/YYYY)
4. Review the import report for specific error messages

## API Endpoints

All endpoints require authentication. Main URL patterns:

- `/admin/` - Django admin panel
- `/accounts/login/` - Login
- `/accounts/signup/` - Sign up
- `/expenses/dashboard/` - Main dashboard
- `/expenses/groups/` - All groups
- `/expenses/group/<id>/` - Group detail
- `/expenses/group/<id>/expenses/add/` - Add expense
- `/expenses/group/<id>/settlement/add/` - Record payment
- `/expenses/group/<id>/import/` - Import CSV
- `/accounts/logout/` - Logout

## File Structure Details

See [SCOPE.md](SCOPE.md) for:
- Complete database schema with all fields
- Anomaly detection log with 40+ types of issues
- How each anomaly is handled
- Data validation rules

## Contributing

Suggestions for improvements:
1. Add expense categories
2. Recurring expense templates
3. Export to PDF/Excel
4. Mobile app
5. Real-time balance charts
6. Notification system

## License

This project is open source. Use, modify, and distribute as needed.

## Support

For issues with:
- **Database/Schema**: See SCOPE.md
- **Decision rationale**: See DECISIONS.md
- **AI-related issues**: See AI_USAGE.md

---

**Last Updated:** June 15, 2026  
**Version:** 1.0  
**Python:** 3.8+  
**Django:** 3.2+
