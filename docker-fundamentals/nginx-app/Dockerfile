# Official Nginx image on Alpine Linux (small footprint)
FROM nginx:alpine

# Replace the default server block with our own (adds a custom header and
# a /health endpoint, distinguishing this from the Apache-app config)
COPY default.conf /etc/nginx/conf.d/default.conf

# Replace the default welcome page with our own Hello World page
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

# Base image already defines this CMD; stated explicitly for clarity
CMD ["nginx", "-g", "daemon off;"]
