import { NextRequest, NextResponse } from 'next/server';
import http from 'node:http';

const internalApiUrl = process.env.INTERNAL_API_URL || 'http://127.0.0.1:4000';

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> | { path: string[] } }) {
  const resolvedParams = await Promise.resolve(context?.params);
  const path = resolvedParams?.path;
  const subPath = Array.isArray(path) ? path.join('/') : (path || '');
  const search = request.nextUrl.search;
  const targetUrl = `${internalApiUrl}/api/${subPath}${search}`;

  const bodyBuffer = ['GET', 'HEAD'].includes(request.method)
    ? undefined
    : Buffer.from(await request.arrayBuffer());

  return new Promise<NextResponse>((resolve) => {
    const url = new URL(targetUrl);
    const reqHeaders: Record<string, string> = {};
    request.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (!['host', 'connection', 'transfer-encoding', 'content-length'].includes(lower)) {
        reqHeaders[key] = value;
      }
    });

    if (bodyBuffer) {
      reqHeaders['content-length'] = String(bodyBuffer.length);
    }

    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port ? Number(url.port) : 4000,
        path: url.pathname + url.search,
        method: request.method,
        headers: reqHeaders,
        timeout: 180000, // 3 minutes full timeout
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
        res.on('end', () => {
          const resHeaders = new Headers();
          for (const [k, v] of Object.entries(res.headers)) {
            const lower = k.toLowerCase();
            if (v && !['transfer-encoding', 'content-encoding', 'content-length'].includes(lower)) {
              if (Array.isArray(v)) {
                v.forEach((item) => resHeaders.append(k, item));
              } else {
                resHeaders.set(k, v);
              }
            }
          }
          const statusCode = res.statusCode || 200;
          // HTTP 204, 205, and 304 MUST NOT have a response body according to Fetch specification
          const hasNoBody = [204, 205, 304].includes(statusCode);
          const responseBody = hasNoBody ? null : Buffer.concat(chunks);
          resolve(
            new NextResponse(responseBody, {
              status: statusCode,
              statusText: res.statusMessage || 'OK',
              headers: resHeaders,
            })
          );
        });
      }
    );

    req.on('timeout', () => {
      req.destroy();
      resolve(
        NextResponse.json(
          { error: { message: 'Upstream request timed out (180s limit)' } },
          { status: 504 }
        )
      );
    });

    req.on('error', (err) => {
      resolve(
        NextResponse.json(
          { error: { message: err?.message || 'Upstream service unavailable' } },
          { status: 502 }
        )
      );
    });

    if (bodyBuffer && bodyBuffer.length > 0) {
      req.write(bodyBuffer);
    }
    req.end();
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const dynamic = 'force-dynamic';
