# stats-deploy

# Requirements
- Docker
- Docker Swarm (use command `docker swarm init`)
- Docker-compose
- Open port 80 and 443 externally
- Configure env variables (see below)

# Env variables
Each service has it's own env variables to function properly. Copy files from .envs-template to .envs (for prod) or .envs-dev (for dev) and edit them accordingly to your needs.

# Using git-crypt
Envs for production in .envs are encrypted with [git-crypt](https://www.agwa.name/projects/git-crypt/).

To decrypt files locally (where you have your gpg keys) use `git crypt unlock`.

To decrypt files on production server:
- locally
  ```sh
  git crypt unlock
  git crypt export-key key
  scp ./key stats.golem.network:
  ```
- on stats.golem.network, inside git repository
  ```sh
  git crypt unlock ~/key
  rm ~/key
  ```

# Deployment
To deploy the stats page, simply just use `docker stack deploy -c docker-compose-prod.yml golemstats`

# Local dev environment
Just run the setup_local_env.sh script, configure env variables and run `docker-compose -f docker-compose-dev.yml build && docker stack deploy -c docker-compose-dev.yml golemstats`

# Getting access to the database
If you'd like to get direct access to the database, then install [OpenVPN](https://github.com/angristan/openvpn-install) on the machine and make sure the port you configure is open so you can connect.
Then grab the machines local IPv4 address and edit the Traefik label for the pgadmin service ```- traefik.http.routers.pgadmin.rule=Host(`10.8.0.1`)``` and replace it with your machines local IPv4 address.
Now you should deploy the changes and if you're connected to the VPN, then you should be able to connect to the pgadmin service via `http://LocalIPv4Address:85`


# Configuring the domains the backend API and the frontend should be served on
Simply go edit the ```- traefik.http.routers.webserver.rule=Host(`api.stats.golem.network`, `api.golemstats.com`)``` label for the backend and ```- traefik.http.routers.frontend.rule=Host(`stats.golem.network`, `golemstats.com`)``` for the frontend. The domains specified will make traefik retrieve an SSL certificate for each specificed and automatically renew those.


