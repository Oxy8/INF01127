{
  description = "Python 3.11 com flask e postgreSQL";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  };

  outputs = { self, nixpkgs, ... }: 



      let
        system = "x86_64-linux";
        pkgs = import nixpkgs {
          inherit system;
          config = { allowUnfree = true; };
        };

		
		
        extensions = with pkgs.vscode-extensions; [
          pkief.material-icon-theme
          ms-python.python
          ms-python.pylint
        ];

    
        vscode-with-extensions =
          pkgs.vscode-with-extensions.override { vscodeExtensions = extensions; };

        postgresqlWithExtensions = pkgs.postgresql_17.withPackages (p: [
            p.postgis
            p.pg_repack
          ]);
        
      in

      {
		  
        devShell.x86_64-linux = pkgs.mkShell {
          packages = [
            pkgs.bashInteractive # needed for vscode integrated terminal to work properly
            pkgs.vscode-with-extensions
            pkgs.python312
			pkgs.python312Packages.flask
			pkgs.python312Packages.psycopg2
			pkgs.python312Packages.sqlalchemy
			pkgs.python312Packages.flask-sqlalchemy
			pkgs.python312Packages.flask-login
			pkgs.python312Packages.werkzeug
			pkgs.python312Packages.googlemaps
			pkgs.python312Packages.geoalchemy2
			# pkgs.postgresql_17
			# pkgs.postgresql_17.dev
			postgresqlWithExtensions
          ];

        shellHook = ''
				export PG_START=$PWD/pg_start.sh
				export PG_STOP=$PWD/pg_stop.sh

                export PGDATA=$PWD/pgdata
                export PGSOCKET=$PWD/pgsocket
                export PGSOCKET_URI="postgresql:///test_db?sslmode=require&host=$PGSOCKET"

                mkdir -p "$PGSOCKET"
              
                if [ ! -d "$PGDATA" ]; then
                  echo "Initializing PostgreSQL data directory..."
                  initdb -D $PGDATA
                fi              
                
              '';
        };
      };
}
