"""Discover local games using launcher metadata and bounded standard locations."""
import os
from pathlib import Path
import re
import sys


def _keyvalues(text):
    # Steam's VDF uses quoted strings, braces and C-style escaping.
    tokens = re.findall(r'"((?:\\.|[^"\\])*)"|([{}])', text)
    values = [(re.sub(r'\\([\\"])', r'\1', word) if not brace else brace) for word, brace in tokens]
    def parse(index):
        out = {}
        while index < len(values) and values[index] != '}':
            key = values[index]; index += 1
            if index >= len(values):
                break
            if values[index] == '{':
                val, index = parse(index + 1)
            else:
                val = values[index]; index += 1
            out[key] = val
        return out, index + (index < len(values) and values[index] == '}')
    return parse(0)[0]


def steam_roots():
    home = Path.home()
    roots = [home / '.local/share/Steam', home / '.steam/steam',
             home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
             home / 'snap/steam/common/.local/share/Steam',
             home / 'Library/Application Support/Steam']
    if sys.platform == 'win32':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                roots.insert(0, Path(winreg.QueryValueEx(key, 'SteamPath')[0]))
        except OSError:
            pass
        for var in ('PROGRAMFILES(X86)', 'PROGRAMFILES'):
            if os.environ.get(var):
                roots.append(Path(os.environ[var]) / 'Steam')
    return roots


def _read(path):
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            return {}
        return _keyvalues(path.read_text(encoding='utf-8-sig', errors='replace'))
    except OSError:
        return {}


def discover_games():
    libraries = {}
    for root in steam_roots():
        if not (root / 'steamapps').is_dir():
            continue
        libraries[str(root.resolve())] = root.resolve()
        config = _read(root / 'steamapps/libraryfolders.vdf').get('libraryfolders', {})
        if isinstance(config, dict):
            for key, value in config.items():
                path = value.get('path') if isinstance(value, dict) else value if key.isdigit() else None
                if path:
                    folder = Path(path).expanduser()
                    if folder.is_absolute() and (folder / 'steamapps').is_dir():
                        libraries[str(folder.resolve())] = folder.resolve()
    games = {}
    for library in libraries.values():
        try:
            manifests = list((library / 'steamapps').glob('appmanifest_*.acf'))
        except OSError:
            continue
        for manifest in manifests:
            fields = _read(manifest).get('AppState', {})
            if not isinstance(fields, dict):
                continue
            name, directory = fields.get('name', ''), fields.get('installdir', '')
            if not isinstance(directory, str) or not directory or directory in ('.', '..') or '/' in directory or '\\' in directory:
                continue
            if not isinstance(name, str) or not name or any(x in name.lower() for x in ('proton', 'steam linux runtime', 'legacy steam runtime', 'steamworks common redistributables')):
                continue
            try:
                if 'StateFlags' in fields and not int(fields['StateFlags']) & 4:
                    continue
            except (ValueError, TypeError):
                continue
            path = library / 'steamapps/common' / directory
            if fields.get('appid') == '340' and (path / 'lostcoast').is_dir():
                path /= 'lostcoast'
            if path.is_dir():
                path = path.resolve()
                games[str(path)] = {'name': name, 'path': str(path), 'appid': fields.get('appid', ''), 'source': 'Steam'}
    from app.core.automatic import direct_engine
    for library in (Path.home() / 'Games', Path.home() / 'Игры'):
        if not library.is_dir():
            continue
        libraries[str(library.resolve())] = library.resolve()
        try:
            children = sorted(library.iterdir(), key=lambda p: p.name.casefold())[:500]
            for path in children:
                if path.name.startswith('.') or '.backup' in path.name.lower() or not path.is_dir():
                    continue
                if direct_engine(path) != 'unknown':
                    resolved = path.resolve()
                    games.setdefault(str(resolved), {'name': path.name, 'path': str(resolved), 'appid': '', 'source': 'Папка игр'})
        except OSError:
            continue
    shortcuts = []
    for library in libraries.values():
        common = library / 'steamapps/common'
        if common.is_dir():
            common = common.resolve()
            count = sum(1 for game in games.values() if game['source'] == 'Steam'
                        and common in Path(game['path']).parents)
            shortcuts.append({'path': str(common), 'name': 'Steam', 'game_count': count})
        elif library.name in ('Games', 'Игры'):
            count = sum(1 for game in games.values() if game['source'] == 'Папка игр'
                        and library in Path(game['path']).parents)
            shortcuts.append({'path': str(library), 'name': 'Папка игр', 'game_count': count})
    shortcuts.sort(key=lambda item: (-item['game_count'], item['path'].casefold()))
    return {'games': sorted(games.values(), key=lambda game: game['name'].casefold()),
            'libraries': [str(path) for path in libraries.values()], 'folder_shortcuts': shortcuts}
