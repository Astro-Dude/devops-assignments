import com.sun.net.httpserver.HttpServer;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/** Minimal Java HTTP server using the JDK's built-in HttpServer - no frameworks. */
public class HelloWorld {

    public static void main(String[] args) throws Exception {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));

        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);

        server.createContext("/", exchange -> {
            String hostname = InetAddress.getLocalHost().getHostName();
            String body = """
                <!doctype html>
                <html>
                  <head><title>Java on Docker</title></head>
                  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:80px; background:#f6f8fa;">
                    <h1>Hello World</h1>
                    <p>Served by <strong>Java %s</strong> inside Docker</p>
                    <p>Hostname (container ID): <code>%s</code></p>
                  </body>
                </html>
                """.formatted(System.getProperty("java.version"), hostname);

            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });

        server.setExecutor(null);
        System.out.println("Java server listening on port " + port);
        server.start();
    }
}
