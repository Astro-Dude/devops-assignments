# Small official Node image - alpine keeps the final image tiny
FROM node:20-alpine

# All app files live here inside the container
WORKDIR /app

# Copy package.json first so Docker can cache the dependency layer
COPY package.json ./

# No third-party dependencies in this app, but this is where they would install
RUN npm install --omit=dev

# Now copy the application source
COPY app.js ./

# Document which port the app listens on
EXPOSE 3000

# Start the server
CMD ["node", "app.js"]
