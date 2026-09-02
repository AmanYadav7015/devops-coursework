# Official Apache httpd image on Alpine Linux (small footprint)
FROM httpd:2.4-alpine

# Copy our custom homepage over the default Apache "It works!" page.
# httpd's default DocumentRoot is /usr/local/apache2/htdocs/
COPY index.html /usr/local/apache2/htdocs/index.html

# Apache listens on 80 by default inside the image
EXPOSE 80

# Base image already defines CMD ["httpd-foreground"]; stated explicitly for clarity
CMD ["httpd-foreground"]
