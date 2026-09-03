# Official Apache HTTP Server image
FROM httpd:2.4

# httpd serves everything in this directory by default
COPY public-html/ /usr/local/apache2/htdocs/

# Apache listens on 80 inside the container
EXPOSE 80

# The base image already sets:
#   CMD ["httpd-foreground"]
# so no CMD is needed here.
