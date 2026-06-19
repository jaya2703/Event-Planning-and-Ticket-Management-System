#!/bin/bash
# ============================================================
# EventPro - One-Click Setup Script
# Run this once to set up the entire project
# Usage: bash setup.sh
# ============================================================

echo ""
echo "=================================================="
echo "   EventPro - Setup Script"
echo "=================================================="
echo ""

# Step 1: Install Python dependencies
echo "📦 Installing Python packages..."
pip install django pillow qrcode reportlab --break-system-packages -q
echo "   ✅ Packages installed"

# Step 2: Run database migrations
echo ""
echo "🗄️  Setting up database..."
python manage.py makemigrations accounts
python manage.py makemigrations events
python manage.py makemigrations bookings
python manage.py makemigrations payments
python manage.py makemigrations volunteers
python manage.py makemigrations notifications
python manage.py migrate
echo "   ✅ Database ready"

# Step 3: Create sample data
echo ""
echo "🌱 Creating sample data..."
python create_sample_data.py

# Step 4: Collect static files
echo ""
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput -v 0
echo "   ✅ Static files ready"

echo ""
echo "=================================================="
echo "   ✅ Setup Complete!"
echo "=================================================="
echo ""
echo "   Start the server:  python manage.py runserver"
echo "   Open browser:      http://127.0.0.1:8000"
echo ""
echo "   Login Credentials:"
echo "   Admin:      admin / admin123"
echo "   Organizer:  organizer1 / org123"
echo "   User:       user1 / user123"
echo "   Volunteer:  volunteer1 / vol123"
echo ""
