# INF01127
Engenharia de Software N


# Instalação:
	sudo apt install git
	sudo apt install curl
	
	sh <(curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install) --no-daemon
	
	sudo apt install direnv

	echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
	
	echo 'source $HOME/.nix-profile/etc/profile.d/nix.sh' >> ~/.bashrc && source ~/.bashrc

	mkdir -p ~/.config/nix && echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf	

	git clone https://github.com/Oxy8/INF01127.git

	cd INF01127

	direnv allow
	
	echo "unix_socket_directories = './pgsocket'" >> "$PGDATA/postgresql.conf"
	
	postgres -D $PGDATA -k $PGSOCKET &
	
	createuser -s postgres -h $PGSOCKET
	
	psql -h $PGSOCKET -U postgres -c "CREATE DATABASE test_db;"

	psql -h $PGSOCKET -U postgres -d test_db -c "GRANT ALL PRIVILEGES ON DATABASE test_db TO \"$(whoami)\";"
	
	pg_ctl stop -D $PGDATA

	cd workspace/INF01127/src/

	./run.sh






