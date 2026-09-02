// Plain Java, JDK standard library only (com.sun.net.httpserver.HttpServer).
// No Maven, no Gradle, no external dependencies - compiled directly with javac.
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

public class HelloWorld {

    public static void main(String[] args) throws IOException {
        int port = 8080;
        String portEnv = System.getenv("PORT");
        if (portEnv != null && !portEnv.isEmpty()) {
            port = Integer.parseInt(portEnv);
        }

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/", new HelloHandler());
        server.setExecutor(null);
        server.start();
        System.out.println("Java Hello World server listening on port " + port);
    }

    static class HelloHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            String host;
            try {
                host = InetAddress.getLocalHost().getHostName();
            } catch (Exception e) {
                host = "unknown";
            }

            String html = "<!DOCTYPE html>\n" +
                    "<html lang=\"en\">\n" +
                    "<head><meta charset=\"UTF-8\"><title>Java Hello World</title>\n" +
                    "<style>body{font-family:sans-serif;background:#1b1b2f;color:#eaeaea;" +
                    "text-align:center;padding-top:80px;}h1{font-size:3em;color:#e94560;}" +
                    "p{color:#9a9ab0;}</style></head>\n" +
                    "<body>\n" +
                    "<h1>Hello World</h1>\n" +
                    "<p>Served by plain <strong>Java</strong> (com.sun.net.httpserver.HttpServer)" +
                    " compiled with javac, running on a JRE (eclipse-temurin:21-jre-alpine)</p>\n" +
                    "<p>Hostname: " + host + "</p>\n" +
                    "</body>\n" +
                    "</html>";

            byte[] bytes = html.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        }
    }
}
