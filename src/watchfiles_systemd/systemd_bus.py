import asyncio
from typing import Any, Iterable, Optional

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus


SYSTEMD_DEST = "org.freedesktop.systemd1"
SYSTEMD_PATH = "/org/freedesktop/systemd1"
IFACE_MANAGER = "org.freedesktop.systemd1.Manager"
IFACE_PROPERTIES = "org.freedesktop.DBus.Properties"
IFACE_SERVICE = "org.freedesktop.systemd1.Service"


async def connect_user_bus() -> MessageBus:
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    return bus


async def get_manager(bus: MessageBus):
    intro = await bus.introspect(SYSTEMD_DEST, SYSTEMD_PATH)
    obj = bus.get_proxy_object(SYSTEMD_DEST, SYSTEMD_PATH, intro)
    return obj.get_interface(IFACE_MANAGER)


async def start_transient(
    bus: MessageBus,
    name: str,
    properties: list[tuple[str, Variant]],
    aux: Optional[list[tuple[str, list[tuple[str, Variant]]]]] = None,
):
    mgr = await get_manager(bus)
    mode = "fail"
    if aux is None:
        aux = []
    # StartTransientUnit returns object path to job; we don't use it here
    return await mgr.call_start_transient_unit(name, mode, properties, aux)


async def get_unit_path(bus: MessageBus, unit_name: str) -> Optional[str]:
    mgr = await get_manager(bus)
    try:
        path = await mgr.call_get_unit(unit_name)
        return path
    except Exception:
        return None


async def list_units(bus: MessageBus) -> list[dict[str, Any]]:
    mgr = await get_manager(bus)
    rows = await mgr.call_list_units()
    # According to docs, each row is a tuple of many fields; we map minimal ones we need
    result = []
    for row in rows:
        # name, description, load_state, active_state, sub_state, following, unit_path, job_id, job_type, job_path
        # dbus-next flattens to list/tuple indices
        name = row[0]
        description = row[1]
        load_state = row[2]
        active_state = row[3]
        sub_state = row[4]
        following = row[5]
        unit_path = row[6]
        result.append(
            {
                "Name": name,
                "Description": description,
                "LoadState": load_state,
                "ActiveState": active_state,
                "SubState": sub_state,
                "Following": following,
                "Path": unit_path,
            }
        )
    return result


async def get_main_pid(bus: MessageBus, unit_path: str) -> int:
    intro = await bus.introspect(SYSTEMD_DEST, unit_path)
    obj = bus.get_proxy_object(SYSTEMD_DEST, unit_path, intro)
    props = obj.get_interface(IFACE_PROPERTIES)
    pid = await props.call_get(IFACE_SERVICE, "MainPID")
    # dbus-next Variant from call_get
    if isinstance(pid, Variant):
        return int(pid.value)
    return int(pid)


async def get_unit_status(bus: MessageBus, unit_path: str) -> dict[str, Any]:
    """Fetch a snapshot of key Unit/Service properties.

    Returns a dict including:
      - ActiveState, SubState (Unit)
      - MainPID, NRestarts, Result (Service) when available
      - ActiveEnterTimestamp (Unit) when available
    """
    intro = await bus.introspect(SYSTEMD_DEST, unit_path)
    obj = bus.get_proxy_object(SYSTEMD_DEST, unit_path, intro)
    props = obj.get_interface(IFACE_PROPERTIES)
    def _val(v):
        return v.value if isinstance(v, Variant) else v
    st: dict[str, Any] = {}
    # Unit-level
    try:
        st["ActiveState"] = _val(await props.call_get("org.freedesktop.systemd1.Unit", "ActiveState"))
    except Exception:
        st["ActiveState"] = "unknown"
    try:
        st["SubState"] = _val(await props.call_get("org.freedesktop.systemd1.Unit", "SubState"))
    except Exception:
        st["SubState"] = "unknown"
    try:
        ts = _val(await props.call_get("org.freedesktop.systemd1.Unit", "ActiveEnterTimestamp"))
        # Timestamp is in microseconds since the epoch
        try:
            st["ActiveEnterTimestamp"] = int(ts)
        except Exception:
            pass
    except Exception:
        pass

    # Service-level
    try:
        pid = _val(await props.call_get(IFACE_SERVICE, "MainPID"))
        try:
            pid = int(pid)
        except Exception:
            pid = 0
        st["MainPID"] = pid
    except Exception:
        st["MainPID"] = 0
    # WorkingDirectory (helpful for dashboards)
    try:
        wd = _val(await props.call_get(IFACE_SERVICE, "WorkingDirectory"))
        if isinstance(wd, str) and wd:
            st["WorkingDirectory"] = wd
    except Exception:
        # optional, ignore if missing
        pass
    for key in ("NRestarts", "Result", "ExecMainStatus", "ExecMainCode"):
        try:
            st[key] = _val(await props.call_get(IFACE_SERVICE, key))
        except Exception:
            # optional, ignore if not present on this systemd
            pass
    return st


async def stop_unit(bus: MessageBus, unit_name: str, mode: str = "fail"):
    mgr = await get_manager(bus)
    return await mgr.call_stop_unit(unit_name, mode)


async def start_unit(bus: MessageBus, unit_name: str, mode: str = "replace"):
    mgr = await get_manager(bus)
    return await mgr.call_start_unit(unit_name, mode)


async def restart_unit(bus: MessageBus, unit_name: str, mode: str = "replace"):
    mgr = await get_manager(bus)
    return await mgr.call_restart_unit(unit_name, mode)


async def reset_failed_unit(bus: MessageBus, unit_name: str):
    mgr = await get_manager(bus)
    try:
        await mgr.call_reset_failed_unit(unit_name)
    except Exception:
        # Some versions only expose ResetFailed (global); ignore
        pass


def build_execstart_variant(argv: Iterable[str]):
    """Build Variant for ExecStart: a(sasb)

    argv[0] should be an absolute or resolvable executable.
    """
    args = list(argv)
    if not args:
        raise ValueError("empty argv for ExecStart")
    arr = [[args[0], args, False]]
    return Variant("a(sasb)", arr)
