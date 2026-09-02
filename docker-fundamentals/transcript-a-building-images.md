# Docker — building the six images

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
# --- host: macOS, Docker Desktop, working from docker-fundamentals/ ---
aman@macbook docker-fundamentals % pwd
/Users/aman/Desktop/devops/docker-fundamentals
```

### 1) nodejs-app - plain Node.js HTTP server

```console
aman@macbook nodejs-app % docker build -t df-nodejs:1.0 .
#2 [internal] load metadata for docker.io/library/node:22-alpine
#2 DONE 0.0s

#3 [internal] load .dockerignore
#3 transferring context: 2B done
#3 DONE 0.0s

#4 [internal] load build context
#4 transferring context: 907B done
#4 DONE 0.0s

#5 [1/3] FROM docker.io/library/node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32
#5 resolve docker.io/library/node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 0.0s done
#5 DONE 0.0s

#6 [2/3] WORKDIR /app
#6 DONE 0.0s

#7 [3/3] COPY server.js .
#7 DONE 0.0s

#8 exporting to image
#8 exporting layers 0.0s done
#8 exporting manifest sha256:6654fe49defa3a5413d71b0eba1949397c375247eecc2f65011eac47be2db0a5 done
#8 exporting config sha256:92fc137aff29c62e7cdbce95ff05815ed882070fe5d2fbd6c4efb81a20b02065 done
#8 exporting attestation manifest sha256:37f2a1990da26e58213c9702655db81396c17ac04dadfa964a45671551867d30 done
#8 exporting manifest list sha256:020b6db88d99a9c42222fb23632c3ad615c2276cdc8b1e58d0ed5ac189f9c755 done
#8 naming to docker.io/library/df-nodejs:1.0 done
#8 unpacking to docker.io/library/df-nodejs:1.0 0.0s done
#8 DONE 0.1s
```

### 2) python-app - plain Python http.server (stdlib only)

```console
aman@macbook python-app % docker build -t df-python:1.0 .
#2 [internal] load metadata for docker.io/library/python:3.12-alpine
#2 DONE 1.9s

#3 [internal] load .dockerignore
#3 transferring context: 2B done
#3 DONE 0.0s

#4 [internal] load build context
#4 transferring context: 1.42kB done
#4 DONE 0.0s

#5 [1/3] FROM docker.io/library/python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a
#5 resolve docker.io/library/python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a done
#5 CACHED

#6 [2/3] WORKDIR /app
#6 DONE 0.0s

#7 [3/3] COPY app.py .
#7 DONE 0.0s

#8 exporting to image
#8 exporting layers 0.0s done
#8 exporting manifest sha256:9063b8d65f0641eae51e1ba9e21580382d3f2ed21150bd2d9f095798b847ed63 done
#8 exporting config sha256:d9797cf4dfb69864807b51df6d6a3ac5c3416049ca81313937bbdbbd1e192e78 done
#8 exporting attestation manifest sha256:a0fafb19fe5f4b1950d48cb981ae619e0e6c2949689edeb8ee3ea0784c418fcd done
#8 exporting manifest list sha256:f1e8b23353d39530c987257ad1bafab601d5ac75f1d474f555002334394770dd done
#8 naming to docker.io/library/df-python:1.0 done
#8 unpacking to docker.io/library/df-python:1.0 0.0s done
#8 DONE 0.1s
```

### 3) java-app - multi-stage build: JDK compiles plain Java HttpServer, JRE runs it

```console
aman@macbook java-app % docker build -t df-java:1.0 .
#7 sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4 130.02MB / 156.33MB 32.6s
#7 sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4 138.41MB / 156.33MB 33.6s
#7 sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4 146.80MB / 156.33MB 34.7s
#7 sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4 155.19MB / 156.33MB 35.6s
#7 sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4 156.33MB / 156.33MB 35.7s done
#7 extracting sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4
#7 extracting sha256:7bddbfbcf00f9dde2d79c07cbf11422b3fd09098c518809fae943df61125f2a4 1.4s done
#7 DONE 38.8s

#7 [build 1/4] FROM docker.io/library/eclipse-temurin:21-jdk-alpine@sha256:6ea5548706b60ac0a602eaf48af74792cbab012d90e811ca8db6184b16b5c3d6
#7 extracting sha256:981f95701eabca34d7f767c424a7f3e4fccfa331cf3de975025a1412f403e43d 0.0s done
#7 extracting sha256:ef400840b5e60a28eb6e26b47dca860d731a494752e91862f73ae0d532131a30 0.0s done
#7 DONE 38.8s

#9 [build 2/4] WORKDIR /build
#9 DONE 0.0s

#10 [build 3/4] COPY src/HelloWorld.java .
#10 DONE 0.0s

#11 [build 4/4] RUN javac HelloWorld.java
#11 DONE 0.6s

#12 [stage-1 3/3] COPY --from=build /build/HelloWorld.class .
#12 DONE 0.0s

#13 exporting to image
#13 exporting layers 0.0s done
#13 exporting manifest sha256:47aa876203efcb54e4caa14d343ba81c9a15269ab2e5536d34833c5cf5026027 done
#13 exporting config sha256:cc0dcff3e6675b15c72b54ad2ab7dd304dc64b0d334dd8146721b062b879c375 done
#13 exporting attestation manifest sha256:81c08fc26d6a278dd37e2d6fa267199475fdfa6e6f9535a2d6ad319fc46f2fc7 done
#13 exporting manifest list sha256:dcd130915e2ce10c381722bef0665f471cd26f852093ee5f392ae72a3a05a314 done
#13 naming to docker.io/library/df-java:1.0 done
#13 unpacking to docker.io/library/df-java:1.0 0.0s done
#13 DONE 0.1s
```

### 4) Apache-app - httpd:2.4-alpine + custom index.html

```console
aman@macbook Apache-app % docker build -t df-apache:1.0 .
#5 sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 6.29MB / 10.99MB 7.8s
#5 sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 7.34MB / 10.99MB 8.3s
#5 sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 8.39MB / 10.99MB 9.0s
#5 sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 9.44MB / 10.99MB 9.5s
#5 sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 10.49MB / 10.99MB 9.9s
#5 sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 10.99MB / 10.99MB 10.0s done
#5 extracting sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802
#5 extracting sha256:0174c8f269d8d56ca267c1fffd9cd8206eaad6c35bd4e71159e41f8ff212a802 0.3s done
#5 DONE 10.4s

#5 [1/2] FROM docker.io/library/httpd:2.4-alpine@sha256:1b766f17b84026429b7cb243317b142921b24432336e798bc881c43f45ed9567
#5 extracting sha256:e8da629feebaf24949d5a5a2c7d3395d6d9bd6f7823f9b531470870a58c765f3 0.1s done
#5 DONE 10.5s

#5 [1/2] FROM docker.io/library/httpd:2.4-alpine@sha256:1b766f17b84026429b7cb243317b142921b24432336e798bc881c43f45ed9567
#5 extracting sha256:06ed2d154fac530ce7863a384cdc41e42a7296aff6858e262ad3c185986456a7 0.0s done
#5 DONE 10.5s

#6 [2/2] COPY index.html /usr/local/apache2/htdocs/index.html
#6 DONE 0.2s

#7 exporting to image
#7 exporting layers 0.0s done
#7 exporting manifest sha256:8111f7e55651efedbe084e2f607ade51feb7a455205adf4291606a9b90dabd47 done
#7 exporting config sha256:eeaceed82834393fbed56afa049b4cfd4edd6094bc58650e70e6fb958525e891 done
#7 exporting attestation manifest sha256:7b09e0bc1bb073fa332c056d824b5dac1f5874e8fb7eeca73980fb02088fa767 done
#7 exporting manifest list sha256:6c4b459f67482e928f7c770ee5357627a6c2b7b3c63edab5a229783b450f7e27 done
#7 naming to docker.io/library/df-apache:1.0 done
#7 unpacking to docker.io/library/df-apache:1.0 0.0s done
#7 DONE 0.1s
```

### 5) nginx-app - nginx:alpine + custom default.conf + index.html

```console
aman@macbook nginx-app % docker build -t df-nginx:1.0 .
#2 DONE 0.0s

#3 [internal] load .dockerignore
#3 transferring context: 2B done
#3 DONE 0.0s

#4 [internal] load build context
#4 transferring context: 899B done
#4 DONE 0.0s

#5 [1/3] FROM docker.io/library/nginx:alpine@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913
#5 resolve docker.io/library/nginx:alpine@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913 done
#5 DONE 0.1s

#6 [2/3] COPY default.conf /etc/nginx/conf.d/default.conf
#6 DONE 0.0s

#7 [3/3] COPY index.html /usr/share/nginx/html/index.html
#7 DONE 0.0s

#8 exporting to image
#8 exporting layers 0.1s done
#8 exporting manifest sha256:582b3c9468bb0ff9988c1960562131d6fe2fbca533e6f514733df0b6bce26035 done
#8 exporting config sha256:e8a689a0e899a430d3520dc0f45c90d5bd6511ec123786539a85ca0fdeed6021
#8 exporting config sha256:e8a689a0e899a430d3520dc0f45c90d5bd6511ec123786539a85ca0fdeed6021 done
#8 exporting attestation manifest sha256:c3c4a398f2df460949c7a90e67df26be003d7debe9dd06676667b96ec3fa2e8e done
#8 exporting manifest list sha256:9d53a5be511e795ba365b6fc18282d8a8affe0a1e52d04492f591f9d68de8c29 done
#8 naming to docker.io/library/df-nginx:1.0 done
#8 unpacking to docker.io/library/df-nginx:1.0 0.0s done
#8 DONE 0.1s
```

### 6) React-app - multi-stage: node+esbuild builds a real React app, nginx serves it

```console
aman@macbook React-app % docker build -t df-react:1.0 .

#9 [build 3/7] COPY package.json ./
#9 DONE 0.0s

#10 [build 4/7] RUN npm install
#10 8.603 
#10 8.603 added 7 packages, and audited 8 packages in 8s
#10 8.605 
#10 8.605 1 moderate severity vulnerability
#10 8.605 
#10 8.605 To address all issues (including breaking changes), run:
#10 8.605   npm audit fix --force
#10 8.605 
#10 8.605 Run `npm audit` for details.
#10 8.606 npm notice
#10 8.606 npm notice New major version of npm available! 10.9.8 -> 12.0.2
#10 8.606 npm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2
#10 8.606 npm notice To update run: npm install -g npm@12.0.2
#10 8.606 npm notice
#10 DONE 9.0s

#11 [build 5/7] COPY src ./src
#11 DONE 0.0s

#12 [build 6/7] COPY public ./public
#12 DONE 0.0s

#13 [build 7/7] RUN npm run build
#13 0.235 
#13 0.235 > react-hello-world@1.0.0 build
#13 0.235 > esbuild src/index.jsx --bundle --minify --outfile=public/bundle.js
#13 0.235 
#13 0.259 
#13 0.259   public/bundle.js  139.0kb
#13 0.259 
#13 0.259 ⚡ Done in 20ms
#13 DONE 0.3s

#14 [stage-1 2/2] COPY --from=build /app/public /usr/share/nginx/html
#14 DONE 0.0s

#15 exporting to image
#15 exporting layers 0.0s done
#15 exporting manifest sha256:e7087f2bb753c7e3ce96df45e0e63ae414d4f3ca127cc18299fb2b6a059ce5d1 done
#15 exporting config sha256:98a2fa3499787a58b3eab9616c51e47a15346f407e482545d47d79e56cdb92ea done
#15 exporting attestation manifest sha256:de0c165d21c236057863b6d5e58cbfd7c61c090a1cdd07e6338f2df8f7b04d38 done
#15 exporting manifest list sha256:54e2417c8b9ae70c53fbd0350066241043552229b591b51fb6a236753f897cbb done
#15 naming to docker.io/library/df-react:1.0 done
#15 unpacking to docker.io/library/df-react:1.0 0.0s done
#15 DONE 0.1s
```

### Summary: all six images built

```console
aman@macbook docker-fundamentals % docker images | grep -E 'REPOSITORY|df-'
IMAGE                                                                                         ID             DISK USAGE   CONTENT SIZE   EXTRA
df-apache:1.0                                                                                 6c4b459f6748        105MB         21.1MB        
df-java:1.0                                                                                   dcd130915e2c        286MB         73.4MB        
df-nginx:1.0                                                                                  9d53a5be511e       92.8MB         26.2MB        
df-nodejs:1.0                                                                                 020b6db88d99        228MB         58.1MB        
df-python:1.0                                                                                 f1e8b23353d3       87.8MB         21.4MB        
df-react:1.0                                                                                  54e2417c8b9a       92.9MB         26.2MB        

# --- bug found when running df-java: NoClassDefFoundError for the nested
#     HelloHandler class. javac emits one .class file per class (including
#     the inner static class HelloWorld$HelloHandler.class), but the
#     Dockerfile only copied HelloWorld.class into the runtime stage. ---

aman@macbook java-app % docker run -d --name df-java -p 18083:8080 df-java:1.0
aman@macbook java-app % docker ps -a --filter name=df-java
CONTAINER ID   IMAGE         COMMAND                  CREATED         STATUS                     PORTS     NAMES
5e531ea16c95   df-java:1.0   "java HelloWorld"        5 seconds ago   Exited (1) 4 seconds ago             df-java
aman@macbook java-app % docker logs df-java
Exception in thread "main" java.lang.NoClassDefFoundError: HelloWorld$HelloHandler
	at HelloWorld.main(HelloWorld.java:23)
Caused by: java.lang.ClassNotFoundException: HelloWorld$HelloHandler
	at java.base/jdk.internal.loader.BuiltinClassLoader.loadClass(Unknown Source)
	at java.base/jdk.internal.loader.ClassLoaders$AppClassLoader.loadClass(Unknown Source)
	at java.base/java.lang.ClassLoader.loadClass(Unknown Source)
	... 1 more

# --- root cause: javac HelloWorld.java compiles to TWO class files -
#     HelloWorld.class and HelloWorld$HelloHandler.class (the nested static
#     handler). The Dockerfile only copied the first one into the JRE stage,
#     so the JVM found the entry class but not the handler it references.
#     Fix: COPY --from=build /build/*.class . instead of a single filename,
#     then remove the broken container and rebuild. ---

aman@macbook java-app % docker rm -f df-java
df-java

aman@macbook java-app % docker build -t df-java:1.0 .

aman@macbook java-app % docker build -t df-java:1.0 .
#9 CACHED

#10 [build 2/4] WORKDIR /build
#10 CACHED

#11 [build 4/4] RUN javac HelloWorld.java
#11 CACHED

#12 [stage-1 3/3] COPY --from=build /build/*.class .
#12 DONE 0.0s

#13 exporting to image
#13 exporting layers 0.0s done
#13 exporting manifest sha256:71a6e7f1fb8d6f407aaa82184c3856f35937b026cbe89e23e32db5e86d5e79fc done
#13 exporting config sha256:dbe535e758fe46e743c58b1b8d1946048f314766f0e9ebef4aa1500390f4685e done
#13 exporting attestation manifest sha256:fdbb178378211610a16a62e2895dc08cc1a7dae6717bab1e5410f4b10ff65e9e done
#13 exporting manifest list sha256:f3ce876611a1545e367d7f7d8f026e11d7549862d1329c5a566a51fdc33aff48 done
#13 naming to docker.io/library/df-java:1.0 done
#13 unpacking to docker.io/library/df-java:1.0 done
#13 DONE 0.1s


# --- follow-up fix found later while testing 'docker logs' (see docker-c.txt):
#     Python buffers stdout when not attached to a TTY, so print()/log_message()
#     output never reached 'docker logs' until the process exited. Added
#     ENV PYTHONUNBUFFERED=1 to the Dockerfile and rebuilt. ---

aman@macbook python-app % docker build -t df-python:1.0 .

#5 [1/3] FROM docker.io/library/python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a
#5 resolve docker.io/library/python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a done
#5 DONE 0.0s

#6 [2/3] WORKDIR /app
#6 CACHED

#7 [3/3] COPY app.py .
#7 CACHED

#8 exporting to image
#8 exporting layers done
#8 exporting manifest sha256:e94524c6bb359f5f97f28f603a88a75b32d88f6d8697dbf94317ac23f7736ce3 done
#8 exporting config sha256:68b9d0c0ebc5ced0adc6e11e10c88d30cd0b0024d6367bf72f3545047bc8eb58 done
#8 exporting attestation manifest sha256:394b083b27d75ce77fd44aa829b9397483eebf3449700476287fb260f7b69a9e done
#8 exporting manifest list sha256:8285121e79b15f921094a1de887b559dd6dc4d35994aa20e7064b5eae1bb8847 done
#8 naming to docker.io/library/df-python:1.0 done
#8 unpacking to docker.io/library/df-python:1.0 done
#8 DONE 0.1s
```
