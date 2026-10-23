"""The two API keys of the study in Windows Credential Manager, and the launcher logic around them.

Binding rules (the lead developer and the Coordinator, 2026-10-20):
 * the keys are GENERIC CREDENTIALS under stable names that do not depend on the repository path;
 * the launcher supplies ANTHROPIC_API_KEY and OPENAI_API_KEY only to the harness child process, and changes no global or user environment
   variable, no shell profile and no coding-assistant authentication;
 * a missing credential is looked up first and prompted for only in an interactive terminal, with hidden input asked twice;
   in any non-interactive context (an agent session, a pipe) the launcher STOPS and says so, so a worker session never receives a key;
 * only a light sanity check of the key's shape; NO API call to test a key;
 * nothing persists outside Credential Manager: no file, no log, no argument, no shell history;
 * limitation: Credential Manager protects storage; it does not restrict retrieval to this application.
Windows is implemented and tested (through a fake store). Other operating systems' stores are deferred; explicit process-level environment
injection remains available everywhere.
"""
import ctypes
import getpass
import re
import sys

CREDENTIALS = {
    'anthropic': {'target': 'agent-study/anthropic-api-key', 'variable': 'ANTHROPIC_API_KEY', 'prefix': 'sk-ant-'},
    'openai': {'target': 'agent-study/openai-api-key', 'variable': 'OPENAI_API_KEY', 'prefix': 'sk-'},
}
USER_NAME = 'agent-study'


class CredentialError(Exception):
    pass


class NotInteractiveError(CredentialError):
    pass


def sanity_problem(vendor, value):
    """A short reason why `value` cannot be a key of the vendor, else None. A shape check only; the key is never sent anywhere."""
    prefix = CREDENTIALS[vendor]['prefix']
    if not value or re.search(r'\s', value):
        return 'it is empty or contains whitespace'
    if not value.startswith(prefix):
        return 'it does not start with %s' % prefix
    if len(value) < 20:
        return 'it is too short for a key'
    return None


class WindowsCredentialStore:
    """Generic credentials through CredReadW / CredWriteW (advapi32), no third-party package."""

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    def __init__(self):
        if sys.platform != 'win32':
            raise CredentialError('The Windows Credential Manager store is implemented for Windows only; on another operating system inject '
                                  'ANTHROPIC_API_KEY and OPENAI_API_KEY into the harness process yourself.')
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD), ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
                        ('LastWritten', FILETIME), ('CredentialBlobSize', wintypes.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
                        ('Persist', wintypes.DWORD), ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
                        ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]

        self._cred = CREDENTIAL
        self._api = ctypes.WinDLL('advapi32', use_last_error=True)
        self._api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        self._api.CredReadW.restype = wintypes.BOOL
        self._api.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        self._api.CredWriteW.restype = wintypes.BOOL
        self._api.CredFree.argtypes = [ctypes.c_void_p]

    def read(self, target):
        pointer = ctypes.POINTER(self._cred)()
        if not self._api.CredReadW(target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == 1168:  # ERROR_NOT_FOUND
                return None
            raise CredentialError('Credential Manager could not read %s (Windows error %d)' % (target, error))
        try:
            blob = ctypes.string_at(pointer.contents.CredentialBlob, pointer.contents.CredentialBlobSize)
            return blob.decode('utf-16-le')
        finally:
            self._api.CredFree(pointer)

    def write(self, target, value):
        blob = value.encode('utf-16-le')
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = self._cred()
        cred.Type, cred.TargetName, cred.UserName = self.CRED_TYPE_GENERIC, target, USER_NAME
        cred.CredentialBlobSize, cred.CredentialBlob, cred.Persist = len(blob), buffer, self.CRED_PERSIST_LOCAL_MACHINE
        if not self._api.CredWriteW(ctypes.byref(cred), 0):
            raise CredentialError('Credential Manager could not store %s (Windows error %d)' % (target, ctypes.get_last_error()))


class MemoryCredentialStore:
    """A fake store for tests."""

    def __init__(self, values=None):
        self.values = dict(values or {})

    def read(self, target):
        return self.values.get(target)

    def write(self, target, value):
        self.values[target] = value


def is_interactive(stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    return bool(stdin and stdout and stdin.isatty() and stdout.isatty())


def check(store, vendors=tuple(CREDENTIALS)):
    """{vendor: True/False}: present or missing. Never a value."""
    return {vendor: bool(store.read(CREDENTIALS[vendor]['target'])) for vendor in vendors}


def prompt_and_store(store, vendor, interactive, ask=getpass.getpass, out=print):
    """Ask for one key with hidden input, twice, check its shape and store it. Refuses outside an interactive terminal."""
    info = CREDENTIALS[vendor]
    if not interactive:
        raise NotInteractiveError('credential %s is missing: run the launcher yourself in a terminal (%s --set-credentials); '
                                  'a worker session never receives a key' % (info['target'], 'launcher.py'))
    first = ask('%s (input hidden): ' % info['variable'])
    problem = sanity_problem(vendor, first)
    if problem:
        raise CredentialError('That does not look like a %s key: %s. Nothing was stored.' % (vendor, problem))
    if ask('Again to confirm (input hidden): ') != first:
        raise CredentialError('The two entries differ. Nothing was stored.')
    store.write(info['target'], first)
    out('Stored %s in Windows Credential Manager.' % info['target'])


def load_for_child(store, vendors, interactive, ask=getpass.getpass, out=print):
    """The environment entries for the harness child: {variable: key}. Prompts for the missing ones in an interactive terminal only."""
    entries = {}
    for vendor in vendors:
        info = CREDENTIALS[vendor]
        value = store.read(info['target'])
        if not value:
            out('%s: missing' % info['target'])
            prompt_and_store(store, vendor, interactive, ask=ask, out=out)
            value = store.read(info['target'])
        problem = sanity_problem(vendor, value)
        if problem:
            raise CredentialError('The stored credential %s does not look like a key (%s): run the launcher with --set-credentials.'
                                  % (info['target'], problem))
        entries[info['variable']] = value
    return entries
