const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  PageNumber, Header, Footer, LevelFormat, PageBreak
} = require('docx');
const fs = require('fs');

// ── helpers ────────────────────────────────────────────────────────────────
const border = { style: BorderStyle.SINGLE, size: 1, color: 'B0B0B0' };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorders = {
  top:    { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  left:   { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  right:  { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
};

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)], spacing: { before: 320, after: 120 } });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)], spacing: { before: 240, after: 100 } });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)], spacing: { before: 200, after: 80 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, ...opts })],
    spacing: { after: 120 },
  });
}
function bold(text) {
  return new TextRun({ text, bold: true, size: 22 });
}
function normal(text) {
  return new TextRun({ text, size: 22 });
}
function mixedPara(runs, spacing = 120) {
  return new Paragraph({ children: runs, spacing: { after: spacing } });
}
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bullets', level },
    children: [new TextRun({ text, size: 22 })],
    spacing: { after: 80 },
  });
}
function code(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: 'Courier New', size: 18, color: '1F1F1F' })],
    shading: { fill: 'F4F4F4', type: ShadingType.CLEAR },
    spacing: { after: 60 },
    indent: { left: 480 },
  });
}
function spacer() {
  return new Paragraph({ children: [new TextRun('')], spacing: { after: 120 } });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function twoColTable(rows) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2520, 6840],
    rows: rows.map(([a, b]) => new TableRow({
      children: [
        new TableCell({ borders, width: { size: 2520, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: a, size: 20, bold: true })] })] }),
        new TableCell({ borders, width: { size: 6840, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: b, size: 20 })] })] }),
      ]
    }))
  });
}

function memberTable(rows) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 4680],
    rows: [
      new TableRow({
        children: [
          new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Member', bold: true, color: 'FFFFFF', size: 20 })] })] }),
          new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'GitHub Handle', bold: true, color: 'FFFFFF', size: 20 })] })] }),
          new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 4680, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Contribution', bold: true, color: 'FFFFFF', size: 20 })] })] }),
        ]
      }),
      ...rows.map(([member, handle, contrib], i) => new TableRow({
        children: [
          new TableCell({ borders, shading: { fill: i % 2 === 0 ? 'DEEAF1' : 'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: member, size: 20 })] })] }),
          new TableCell({ borders, shading: { fill: i % 2 === 0 ? 'DEEAF1' : 'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: handle, size: 20 })] })] }),
          new TableCell({ borders, shading: { fill: i % 2 === 0 ? 'DEEAF1' : 'FFFFFF', type: ShadingType.CLEAR }, width: { size: 4680, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: contrib, size: 20 })] })] }),
        ]
      }))
    ]
  });
}

function apiTable(rows) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [1440, 2880, 5040],
    rows: [
      new TableRow({
        children: [
          new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 1440, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Method', bold: true, color: 'FFFFFF', size: 20 })] })] }),
          new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2880, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Endpoint', bold: true, color: 'FFFFFF', size: 20 })] })] }),
          new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 5040, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Description', bold: true, color: 'FFFFFF', size: 20 })] })] }),
        ]
      }),
      ...rows.map(([method, endpoint, desc], i) => new TableRow({
        children: [
          new TableCell({ borders, shading: { fill: i % 2 === 0 ? 'DEEAF1' : 'FFFFFF', type: ShadingType.CLEAR }, width: { size: 1440, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: method, size: 20, bold: true, color: '1F4E79' })] })] }),
          new TableCell({ borders, shading: { fill: i % 2 === 0 ? 'DEEAF1' : 'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2880, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: endpoint, size: 20, font: 'Courier New' })] })] }),
          new TableCell({ borders, shading: { fill: i % 2 === 0 ? 'DEEAF1' : 'FFFFFF', type: ShadingType.CLEAR }, width: { size: 5040, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: desc, size: 20 })] })] }),
        ]
      }))
    ]
  });
}

// ── document ──────────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Calibri', color: '1F4E79' },
        paragraph: { spacing: { before: 320, after: 120 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '1F4E79', space: 1 } } }
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Calibri', color: '2E74B5' },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 }
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Calibri', color: '5B9BD5' },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 }
      },
    ]
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: '\u2013', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
        ]
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            children: [new TextRun({ text: 'CO3094 – Assignment 1 Report: Non-Blocking HTTP Server & Chat Application', size: 18, color: '666666' })],
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA', space: 1 } }
          })
        ]
      })
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [
              new TextRun({ text: 'Page ', size: 18, color: '888888' }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '888888' }),
              new TextRun({ text: ' of ', size: 18, color: '888888' }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: '888888' }),
            ],
            border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA', space: 1 } }
          })
        ]
      })
    },
    children: [

      // ─── TITLE PAGE ──────────────────────────────────────────────────
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 1440, after: 200 },
        children: [new TextRun({ text: 'HCMC University of Technology', size: 28, bold: true, color: '1F4E79' })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
        children: [new TextRun({ text: 'Faculty of Computer Science & Engineering', size: 24, color: '2E74B5' })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
        children: [new TextRun({ text: 'Course: CO3094 – Computer Network', size: 24, color: '2E74B5' })]
      }),
      spacer(),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 480, after: 200 },
        children: [new TextRun({ text: 'ASSIGNMENT 1 REPORT', size: 52, bold: true, color: '1F4E79' })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
        children: [new TextRun({ text: 'Non-Blocking HTTP Server & Hybrid Chat Application', size: 30, bold: true, color: '2E74B5' })]
      }),
      spacer(),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 480, after: 80 },
        children: [new TextRun({ text: 'Academic Year 2025–2026  |  March 2026', size: 22, color: '555555' })]
      }),

      spacer(),
      // Team table
      memberTable([
        ['Thái (repo1)',  'dangthai011205',    'Client-server chat paradigm, Peer, Tracker, PeerRegistry'],
        ['(repo2)',       'calcusan',          'Channel management, ChannelPool, Proxy load balancing'],
        ['Phú (repo3)',   'phutranphu1109-del','HTTP Authentication (RFC 2617/7235/6265), Response helpers'],
        ['Long (repo4)',  '2005nglong-source', 'P2P chat app, async broadcast with asyncio.gather'],
        ['Minh (repo5)',  'Cminh11',           'Non-blocking backend (ASYNC_MODE, callback/coroutine modes)'],
      ]),
      pageBreak(),

      // ─── 1. INTRODUCTION ─────────────────────────────────────────────
      h1('1. Introduction'),
      p('This report documents the design, implementation and testing of Assignment 1 for CO3094 Computer Network. The objective was to build a non-blocking HTTP server framework (AsynapRous) and a hybrid Peer-to-Peer (P2P) chat application that integrates client-server and peer-to-peer paradigms.'),
      p('The system consists of five main components: a reverse proxy, a backend server, the AsynapRous routing framework, a centralised tracker for peer discovery, and a P2P chat application. Each component was implemented by one or more team members and then merged into a single cohesive codebase.'),

      h2('1.1 Assignment Objectives'),
      bullet('Implement a non-blocking TCP communication mechanism using Python standard library.'),
      bullet('Build an HTTP server with authentication (RFC 2617, RFC 7235, RFC 6265).'),
      bullet('Develop a hybrid chat application that combines client-server and peer-to-peer communication.'),
      bullet('Design and implement custom application-level protocols for peer interaction.'),
      spacer(),

      h2('1.2 System Overview'),
      p('Figure 1 in the assignment specification illustrates the overall architecture: multiple clients connect through a Proxy process, which routes requests to one or more Backend processes. In addition, the AsynapRous framework hosts the P2P tracker and peer-side HTTP services.'),
      p('The proxy uses virtual-host routing defined in config/proxy.conf, implementing round-robin load balancing across multiple backend instances. Each backend runs in one of three non-blocking modes controlled by the ASYNC_MODE environment variable.'),

      pageBreak(),

      // ─── 2. NON-BLOCKING MECHANISMS ──────────────────────────────────
      h1('2. Non-Blocking Communication Mechanisms'),
      p('Section 2.1 of the assignment specification requires that the server use non-blocking I/O rather than blocking sockets, so that a single server thread can handle thousands of concurrent connections. Three distinct mechanisms were implemented, selectable at runtime.'),

      h2('2.1 Mode Selection'),
      p('The backend server reads the ASYNC_MODE environment variable at startup to choose its concurrency strategy:'),
      code('ASYNC_MODE=threading  python start_backend.py   # default'),
      code('ASYNC_MODE=callback   python start_backend.py   # selector event-loop'),
      code('ASYNC_MODE=coroutine  python start_backend.py   # asyncio'),
      p('The selection logic is implemented in daemon/backend.py inside run_backend(). If an invalid value is supplied the server falls back to threading mode and logs a warning.'),

      h2('2.2 Multi-Threading Mode'),
      p('In the default threading mode the server calls server.accept() in a loop. For each incoming connection it spawns a Python daemon thread that calls handle_client(), which in turn instantiates an HttpAdapter and processes the full request-response cycle. Thread objects are marked daemon=True so they do not block program exit.'),
      p('This mode is the simplest to reason about and is well-suited to moderate concurrency. Each thread blocks independently on recv() calls, preventing slow clients from affecting others.'),

      h2('2.3 Callback / Selector Mode'),
      p('In callback mode the listening socket is set to non-blocking and registered with Python\'s selectors.DefaultSelector. The main loop calls sel.select(timeout=None), which blocks cheaply at the OS level until at least one file descriptor is ready. When the server socket becomes readable a callback (handle_client_callback) is invoked to accept one connection and process it.'),
      p('This is the classic event-driven, single-threaded model. It avoids thread creation overhead but requires that each handler complete quickly; long-running handlers would stall the event loop.'),

      h2('2.4 Coroutine (asyncio) Mode'),
      p('In coroutine mode asyncio.run() launches async_server(), which calls asyncio.start_server(). The asyncio event loop schedules incoming connections as coroutines. Each connection is handled by connection_handler(), which creates an HttpAdapter and awaits handle_client_coroutine().'),
      p('The coroutine handler reads the request with await reader.read(65536) and writes the response with writer.write() followed by await writer.drain(). Because all waits are non-blocking yields to the event loop, a single thread can service many concurrent connections with minimal memory overhead.'),

      h2('2.5 Comparison'),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2340, 2340, 2340, 2340],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Mode', bold: true, color: 'FFFFFF', size: 20 })] })] }),
            new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Mechanism', bold: true, color: 'FFFFFF', size: 20 })] })] }),
            new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Strengths', bold: true, color: 'FFFFFF', size: 20 })] })] }),
            new TableCell({ borders, shading: { fill: '1F4E79', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: 'Limitations', bold: true, color: 'FFFFFF', size: 20 })] })] }),
          ]}),
          ...([
            ['threading', 'Thread per connection', 'Simple, familiar', 'Memory per thread'],
            ['callback', 'Selector + callback', 'Low overhead', 'Handlers must be fast'],
            ['coroutine', 'asyncio async/await', 'Scalable, readable', 'Python GIL for CPU tasks'],
          ].map(([a,b,c,d], i) => new TableRow({ children: [
            new TableCell({ borders, shading: { fill: i%2===0?'DEEAF1':'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: a, size: 20, font: 'Courier New' })] })] }),
            new TableCell({ borders, shading: { fill: i%2===0?'DEEAF1':'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: b, size: 20 })] })] }),
            new TableCell({ borders, shading: { fill: i%2===0?'DEEAF1':'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: c, size: 20 })] })] }),
            new TableCell({ borders, shading: { fill: i%2===0?'DEEAF1':'FFFFFF', type: ShadingType.CLEAR }, width: { size: 2340, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: d, size: 20 })] })] }),
          ]}))),
        ]
      }),
      spacer(),
      pageBreak(),

      // ─── 3. PROXY AND BACKEND ─────────────────────────────────────────
      h1('3. Proxy Server and Backend'),

      h2('3.1 Proxy Design'),
      p('The proxy server is implemented in daemon/proxy.py. It binds to a port (default 8080), accepts client connections in a thread pool, extracts the HTTP Host header from each incoming request, and resolves it against the virtual-host routing table loaded from config/proxy.conf.'),
      p('Routing resolution is performed by resolve_routing_policy(), which looks up the hostname in the routes dictionary. Each entry maps a hostname to a tuple of (proxy_list, policy). When multiple backends are defined, apply_load_balancing() selects one according to the configured policy (round-robin by default, with random as an alternative).'),

      h2('3.2 Connection Pooling (ChannelPool)'),
      p('Rather than opening a new TCP socket for every forwarded request, the proxy maintains a ChannelPool (daemon/channel.py). The pool stores idle Channel objects keyed by (host, port). When a backend connection is needed, get_channel() first tries to dequeue an idle channel; if none is available it creates a new one, up to max_pool_size. After the response is received the channel is released back to the pool via release_channel().'),
      p('Stale channels (unused for longer than idle_timeout seconds) are periodically closed by cleanup_stale_channels(). Thread safety is ensured by a threading.Lock guarding all pool operations.'),

      h2('3.3 Configuration Format'),
      p('The proxy reads config/proxy.conf on startup. Each block declares a virtual host and its backend targets:'),
      code('host "192.168.56.103:8080" {'),
      code('    proxy_pass http://192.168.56.103:9000;'),
      code('}'),
      code('host "app2.local" {'),
      code('    proxy_pass http://192.168.56.210:9002;'),
      code('    proxy_pass http://192.168.56.220:9002;'),
      code('    dist_policy round-robin'),
      code('}'),

      h2('3.4 Backend Server'),
      p('The backend server (daemon/backend.py, launched via start_backend.py) binds to a configurable port (default 9000) and delegates every accepted connection to an HttpAdapter instance. The adapter handles the full HTTP lifecycle: parsing, authentication, route dispatch, and response construction.'),
      spacer(),
      pageBreak(),

      // ─── 4. HTTP ADAPTER AND REQUEST/RESPONSE ─────────────────────────
      h1('4. HTTP Request/Response Pipeline'),

      h2('4.1 Request Parsing'),
      p('The Request class (daemon/request.py) parses a raw HTTP string received from the socket. The prepare() method performs the following steps:'),
      bullet('Split the raw string at the first double CRLF to separate headers from the body (fetch_headers_body).'),
      bullet('Parse the request line to extract the HTTP method, path, and version (extract_request_line). A bare "/" path is normalised to "/index.html".'),
      bullet('Parse header lines into a CaseInsensitiveDict for case-insensitive header lookup.'),
      bullet('Parse the Cookie header into a key-value dict (parse_cookies, RFC 6265).'),
      bullet('Decode the Authorization header to extract Basic auth credentials (prepare_auth, RFC 2617).'),
      bullet('Look up the matched route handler from the routes dict for the (method, path) key.'),

      h2('4.2 Response Construction'),
      p('The Response class (daemon/response.py) builds raw HTTP response bytes. Key methods include:'),
      bullet('build_response(request): serves static files from the www/ or static/ directories, setting MIME types via mimetypes.guess_type().'),
      bullet('build_unauthorized(): returns a 401 response with WWW-Authenticate: Basic realm="AsynapRous" per RFC 7235.'),
      bullet('build_set_cookie_response(body, cookies): returns a 200 response with one or more Set-Cookie headers per RFC 6265.'),
      bullet('build_json_ok(body): returns a 200 response with Content-Type: application/json.'),
      bullet('build_notfound(): returns a standard 404 response.'),

      h2('4.3 HttpAdapter'),
      p('HttpAdapter (daemon/httpadapter.py) coordinates the request-response cycle. Its handle_client() method orchestrates the full flow:'),
      bullet('Receive the full request body, respecting the Content-Length header to avoid truncation.'),
      bullet('Call _is_authenticated() which tries cookie-session authentication first, then HTTP Basic auth.'),
      bullet('If the path is /login and method is POST/PUT, call _handle_login() to validate credentials against _USER_DB and issue a session cookie via _create_session().'),
      bullet('For other paths with a registered route hook, call _invoke_hook() which handles both synchronous and async (coroutine) handlers.'),
      bullet('For static file paths, call resp.build_response() directly.'),
      bullet('Send the response bytes via conn.sendall() and close the connection.'),
      spacer(),
      pageBreak(),

      // ─── 5. AUTHENTICATION ────────────────────────────────────────────
      h1('5. Authentication Implementation'),

      h2('5.1 HTTP Basic Authentication (RFC 2617 / RFC 7235)'),
      p('When an unauthenticated request is made to a protected resource, the server returns:'),
      code('HTTP/1.1 401 Unauthorized'),
      code('WWW-Authenticate: Basic realm="AsynapRous"'),
      p('The client then retries with an Authorization header:'),
      code('Authorization: Basic dXNlcjE6cGFzc3dvcmQx'),
      p('Request.prepare_auth() decodes the Base64-encoded "username:password" credential. HttpAdapter._authenticate_basic() looks up the username in _USER_DB and compares the password. On success the username is returned; on failure None is returned and a 401 is sent.'),

      h2('5.2 Cookie Session Management (RFC 6265)'),
      p('Posting valid credentials to /login triggers the _handle_login() path in HttpAdapter. The server:'),
      bullet('Accepts credentials in JSON body ({"username": "...", "password": "..."}) or in the Authorization header.'),
      bullet('Validates against _USER_DB.'),
      bullet('Calls _create_session() which invokes utils.generate_session_token() to produce a unique token, stores username -> token in _SESSION_STORE, and returns the token.'),
      bullet('Returns a 200 response with Set-Cookie: session_token=<token>; HttpOnly; Path=/'),
      p('Subsequent requests include Cookie: session_token=<token>. The server calls _authenticate_cookie(), which looks up the token in _SESSION_STORE and returns the associated username if found.'),

      h2('5.3 Public and Protected Paths'),
      p('The following paths are publicly accessible without authentication: /index.html, /login.html, /form.html, /favicon.ico, and any path under /css/, /images/, or /static/. All other paths require either a valid session cookie or Basic auth credentials.'),

      h2('5.4 Default User Database'),
      twoColTable([
        ['Username', 'Password'],
        ['admin',    'admin123'],
        ['user1',    'password1'],
        ['user2',    'password2'],
      ]),
      spacer(),
      pageBreak(),

      // ─── 6. ASYNAPROUS FRAMEWORK ──────────────────────────────────────
      h1('6. AsynapRous Framework'),
      p('AsynapRous (daemon/asynaprous.py) is a lightweight decorator-based RESTful router modelled on Flask/FastAPI patterns but built entirely on Python standard library primitives. It bridges the routing layer and the backend server.'),

      h2('6.1 Route Registration'),
      p('Developers register route handlers using the @app.route() decorator:'),
      code('@app.route("/login", methods=["POST"])'),
      code('def login(headers, body):'),
      code('    return {"message": "Logged in"}'),
      p('Internally route() maps each (METHOD, path) tuple to the handler function in a dict. Both synchronous and async (coroutine) handlers are supported. The decorator wraps the function in either sync_wrapper or async_wrapper accordingly and preserves _route_path and _route_methods metadata on the function object.'),

      h2('6.2 Server Launch'),
      p('Calling app.prepare_address(ip, port) stores the bind address, and app.run() delegates to create_backend(), passing the routes dict. The backend server then uses the routes dict during request parsing (in Request.prepare()) to match incoming requests to handlers.'),

      h2('6.3 Independent Operation'),
      p('AsynapRous can run independently without a proxy, useful for the P2P peer app and tracker. The sample app (apps/sampleapp.py) demonstrates this pattern, exposing /login and /echo endpoints on port 2026.'),
      spacer(),
      pageBreak(),

      // ─── 7. HYBRID P2P CHAT ───────────────────────────────────────────
      h1('7. Hybrid P2P Chat Application'),
      p('Section 2.3 of the specification requires a hybrid chat application combining client-server and peer-to-peer paradigms. The implementation spans three modules: daemon/tracker.py (centralised server), daemon/peer.py (peer client), and apps/p2papp.py (peer HTTP server).'),

      h2('7.1 Initialization Phase — Client-Server Paradigm'),

      h3('7.1.1 Tracker Server (PeerRegistry)'),
      p('The tracker (daemon/tracker.py) is a centralised registration server. It maintains an in-memory dict of peers keyed by "ip:port" strings. Each entry records the IP, port, last-seen timestamp, and status. A background keepalive thread periodically calls cleanup_inactive_peers() to remove peers whose last heartbeat exceeded timeout_seconds (default 30 s).'),
      p('The tracker is exposed as an HTTP service via apps/trackerapp.py and start_tracker.py, using the AsynapRous framework on port 9000 (by default).'),

      h3('7.1.2 Tracker REST API'),
      apiTable([
        ['POST', '/register',   'Register a new peer; body: {"ip": "...", "port": N}; returns peer_id'],
        ['GET',  '/discover',   'Return list of all active peers with their ip and port'],
        ['POST', '/connect',    'Return connection details for a target peer; body: {source_peer_id, target_peer_id}'],
        ['GET',  '/status',     'Return tracker statistics (total, active peers, timeout)'],
      ]),

      h3('7.1.3 Peer Registration and Discovery'),
      p('The Peer class (daemon/peer.py) encapsulates a peer\'s client logic. On startup (start_p2p.py) the following sequence executes:'),
      bullet('peer.register() — sends POST /register to the tracker with own ip and port.'),
      bullet('peer.discover_peers() — sends GET /discover, updates the local known_peers list.'),
      bullet('peer.start_discovery() — launches a background thread that repeats discover_peers() every discovery_interval seconds.'),
      bullet('peer.connect_to_peer(target_peer_id) — sends POST /connect to the tracker to obtain connection details, then opens a direct TCP socket to the target.'),

      h2('7.2 Peer-to-Peer Chat Phase'),

      h3('7.2.1 P2P App Endpoints'),
      p('Each peer runs an AsynapRous HTTP server (apps/p2papp.py) to receive messages from other peers:'),
      apiTable([
        ['POST', '/send-peer',       'Receive a direct message from a peer; body: {"sender_ip": "...", "message": "..."}'],
        ['POST', '/broadcast-peer',  'Receive a broadcast message from the network; same body format'],
        ['POST', '/local-send',      'UI-triggered; type: broadcast or direct; dispatches to peers asynchronously'],
      ]),

      h3('7.2.2 Non-Blocking Message Dispatch'),
      p('Outgoing messages use asyncio to avoid blocking the server:'),
      bullet('send_p2p_message(target_ip, target_port, message, endpoint) — opens a non-blocking async TCP connection using asyncio.open_connection(), sends an HTTP POST request with a JSON body, and awaits the acknowledgement.'),
      bullet('broadcast_message(message) — builds a list of send_p2p_message() coroutines, one per peer in active_peers, and runs them concurrently with asyncio.gather(). This means all outgoing connections are initiated simultaneously, without blocking each other.'),
      p('The local-send endpoint bridges the synchronous HTTP request (from the browser/UI) to the async dispatch logic by calling loop.run_until_complete().'),

      h2('7.3 Channel Management'),
      p('The specification requires a channel listing UI. In the current implementation the channels are implicit: each peer\'s IP:port pair represents a communication channel. The known_peers list (maintained by the discovery thread) functions as the channel membership list. The /discover endpoint provides the channel listing, and /send-peer and /broadcast-peer provide message submission.'),
      spacer(),
      pageBreak(),

      // ─── 8. MODULE STRUCTURE ─────────────────────────────────────────
      h1('8. Module and File Structure'),
      twoColTable([
        ['daemon/asynaprous.py',  'Decorator-based RESTful router; wraps backend.create_backend()'],
        ['daemon/backend.py',     'TCP server with threading / callback / coroutine modes'],
        ['daemon/proxy.py',       'Reverse proxy with virtual-host routing and round-robin LB'],
        ['daemon/channel.py',     'Channel and ChannelPool for backend connection reuse'],
        ['daemon/httpadapter.py', 'HTTP lifecycle: recv, parse, auth, dispatch, respond'],
        ['daemon/request.py',     'HTTP request parser (RFC 2617 auth, RFC 6265 cookies)'],
        ['daemon/response.py',    'HTTP response builder (static files, JSON, 401, Set-Cookie)'],
        ['daemon/tracker.py',     'PeerRegistry: in-memory peer store with keepalive thread'],
        ['daemon/peer.py',        'Peer client: register, discover, connect, server thread'],
        ['daemon/dictionary.py',  'CaseInsensitiveDict for HTTP header handling'],
        ['daemon/utils.py',       'Auth helpers: generate_session_token, get_auth_from_url'],
        ['apps/sampleapp.py',     'Sample AsynapRous app with /login and /echo routes'],
        ['apps/trackerapp.py',    'Tracker REST API (/register, /discover, /connect, /status)'],
        ['apps/p2papp.py',        'P2P chat app (/send-peer, /broadcast-peer, /local-send)'],
        ['config/proxy.conf',     'Virtual-host routing configuration'],
        ['www/',                  'Static HTML pages (index.html, login.html, form.html)'],
        ['start_proxy.py',        'Entry point: launch proxy server'],
        ['start_backend.py',      'Entry point: launch backend server'],
        ['start_tracker.py',      'Entry point: launch P2P tracker'],
        ['start_p2p.py',          'Entry point: launch P2P peer'],
        ['start_sampleapp.py',    'Entry point: launch sample AsynapRous webapp'],
      ]),
      spacer(),
      pageBreak(),

      // ─── 9. HOW TO RUN ────────────────────────────────────────────────
      h1('9. Running the System'),

      h2('9.1 Start the Tracker'),
      code('python start_tracker.py --server-ip 0.0.0.0 --server-port 9000'),

      h2('9.2 Start the Proxy'),
      code('python start_proxy.py --server-ip 0.0.0.0 --server-port 8080'),

      h2('9.3 Start the Backend'),
      code('# Default threading mode'),
      code('python start_backend.py --server-ip 0.0.0.0 --server-port 9001'),
      code(''),
      code('# Coroutine mode'),
      code('ASYNC_MODE=coroutine python start_backend.py --server-ip 0.0.0.0 --server-port 9001'),

      h2('9.4 Start P2P Peers'),
      code('# Peer A'),
      code('python start_p2p.py --server-ip 0.0.0.0 --server-port 9101 \\'),
      code('                    --tracker-ip 127.0.0.1 --tracker-port 9000'),
      code(''),
      code('# Peer B'),
      code('python start_p2p.py --server-ip 0.0.0.0 --server-port 9102 \\'),
      code('                    --tracker-ip 127.0.0.1 --tracker-port 9000'),

      h2('9.5 Test Authentication'),
      p('Open a browser in incognito mode (to avoid cached credentials) and navigate to http://localhost:8080. The server redirects unauthenticated requests to the login page. Submit admin/admin123 to receive a session cookie and access protected resources.'),
      p('Alternatively, test with curl:'),
      code('# Basic auth'),
      code('curl -u admin:admin123 http://localhost:8080/'),
      code(''),
      code('# Cookie session'),
      code('curl -X POST http://localhost:9001/login \\'),
      code('     -H "Content-Type: application/json" \\'),
      code('     -d \'{"username":"admin","password":"admin123"}\' -c cookies.txt'),
      code('curl http://localhost:9001/ -b cookies.txt'),
      spacer(),
      pageBreak(),

      // ─── 10. DESIGN DECISIONS ─────────────────────────────────────────
      h1('10. Design Decisions and Discussion'),

      h2('10.1 Framework Built from Scratch'),
      p('In accordance with the assignment specification ("we do not encourage framework usages"), the entire server stack is built on Python\'s standard library: socket, threading, selectors, asyncio, and json. No third-party web frameworks (Flask, FastAPI, Django) are used on the server side.'),

      h2('10.2 Protocol Design'),
      p('All inter-daemon communication uses HTTP/1.1 with JSON bodies. This choice allows any HTTP client (browser, curl, REST client) to interact with every component, and aligns with RESTful API conventions. The peer-to-peer messages (send-peer, broadcast-peer) are also JSON over HTTP, making them easy to trace with standard tools.'),

      h2('10.3 Session Token Security'),
      p('Session tokens are generated by utils.generate_session_token(), which combines the username with a random component to produce a unique identifier. In a production system these would be stored in a persistent database and cryptographically signed (e.g., using HMAC). For this assignment an in-memory dict is used for simplicity.'),

      h2('10.4 Non-Blocking in the Peer App'),
      p('The P2P broadcast uses asyncio.gather() so that outgoing HTTP requests to multiple peers are issued concurrently rather than sequentially. This satisfies the non-blocking requirement for peer communication and demonstrates the coroutine mechanism described in Section 2.1 of the specification.'),

      h2('10.5 Connection Pool Lifecycle'),
      p('The ChannelPool in the proxy uses a thread-safe Queue per backend. Channels are marked active/idle rather than discarded after each request, reducing TCP handshake overhead under load. Stale channels (exceeded idle_timeout) are cleaned up lazily, keeping the pool lean.'),
      spacer(),
      pageBreak(),

      // ─── 11. GRADING CHECKLIST ─────────────────────────────────────────
      h1('11. Grading Checklist'),
      twoColTable([
        ['Criterion', 'Implementation Status'],
        ['Authentication — HTTP Basic Auth (RFC 2617/7235)', 'Implemented in Request.prepare_auth() + HttpAdapter._authenticate_basic()'],
        ['Authentication — Cookie Sessions (RFC 6265)', 'Implemented in HttpAdapter._handle_login() + _authenticate_cookie()'],
        ['ChatApp — Client-Server Paradigm', 'PeerRegistry (tracker) + Peer class with HTTP registration/discovery'],
        ['ChatApp — P2P Paradigm', 'p2papp.py with asyncio-based direct/broadcast send'],
        ['Non-Blocking Communication', 'Three modes: threading, callback (selectors), coroutine (asyncio)'],
        ['Protocol Design', 'Custom REST API over HTTP/1.1 with JSON; all routes documented'],
        ['No External Frameworks', 'Standard library only; AsynapRous framework built from scratch'],
        ['PEP 8 / PEP 257 Compliance', 'Docstrings on all public methods; snake_case naming throughout'],
      ]),
      spacer(),
      pageBreak(),

      // ─── 12. CONCLUSION ───────────────────────────────────────────────
      h1('12. Conclusion'),
      p('This assignment successfully demonstrates the major concepts of computer network programming taught in CO3094: the client-server paradigm (proxy, backend, tracker), the peer-to-peer paradigm (direct peer connections via the P2P chat app), and non-blocking network communication (three selectable async modes).'),
      p('By implementing all server logic from Python standard library primitives and designing a custom RESTful protocol for peer interaction, the team gained practical experience in HTTP internals, TCP socket programming, authentication standards, and asynchronous I/O patterns.'),
      p('The modular architecture — with each daemon (proxy, backend, tracker, P2P peer) running as an independent process communicating over well-defined HTTP APIs — also reflects real-world microservice design principles and makes the system straightforward to extend or deploy on separate machines.'),
      spacer(),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/mnt/user-data/outputs/CO3094_Assignment1_Report.docx', buffer);
  console.log('Done: CO3094_Assignment1_Report.docx');
});
