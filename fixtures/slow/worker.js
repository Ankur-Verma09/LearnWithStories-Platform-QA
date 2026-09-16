const headers = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      return new Response(JSON.stringify({ status: "ok", release: "slow" }), {
        status: 200,
        headers,
      });
    }
    return new Response("Learn With Stories QA - slow", {
      status: 200,
      headers: { ...headers, "Content-Type": "text/plain; charset=utf-8" },
    });
  },
};

