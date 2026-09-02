// Java + Maven deployment demo (Task 3: Docker Application Deployment).
// Exposes a small JSON API (/api/info) using org.json, and an HTML page (/),
// and reports the JRE runtime version.
package com.example;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import org.json.JSONObject;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Instant;

public class App {

    public static void main(String[] args) throws IOException {
        int port = 8080;
        String portEnv = System.getenv("PORT");
        if (portEnv != null && !portEnv.isEmpty()) {
            port = Integer.parseInt(portEnv);
        }

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/api/info", new InfoHandler());
        server.createContext("/", new IndexHandler());
        server.setExecutor(null);
        server.start();
        System.out.println("ms-deploy-java listening on port " + port
                + " (JRE " + System.getProperty("java.version") + ")");
    }

    private static String hostname() {
        try {
            return InetAddress.getLocalHost().getHostName();
        } catch (Exception e) {
            return "unknown";
        }
    }

    static class InfoHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            JSONObject json = new JSONObject();
            json.put("app", "ms-deploy-java");
            json.put("language", "Java");
            json.put("runtime", "JRE " + System.getProperty("java.version"));
            json.put("framework", "org.json 20240303");
            json.put("hostname", hostname());
            json.put("platform", System.getProperty("os.name") + " " + System.getProperty("os.arch"));
            json.put("timestamp", Instant.now().toString());

            byte[] bytes = json.toString(2).getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        }
    }

    static class IndexHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            String javaVersion = System.getProperty("java.version");
            String html = "<!DOCTYPE html>\n" +
                    "<html lang=\"en\">\n" +
                    "<head><meta charset=\"UTF-8\"><title>Java Deployment Demo</title>\n" +
                    "<style>body{font-family:sans-serif;background:#1b1b2f;color:#eaeaea;" +
                    "text-align:center;padding-top:70px;}h1{font-size:2.6em;color:#e94560;}" +
                    "p{color:#9a9ab0;}code{background:#162447;padding:2px 8px;border-radius:4px;}</style></head>\n" +
                    "<body>\n" +
                    "<h1>Java Deployment Demo</h1>\n" +
                    "<p>Runtime: <strong>JRE " + javaVersion + "</strong> &middot; Built with <strong>Maven</strong>, packaged as a shaded jar</p>\n" +
                    "<p>JSON API: <code>GET /api/info</code></p>\n" +
                    "<p>Hostname: " + hostname() + "</p>\n" +
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
