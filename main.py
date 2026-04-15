import asyncio
import json
import os
import socket
import sys
import threading
import time
import traceback
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from utils.network_tools import get_default_interface_ipv4
    from utils.packet_templates import ClientHelloMaker
except ModuleNotFoundError:
    from network_tools import get_default_interface_ipv4
    from packet_templates import ClientHelloMaker

from fake_tcp import FakeInjectiveConnection, FakeTcpInjector


def get_exe_dir() -> str:
    """Return the directory where the executable or script is located."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def configure_keepalive(sock: socket.socket) -> None:
    sock.setblocking(False)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 11)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)


def build_windivert_filter(interface_ipv4: str, connect_ip: str, handshake_only: bool) -> str:
    addr_filter = (
        "("
        + "(ip.SrcAddr == " + interface_ipv4 + " and ip.DstAddr == " + connect_ip + ")"
        + " or "
        + "(ip.SrcAddr == " + connect_ip + " and ip.DstAddr == " + interface_ipv4 + ")"
        + ")"
    )
    if handshake_only:
        return (
            "tcp and tcp.PayloadLength == 0 and "
            + addr_filter
            + " and (tcp.Syn or tcp.Ack or tcp.Rst or tcp.Fin)"
        )
    return "tcp and " + addr_filter


config_path = os.path.join(get_exe_dir(), "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

LISTEN_HOST = config["LISTEN_HOST"]
LISTEN_PORT = config["LISTEN_PORT"]
FAKE_SNI = config["FAKE_SNI"].encode()
CONNECT_IP = config["CONNECT_IP"]
CONNECT_PORT = config["CONNECT_PORT"]
INTERFACE_IPV4 = get_default_interface_ipv4(CONNECT_IP)
DATA_MODE = "tls"
BYPASS_METHOD = "wrong_seq"

DEBUG = bool(config.get("DEBUG", False))
HANDLE_LIMIT = int(config.get("HANDLE_LIMIT", 128))
ACCEPT_BACKLOG = int(config.get("ACCEPT_BACKLOG", max(HANDLE_LIMIT * 2, 128)))
CONNECT_TIMEOUT = float(config.get("CONNECT_TIMEOUT", 5.0))
HANDSHAKE_TIMEOUT = float(config.get("HANDSHAKE_TIMEOUT", 2.0))
RESOURCE_PRESSURE_BACKOFF = float(config.get("RESOURCE_PRESSURE_BACKOFF", 0.5))
FAKE_SEND_WORKERS = int(config.get("FAKE_SEND_WORKERS", 2))
NARROW_WINDIVERT_FILTER = bool(config.get("NARROW_WINDIVERT_FILTER", True))

fake_injective_connections: dict[tuple, FakeInjectiveConnection] = {}
fake_injective_connections_lock = threading.Lock()
active_handle_tasks: set[asyncio.Task] = set()
handle_semaphore = asyncio.Semaphore(HANDLE_LIMIT)
resource_pressure_until = 0.0


def log_debug(*args) -> None:
    if DEBUG:
        print(*args)


def mark_resource_pressure(seconds: float = RESOURCE_PRESSURE_BACKOFF) -> None:
    global resource_pressure_until
    until = time.monotonic() + max(0.0, seconds)
    if until > resource_pressure_until:
        resource_pressure_until = until


async def maybe_backoff_for_resource_pressure() -> None:
    delay = resource_pressure_until - time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)


def register_fake_connection(connection: FakeInjectiveConnection) -> None:
    with fake_injective_connections_lock:
        fake_injective_connections[connection.id] = connection


def unregister_fake_connection(connection: FakeInjectiveConnection) -> None:
    with fake_injective_connections_lock:
        fake_injective_connections.pop(connection.id, None)


def shutdown_socket(sock: Optional[socket.socket], how: int) -> None:
    if sock is None:
        return
    try:
        fileno = sock.fileno()
    except OSError:
        return
    if fileno == -1:
        return

    try:
        sock.shutdown(how)
    except OSError:
        pass


async def close_socket(sock: Optional[socket.socket]) -> None:
    if sock is None:
        return

    shutdown_socket(sock, socket.SHUT_RDWR)

    try:
        sock.close()
    except OSError:
        pass


async def relay_main_loop(
    read_sock: socket.socket,
    write_sock: socket.socket,
    first_prefix_data: bytes = b"",
) -> str:
    loop = asyncio.get_running_loop()

    try:
        if first_prefix_data:
            await loop.sock_sendall(write_sock, first_prefix_data)

        while True:
            data = await loop.sock_recv(read_sock, 65575)
            if not data:
                return "eof"

            await loop.sock_sendall(write_sock, data)

    except asyncio.CancelledError:
        raise
    except OSError as e:
        if getattr(e, "winerror", None) == 10055:
            mark_resource_pressure()
        return "socket_error"
    except ConnectionError:
        return "socket_error"


async def relay_bidirectional(incoming_sock: socket.socket, outgoing_sock: socket.socket) -> None:
    client_to_server = asyncio.create_task(relay_main_loop(incoming_sock, outgoing_sock))
    server_to_client = asyncio.create_task(relay_main_loop(outgoing_sock, incoming_sock))

    task_to_peer_write = {
        client_to_server: outgoing_sock,
        server_to_client: incoming_sock,
    }

    pending = {client_to_server, server_to_client}

    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                exc = task.exception()
                if exc is not None:
                    for other in pending:
                        other.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    raise exc

                result = task.result()

                if result == "eof":
                    shutdown_socket(task_to_peer_write[task], socket.SHUT_WR)
                    continue

                if result == "socket_error":
                    for other in pending:
                        other.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    return
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


async def handle(incoming_sock: socket.socket, incoming_remote_addr) -> None:
    outgoing_sock = None
    fake_injective_conn = None

    try:
        await maybe_backoff_for_resource_pressure()
        loop = asyncio.get_running_loop()

        if DATA_MODE == "tls":
            fake_data = ClientHelloMaker.get_client_hello_with(
                os.urandom(32),
                os.urandom(32),
                FAKE_SNI,
                os.urandom(32),
            )
        else:
            sys.exit("impossible mode!")

        outgoing_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        configure_keepalive(outgoing_sock)
        outgoing_sock.bind((INTERFACE_IPV4, 0))

        src_port = outgoing_sock.getsockname()[1]
        fake_injective_conn = FakeInjectiveConnection(
            outgoing_sock,
            INTERFACE_IPV4,
            CONNECT_IP,
            src_port,
            CONNECT_PORT,
            fake_data,
            BYPASS_METHOD,
            incoming_sock,
        )
        register_fake_connection(fake_injective_conn)

        try:
            await asyncio.wait_for(loop.sock_connect(outgoing_sock, (CONNECT_IP, CONNECT_PORT)), CONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            log_debug("connect timeout:", incoming_remote_addr)
            return
        except OSError as e:
            if getattr(e, "winerror", None) == 10055:
                mark_resource_pressure()
            log_debug("connect socket error:", repr(e))
            return

        if BYPASS_METHOD == "wrong_seq":
            try:
                await asyncio.wait_for(fake_injective_conn.t2a_event.wait(), HANDSHAKE_TIMEOUT)
            except asyncio.TimeoutError:
                log_debug("handshake timeout:", incoming_remote_addr)
                return

            if fake_injective_conn.t2a_msg == "unexpected_close":
                return
            if fake_injective_conn.t2a_msg != "fake_data_ack_recv":
                sys.exit("impossible t2a msg!")
        else:
            sys.exit("unknown bypass method!")

        fake_injective_conn.monitor = False
        unregister_fake_connection(fake_injective_conn)

        await relay_bidirectional(incoming_sock, outgoing_sock)

    except asyncio.CancelledError:
        raise
    except OSError as e:
        if getattr(e, "winerror", None) == 10055:
            mark_resource_pressure()
        print("handle socket error:", e)
    except Exception:
        traceback.print_exc()
    finally:
        if fake_injective_conn is not None:
            fake_injective_conn.monitor = False
            unregister_fake_connection(fake_injective_conn)

        await close_socket(outgoing_sock)
        await close_socket(incoming_sock)


async def handle_wrapper(incoming_sock: socket.socket, incoming_remote_addr) -> None:
    try:
        await handle(incoming_sock, incoming_remote_addr)
    finally:
        handle_semaphore.release()


def _on_handle_task_done(task: asyncio.Task) -> None:
    active_handle_tasks.discard(task)
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        print("handle task failed:", repr(exc))


async def main() -> None:
    if not INTERFACE_IPV4:
        sys.exit("no interface ipv4 found for CONNECT_IP")

    mother_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mother_sock.setblocking(False)
    mother_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    mother_sock.bind((LISTEN_HOST, LISTEN_PORT))
    mother_sock.listen(ACCEPT_BACKLOG)

    loop = asyncio.get_running_loop()
    try:
        while True:
            await maybe_backoff_for_resource_pressure()
            await handle_semaphore.acquire()
            try:
                incoming_sock, addr = await loop.sock_accept(mother_sock)
            except Exception:
                handle_semaphore.release()
                raise

            configure_keepalive(incoming_sock)

            task = asyncio.create_task(handle_wrapper(incoming_sock, addr))
            active_handle_tasks.add(task)
            task.add_done_callback(_on_handle_task_done)
    finally:
        for task in list(active_handle_tasks):
            task.cancel()
        if active_handle_tasks:
            await asyncio.gather(*active_handle_tasks, return_exceptions=True)
        await close_socket(mother_sock)


if __name__ == "__main__":
    w_filter = build_windivert_filter(INTERFACE_IPV4, CONNECT_IP, NARROW_WINDIVERT_FILTER)
    fake_tcp_injector = FakeTcpInjector(
        w_filter,
        fake_injective_connections,
        fake_injective_connections_lock,
        debug=DEBUG,
        worker_count=FAKE_SEND_WORKERS,
    )
    threading.Thread(target=fake_tcp_injector.run, args=(), daemon=True).start()
    print("هشن شومافر تیامح دینکیم هدافتسا دازآ تنرتنیا هب یسرتسد یارب همانرب نیا زا رگا")
    print("دراد امش تیامح هب زاین هک مراد رظن رد دازآ تنرتنیا هب ناریا مدرم مامت یسرتسد یارب یدایز یاه همانرب و اه هژورپ")
    print()
    print("USDT (BEP20): 0x76a768B53Ca77B43086946315f0BDF21156bF424\n")
    print("@patterniha")
    print(
        "HANDLE_LIMIT=", HANDLE_LIMIT,
        "ACCEPT_BACKLOG=", ACCEPT_BACKLOG,
        "WORKERS=", FAKE_SEND_WORKERS,
        "NARROW_FILTER=", NARROW_WINDIVERT_FILTER,
    )
    asyncio.run(main())
