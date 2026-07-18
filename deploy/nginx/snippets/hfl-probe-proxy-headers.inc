# Minimal reverse-proxy headers for internal health and metrics probes.
proxy_set_header Host $http_host;
proxy_set_header X-HFL-Site-Role $hfl_site;
