/**
 * Server-side proxy to the FastAPI backend.
 *
 * Why this exists instead of a next.config rewrite:
 *
 *  1. The browser is not necessarily the machine running this app (containers,
 *     remote preview URLs), so the client must never be told to call
 *     localhost:8000. It calls same-origin /api/v1/* and this handler forwards.
 *  2. Next's built-in rewrite proxy hangs up the socket after 30 s. Real MCDA
 *     and network analyses over the live graph take longer, so every heavy
 *     POST died with ECONNRESET -> 500 -> the client silently swapped in mock
 *     data. This handler sets its own, much longer budget.
 *
 * Backend location is configurable with BACKEND_ORIGIN (server-side only).
 */
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

const BACKEND = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
/** Long enough for site suitability / accessibility on the full graph. */
const UPSTREAM_TIMEOUT_MS = 240_000;

async function forward(req: NextRequest, path: string[]) {
  const search = req.nextUrl.search ?? "";
  const url = `${BACKEND}/api/v1/${path.join("/")}${search}`;

  const headers = new Headers();
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);

  const method = req.method.toUpperCase();
  const body =
    method === "GET" || method === "HEAD" ? undefined : await req.text();

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), UPSTREAM_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method,
      headers,
      body,
      signal: ctrl.signal,
      cache: "no-store"
    });
    const payload = await res.arrayBuffer();
    return new Response(payload, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store"
      }
    });
  } catch (err: unknown) {
    const aborted = err instanceof Error && err.name === "AbortError";
    // Report the failure honestly instead of letting it look like a backend
    // 500: the client distinguishes "backend down" from "backend said no".
    return Response.json(
      {
        error: aborted ? "backend timeout" : "backend unreachable",
        detail: err instanceof Error ? err.message : String(err),
        upstream: url
      },
      { status: 504 }
    );
  } finally {
    clearTimeout(timer);
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
