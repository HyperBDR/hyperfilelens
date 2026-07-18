# Shared reverse-proxy headers for Django/Gunicorn (api:8000) and Daphne (api:8001).
# Include inside a location { } block after proxy_pass.

proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Port $server_port;
proxy_set_header X-HFL-Site-Role $hfl_site;
proxy_set_header X-Request-Id $http_x_request_id;
proxy_set_header X-Org-Key $http_x_org_key;
