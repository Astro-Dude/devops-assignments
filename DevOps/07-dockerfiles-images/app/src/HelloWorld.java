import com.sun.net.httpserver.HttpServer;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/**
 * Multi-stage build demo application.
 *
 * Stage 1 of the Dockerfile compiles this file with the full JDK.
 * Stage 2 copies only the resulting .class files onto a slim JRE image.
 */
public class HelloWorld {

    public static void main(String[] args) throws Exception {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));

        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);

        server.createContext("/", exchange -> {
            String hostname = InetAddress.getLocalHost().getHostName();
            String body = """
                <!doctype html>
                <html>
                  <head><title>Docker Multi-Stage Build</title></head>
                  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#f6f8fa;">
                    <h1>Hello World from Docker multi-stage build</h1>
                    <p>Java runtime: <strong>%s</strong></p>
                    <p>Container hostname: <code>%s</code></p>
                    <p>Listening on port <strong>%d</strong></p>
                  </body>
                </html>
                """.formatted(System.getProperty("java.version"), hostname, port);

            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });

        server.setExecutor(null);
        System.out.println("Multi-stage demo listening on port " + port);
        server.start();
    }
}
