#!/bin/bash
# Fix PostgreSQL authentication for host connections
# This script configures pg_hba.conf to use MD5 authentication
# Run this after: make up

set -e

echo "🔧 Fixing PostgreSQL authentication..."

# Check if container is running
if ! docker ps | grep -q doktalk-postgres; then
    echo "❌ Error: doktalk-postgres container is not running"
    echo "   Run 'make up' first"
    exit 1
fi

# Update pg_hba.conf to use MD5 auth
docker exec doktalk-postgres bash -c "
cat > /var/lib/postgresql/data/pg_hba.conf << 'EOF'
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections
local   all             all                                     trust

# IPv4 local connections
host    all             all             127.0.0.1/32            trust

# IPv6 local connections
host    all             all             ::1/128                 trust

# Allow connections from Docker network (MD5)
host    all             all             0.0.0.0/0               md5

# Replication
local   replication     all                                     trust
host    replication     all             127.0.0.1/32            trust
host    replication     all             ::1/128                 trust
EOF
"

# Reset user password
docker exec doktalk-postgres psql -U doktalk_user -d doktalk -c \
    "ALTER USER doktalk_user WITH PASSWORD 'password';" > /dev/null

# Reload PostgreSQL configuration
docker exec doktalk-postgres psql -U doktalk_user -d doktalk -c \
    "SELECT pg_reload_conf();" > /dev/null

echo "✅ PostgreSQL authentication fixed"
echo "   You can now connect from the host machine"
echo ""
echo "Test connection:"
echo "  poetry run python -c 'import asyncio; from sqlalchemy.ext.asyncio import create_async_engine; from sqlalchemy import text; asyncio.run((lambda: create_async_engine(\"postgresql+asyncpg://doktalk_user:password@localhost:5432/doktalk\").connect()).__call__())'"
