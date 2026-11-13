"""Update an existing Steam Workshop item through the running, signed-in Steam client.

Calls the Steamworks flat API in a game's own steam_api library, the route in-game uploaders use. It never signs in,
so the desktop client stays connected. SteamCMD signs in as a second client and replaces the desktop session.

Updates only: it cannot create an item, add gallery images or post comments. Only the fields passed are changed.
Requires the Steam client to be running and online as an account allowed to edit the item. While it runs, Steam shows
that account as playing the game. Uses the Python standard library only.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import re
import sys
import time
from pathlib import Path

VISIBILITY = {"public": 0, "friends": 1, "private": 2, "unlisted": 3}
SUBMIT_RESULT_CALLBACK = 3404  # k_iSteamUGCCallbacks + 4, SubmitItemUpdateResult_t
STATUS = {0: "invalid", 1: "preparing config", 2: "preparing content", 3: "uploading content", 4: "uploading preview", 5: "committing"}
# The EResult values a Workshop update commonly returns; the rest are printed as numbers.
RESULTS = {
    1: "OK", 2: "failure", 8: "invalid parameter", 9: "file not found", 15: "access denied (not the item's owner or a contributor)",
    16: "timeout", 17: "banned", 21: "not logged on (the Steam client is offline)", 24: "insufficient privilege",
    25: "limit exceeded", 33: "locked",
}


class StringArray(ctypes.Structure):  # SteamParamStringArray_t
    _pack_ = 8
    _fields_ = [("strings", ctypes.POINTER(ctypes.c_char_p)), ("count", ctypes.c_int32)]


class SubmitResult(ctypes.Structure):  # SubmitItemUpdateResult_t
    _pack_ = 8
    _fields_ = [("result", ctypes.c_int32), ("needs_legal_agreement", ctypes.c_bool), ("item", ctypes.c_uint64)]


def interface_accessor(library_bytes: bytes, name: str) -> str:
    """The versioned accessor a library exports, for example SteamAPI_SteamUGC_v021. Versions differ between games."""
    found = sorted(set(re.findall(rb"SteamAPI_%s_v\d+" % name.encode(), library_bytes)))
    if not found:
        raise SystemExit(f"{name} accessor not found in the Steam API library; it may predate the flat API")
    return found[-1].decode()


def parse_tags(text: str) -> list[str]:
    tags = [tag.strip() for tag in text.split(",")]
    if any(not tag for tag in tags):
        raise SystemExit("--tags has an empty entry")
    return tags


def read_text(path: str | None) -> str | None:
    return None if path is None else Path(path).read_text(encoding="utf-8").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--steam-api", required=True, help="path to the game's steam_api64.dll (or libsteam_api.so / .dylib)")
    parser.add_argument("--app-id", required=True, type=int, help="the game's App ID")
    parser.add_argument("--item-id", required=True, type=int, help="published file ID of the existing item")
    parser.add_argument("--content", help="folder to upload as the item's content")
    parser.add_argument("--preview", help="main preview image")
    parser.add_argument("--title")
    parser.add_argument("--description-file", help="UTF-8 file holding the description (Steam BBCode)")
    parser.add_argument("--tags", help="comma-separated tags; replaces every existing tag")
    parser.add_argument("--visibility", choices=sorted(VISIBILITY))
    parser.add_argument("--changenote", help="change note text")
    parser.add_argument("--changenote-file", help="UTF-8 file holding the change note")
    parser.add_argument("--expect-steam-id", type=int, help="refuse unless the client is signed in as this SteamID64")
    parser.add_argument("--timeout", type=float, default=900, help="seconds to wait for Steam to finish (default 900)")
    parser.add_argument("--dry-run", action="store_true", help="check the inputs and the client connection, then stop without submitting")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.changenote and args.changenote_file:
        raise SystemExit("pass --changenote or --changenote-file, not both")
    note = args.changenote if args.changenote is not None else read_text(args.changenote_file)
    description = read_text(args.description_file)
    tags = parse_tags(args.tags) if args.tags is not None else None
    content = Path(args.content).resolve() if args.content else None
    preview = Path(args.preview).resolve() if args.preview else None
    if content is not None and not content.is_dir():
        raise SystemExit(f"content folder not found: {content}")
    if preview is not None and not preview.is_file():
        raise SystemExit(f"preview file not found: {preview}")
    if not any(value is not None for value in (content, preview, args.title, description, tags, args.visibility)):
        raise SystemExit("nothing to update: pass at least one of --content, --preview, --title, --description-file, --tags, --visibility")

    library_path = Path(args.steam_api).resolve()
    if not library_path.is_file():
        raise SystemExit(f"Steam API library not found: {library_path}")
    library_bytes = library_path.read_bytes()
    # The library reads the App ID from the environment, so no steam_appid.txt has to be written anywhere.
    os.environ["SteamAppId"] = os.environ["SteamGameId"] = str(args.app_id)
    api = ctypes.CDLL(str(library_path))

    def function(name, restype, *argtypes):
        fn = getattr(api, name)
        fn.restype, fn.argtypes = restype, list(argtypes)
        return fn

    pointer, handle, text = ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p
    if b"SteamAPI_InitFlat" in library_bytes:
        error = ctypes.create_string_buffer(1024)
        if function("SteamAPI_InitFlat", ctypes.c_int, ctypes.c_char_p)(error) != 0:
            raise SystemExit("Steam did not initialise: " + error.value.decode("utf-8", "replace") + " (is the Steam client running?)")
    elif not function("SteamAPI_Init", ctypes.c_bool)():
        raise SystemExit("Steam did not initialise (is the Steam client running?)")

    run_callbacks = function("SteamAPI_RunCallbacks", None)
    try:
        user = function(interface_accessor(library_bytes, "SteamUser"), pointer)()
        utils = function(interface_accessor(library_bytes, "SteamUtils"), pointer)()
        ugc = function(interface_accessor(library_bytes, "SteamUGC"), pointer)()
        steam_id = function("SteamAPI_ISteamUser_GetSteamID", ctypes.c_uint64, pointer)(user)
        print(f"Steam client signed in as {steam_id}")
        if args.expect_steam_id is not None and steam_id != args.expect_steam_id:
            print("REFUSED: that is not the expected account; nothing sent")
            return 3

        logged_on = function("SteamAPI_ISteamUser_BLoggedOn", ctypes.c_bool, pointer)
        deadline = time.monotonic() + 15
        while not logged_on(user) and time.monotonic() < deadline:
            run_callbacks()
            time.sleep(0.1)
        if not logged_on(user):
            print("REFUSED: the Steam client is offline. Reconnect it (Steam menu, Go Online) and run again; nothing sent")
            return 3
        if args.dry_run:
            print("Dry run: inputs and connection are fine; nothing sent")
            return 0

        update = function("SteamAPI_ISteamUGC_StartItemUpdate", handle, pointer, ctypes.c_uint32, ctypes.c_uint64)(ugc, args.app_id, args.item_id)

        def set_text(name: str, value: str | None, label: str) -> None:
            if value is not None and not function("SteamAPI_ISteamUGC_" + name, ctypes.c_bool, pointer, handle, text)(ugc, update, value.encode("utf-8")):
                raise SystemExit(f"Steam rejected the {label}; nothing sent")

        set_text("SetItemTitle", args.title, "title")
        set_text("SetItemDescription", description, "description")
        set_text("SetItemContent", str(content) if content else None, "content folder")
        set_text("SetItemPreview", str(preview) if preview else None, "preview file")
        if args.visibility is not None and not function("SteamAPI_ISteamUGC_SetItemVisibility", ctypes.c_bool, pointer, handle, ctypes.c_int)(ugc, update, VISIBILITY[args.visibility]):
            raise SystemExit("Steam rejected the visibility; nothing sent")
        if tags is not None:
            strings = (ctypes.c_char_p * len(tags))(*[tag.encode("utf-8") for tag in tags])
            array = StringArray(ctypes.cast(strings, ctypes.POINTER(ctypes.c_char_p)), len(tags))
            # Older libraries take three arguments; the extra one is ignored there.
            set_tags = function("SteamAPI_ISteamUGC_SetItemTags", ctypes.c_bool, pointer, handle, ctypes.POINTER(StringArray), ctypes.c_bool)
            if not set_tags(ugc, update, ctypes.byref(array), False):
                raise SystemExit("Steam rejected the tags; nothing sent")

        call = function("SteamAPI_ISteamUGC_SubmitItemUpdate", ctypes.c_uint64, pointer, handle, text)(
            ugc, update, note.encode("utf-8") if note else None)
        completed = function("SteamAPI_ISteamUtils_IsAPICallCompleted", ctypes.c_bool, pointer, ctypes.c_uint64, ctypes.POINTER(ctypes.c_bool))
        progress = function("SteamAPI_ISteamUGC_GetItemUpdateProgress", ctypes.c_int, pointer, handle, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64))
        failed, last = ctypes.c_bool(False), None
        deadline = time.monotonic() + args.timeout
        while not completed(utils, call, ctypes.byref(failed)):
            if time.monotonic() > deadline:
                print("UNKNOWN: timed out waiting for Steam. Check the live item before retrying")
                return 2
            done, total = ctypes.c_uint64(0), ctypes.c_uint64(0)
            status = progress(ugc, update, ctypes.byref(done), ctypes.byref(total))
            if status != last and status in STATUS and status != 0:
                print("  " + STATUS[status])
                last = status
            run_callbacks()
            time.sleep(0.1)

        result = SubmitResult()
        get_result = function("SteamAPI_ISteamUtils_GetAPICallResult", ctypes.c_bool, pointer, ctypes.c_uint64, pointer, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool))
        if not get_result(utils, call, ctypes.byref(result), ctypes.sizeof(result), SUBMIT_RESULT_CALLBACK, ctypes.byref(failed)) or failed.value:
            print("UNKNOWN: Steam returned no result. Check the live item before retrying")
            return 2
        if result.needs_legal_agreement:
            print("Steam says this account must accept the Workshop legal agreement before the item is visible")
        if result.result != 1:
            print(f"FAILED: Steam result {result.result}: {RESULTS.get(result.result, 'see EResult in the Steamworks documentation')}")
            return 1
        print(f"OK: item {result.item} updated. Verify the live item; this result alone is not proof of each field")
        return 0
    finally:
        function("SteamAPI_Shutdown", None)()


if __name__ == "__main__":
    sys.exit(main())
