// Minimal Go HTTP server used to demonstrate a Docker multi-stage build.
// Requirement: it must serve exactly "Hello World from Docker multi-stage build"
// on port 8080.
package main

import (
	"fmt"
	"log"
	"net/http"
)

const message = "Hello World from Docker multi-stage build"

func handler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprint(w, message)
}

func main() {
	http.HandleFunc("/", handler)
	log.Println("multi-stage demo app listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
