echo "Stopping PostgreSQL..."
pg_ctl -D $PGDATA stop -m fast
