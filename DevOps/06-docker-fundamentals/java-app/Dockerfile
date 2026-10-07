# ---- Stage 1: compile the Java source with the full JDK ----
FROM eclipse-temurin:21-jdk AS builder

WORKDIR /build
COPY src/HelloWorld.java ./
RUN javac -d /build/classes HelloWorld.java

# ---- Stage 2: run it on the much smaller JRE ----
FROM eclipse-temurin:21-jre

WORKDIR /app
# Only the compiled .class files are carried over - the JDK and source stay behind
COPY --from=builder /build/classes ./

EXPOSE 8080

CMD ["java", "HelloWorld"]
