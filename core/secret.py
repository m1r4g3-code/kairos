"""
KAIROS core — secrets kept in Windows Credential Manager, not in files.

    secret.put("KairosCloudbet", value)    store or replace
    secret.get("KairosCloudbet")           -> str or None
    secret.delete("KairosCloudbet")

A secret stored here never touches the repository, `.env`, a log or a prompt.
Off Windows every call is a no-op that returns None/False.

Pure stdlib (ctypes).
"""

from __future__ import annotations

import sys

CRED_TYPE_GENERIC, CRED_PERSIST_LOCAL_MACHINE = 1, 2


def _api():
    import ctypes
    from ctypes import wintypes

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                    ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                    ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_char)), ("Persist", wintypes.DWORD),
                    ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
    adv.CredWriteW.restype = wintypes.BOOL
    adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    adv.CredDeleteW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    return ctypes, adv, CREDENTIAL


def put(name: str, value: str) -> bool:
    if sys.platform != "win32":
        return False
    ctypes, adv, CREDENTIAL = _api()
    blob = value.encode("utf-8")
    buf = ctypes.create_string_buffer(blob, len(blob))
    cred = CREDENTIAL(Type=CRED_TYPE_GENERIC, TargetName=name, CredentialBlobSize=len(blob),
                      CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)),
                      Persist=CRED_PERSIST_LOCAL_MACHINE, UserName="kairos")
    return bool(adv.CredWriteW(ctypes.byref(cred), 0))


def get(name: str) -> str | None:
    if sys.platform != "win32":
        return None
    ctypes, adv, CREDENTIAL = _api()
    ptr = ctypes.POINTER(CREDENTIAL)()
    if not adv.CredReadW(name, CRED_TYPE_GENERIC, 0, ctypes.byref(ptr)):
        return None
    try:
        c = ptr.contents
        return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-8")
    finally:
        adv.CredFree(ptr)


def delete(name: str) -> bool:
    if sys.platform != "win32":
        return False
    _, adv, _ = _api()
    return bool(adv.CredDeleteW(name, CRED_TYPE_GENERIC, 0))
