echo "Starting PostgreSQL..."
pg_ctl -D $PGDATA -o '-k $PGSOCKET' -l $PGDATA/logfile start -w
