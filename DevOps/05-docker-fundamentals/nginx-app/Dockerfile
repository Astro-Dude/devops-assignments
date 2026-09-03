# Official Nginx image, alpine variant for a small footprint
FROM nginx:alpine

# Replace the default site configuration
COPY default.conf /etc/nginx/conf.d/default.conf

# Copy the static site into the directory nginx serves
COPY html/ /usr/share/nginx/html/

EXPOSE 80

# The base image already runs nginx in the foreground.
