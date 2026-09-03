# =====================================================================
#  MULTI-STAGE DOCKERFILE
#
#  Stage 1 ("builder") uses the full JDK to compile the source.
#  Stage 2 uses only the much smaller JRE and copies the compiled
#  classes across. The compiler, the build tools and the source code
#  never appear in the final image.
# =====================================================================

# ---------------------- Stage 1: BUILD ----------------------
FROM eclipse-temurin:21-jdk AS builder

WORKDIR /build

# Copy the source in and compile it
COPY src/HelloWorld.java ./
RUN javac -d /build/classes HelloWorld.java

# ---------------------- Stage 2: RUNTIME --------------------
FROM eclipse-temurin:21-jre

WORKDIR /app

# Copy ONLY the compiled output from the builder stage.
# Nothing else from stage 1 is carried over.
COPY --from=builder /build/classes ./

# The application listens on 8080
EXPOSE 8080

CMD ["java", "HelloWorld"]
