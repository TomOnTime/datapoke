#!/usr/bin/env python3
"""
Tests for yamlpoke and jsonpoke.
"""

import sys
import json
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml

# Patch argv so argparse doesn't pick up pytest args
import unittest.mock as mock

# ---- Import the modules under test ----
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

HERE = Path(__file__).parent
yp = load_module("yamlpoke", HERE / "yamlpoke.py")
jp = load_module("jsonpoke", HERE / "jsonpoke.py")


# ===========================================================================
# Shared path-parsing tests
# ===========================================================================

def test_parse_simple_path():
    assert yp.parse_path("foo.bar.baz") == ["foo", "bar", "baz"]

def test_parse_index():
    assert yp.parse_path("items[0].name") == ["items", 0, "name"]

def test_parse_quoted():
    assert yp.parse_path('foo."my.key".bar') == ["foo", "my.key", "bar"]

def test_parse_empty():
    assert yp.parse_path("") == []
    assert yp.parse_path(".") == []

def test_segments_round_trip():
    segs = ["foo", "bar", 2, "baz"]
    assert yp.segments_to_path_str(segs) == "foo.bar[2].baz"


# ===========================================================================
# YAML — list mode
# ===========================================================================

SAMPLE_YAML = textwrap.dedent("""\
    server:
      host: localhost
      port: 8080
    database:
      name: mydb
      pool:
        size: 5
    tags:
      - alpha
      - beta
""")

def _yaml_file(content=SAMPLE_YAML):
    f = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False, encoding="utf-8")
    f.write(content)
    f.flush()
    f.close()
    return Path(f.name)

def test_yaml_list():
    fpath = _yaml_file()
    leaves = yp.list_paths(yp.load_yaml(fpath))
    paths = [yp.segments_to_path_str(s) for s, _ in leaves]
    assert "server.host" in paths
    assert "server.port" in paths
    assert "database.pool.size" in paths
    assert "tags[0]" in paths
    assert "tags[1]" in paths
    fpath.unlink()


# ===========================================================================
# YAML — poke mode
# ===========================================================================

def test_yaml_poke_existing_scalar():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "server.port", "9090", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["server"]["port"] == 9090
    fpath.unlink()

def test_yaml_poke_create_new_path():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "server.tls", "true", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["server"]["tls"] == True
    fpath.unlink()

def test_yaml_poke_no_create_skips():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "--no-create", "server.newkey", "hello", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert "newkey" not in data["server"]
    fpath.unlink()

def test_yaml_poke_no_create_updates_existing():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "--no-create", "server.port", "7777", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["server"]["port"] == 7777
    fpath.unlink()

def test_yaml_poke_string_value():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "server.host", "example.com", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["server"]["host"] == "example.com"
    fpath.unlink()

def test_yaml_poke_deep_create():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "new.deep.path", "42", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["new"]["deep"]["path"] == 42
    fpath.unlink()

def test_yaml_poke_list_index():
    fpath = _yaml_file()
    with mock.patch("sys.argv", ["yamlpoke", "poke", "tags[0]", "gamma", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["tags"][0] == "gamma"
    fpath.unlink()


# ===========================================================================
# YAML — update mode (wildcard)
# ===========================================================================

WILDCARD_YAML = textwrap.dedent("""\
    services:
      web:
        port: 80
        enabled: true
      api:
        port: 8080
        enabled: false
      db:
        port: 5432
        enabled: true
""")

def test_yaml_update_wildcard():
    fpath = _yaml_file(WILDCARD_YAML)
    with mock.patch("sys.argv", ["yamlpoke", "update", "services.*", "version", "1.0", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    # YAML parses "1.0" as float
    assert data["services"]["web"]["version"] == 1.0
    assert data["services"]["api"]["version"] == 1.0
    assert data["services"]["db"]["version"] == 1.0
    fpath.unlink()

def test_yaml_update_subpath():
    """update adds a sibling sub-path under the matched container, not inside a scalar."""
    fpath = _yaml_file(WILDCARD_YAML)
    # Match services.* (the service dict itself), then add sub-path "meta.owner"
    with mock.patch("sys.argv", ["yamlpoke", "update", "services.*", "meta.owner", "team-a", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["services"]["web"]["meta"]["owner"] == "team-a"
    assert data["services"]["api"]["meta"]["owner"] == "team-a"
    assert data["services"]["db"]["meta"]["owner"] == "team-a"
    fpath.unlink()

def test_yaml_update_no_match():
    fpath = _yaml_file(WILDCARD_YAML)
    with mock.patch("sys.argv", ["yamlpoke", "update", "nonexistent.*", "foo", "bar", str(fpath)]):
        yp.main()
    # Should not crash, file unchanged
    data = yp.load_yaml(fpath)
    assert "nonexistent" not in data
    fpath.unlink()


# ===========================================================================
# JSON — list mode
# ===========================================================================

SAMPLE_JSON = {
    "server": {"host": "localhost", "port": 8080},
    "database": {"name": "mydb", "pool": {"size": 5}},
    "tags": ["alpha", "beta"]
}

def _json_file(content=None):
    if content is None:
        content = SAMPLE_JSON
    f = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8")
    json.dump(content, f, indent=2)
    f.flush()
    f.close()
    return Path(f.name)

def test_json_list():
    fpath = _json_file()
    leaves = jp.list_paths(jp.load_json(fpath))
    paths = [jp.segments_to_path_str(s) for s, _ in leaves]
    assert "server.host" in paths
    assert "server.port" in paths
    assert "database.pool.size" in paths
    assert "tags[0]" in paths
    fpath.unlink()


# ===========================================================================
# JSON — poke mode
# ===========================================================================

def test_json_poke_int():
    fpath = _json_file()
    with mock.patch("sys.argv", ["jsonpoke", "poke", "server.port", "9090", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert data["server"]["port"] == 9090
    fpath.unlink()

def test_json_poke_bool():
    fpath = _json_file()
    with mock.patch("sys.argv", ["jsonpoke", "poke", "server.tls", "true", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert data["server"]["tls"] == True
    fpath.unlink()

def test_json_poke_null():
    fpath = _json_file()
    with mock.patch("sys.argv", ["jsonpoke", "poke", "database.name", "null", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert data["database"]["name"] is None
    fpath.unlink()

def test_json_poke_no_create():
    fpath = _json_file()
    with mock.patch("sys.argv", ["jsonpoke", "poke", "--no-create", "server.newkey", "hello", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert "newkey" not in data["server"]
    fpath.unlink()

def test_json_poke_create_deep():
    fpath = _json_file()
    with mock.patch("sys.argv", ["jsonpoke", "poke", "new.deep.key", "99", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert data["new"]["deep"]["key"] == 99
    fpath.unlink()

def test_json_poke_preserves_indent():
    fpath = _json_file()
    original_text = fpath.read_text()
    with mock.patch("sys.argv", ["jsonpoke", "poke", "server.port", "1234", str(fpath)]):
        jp.main()
    new_text = fpath.read_text()
    # Should still be indented (2 spaces)
    assert "  " in new_text
    fpath.unlink()


# ===========================================================================
# JSON — update mode (wildcard)
# ===========================================================================

WILDCARD_JSON = {
    "services": {
        "web": {"port": 80, "enabled": True},
        "api": {"port": 8080, "enabled": False},
        "db": {"port": 5432, "enabled": True},
    }
}

def test_json_update_wildcard():
    fpath = _json_file(WILDCARD_JSON)
    with mock.patch("sys.argv", ["jsonpoke", "update", "services.*", "version", '"2.0"', str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert data["services"]["web"]["version"] == "2.0"
    assert data["services"]["api"]["version"] == "2.0"
    assert data["services"]["db"]["version"] == "2.0"
    fpath.unlink()

def test_json_update_no_match():
    fpath = _json_file(WILDCARD_JSON)
    with mock.patch("sys.argv", ["jsonpoke", "update", "nope.*", "x", "1", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert "nope" not in data
    fpath.unlink()


# ===========================================================================
# Coercion tests
# ===========================================================================

def test_yaml_coerce_int():
    assert yp.coerce_value("42") == 42

def test_yaml_coerce_float():
    assert yp.coerce_value("3.14") == 3.14

def test_yaml_coerce_bool_true():
    assert yp.coerce_value("true") == True

def test_yaml_coerce_bool_false():
    assert yp.coerce_value("false") == False

def test_yaml_coerce_null():
    assert yp.coerce_value("null") is None

def test_yaml_coerce_string():
    assert yp.coerce_value("hello world") == "hello world"

def test_json_coerce_int():
    assert jp.coerce_value("42") == 42

def test_json_coerce_bool():
    assert jp.coerce_value("true") == True

def test_json_coerce_null():
    assert jp.coerce_value("null") is None

def test_json_coerce_string():
    assert jp.coerce_value("not-json!!") == "not-json!!"


# ===========================================================================
# Empty-subpath update (replace matched node directly)
# ===========================================================================

def test_yaml_update_empty_subpath_replaces_scalar():
    """update with no subpath (empty string) replaces the matched node itself."""
    fpath = _yaml_file(WILDCARD_YAML)
    with mock.patch("sys.argv", ["yamlpoke", "update", "services.*.enabled", ".", "false", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["services"]["web"]["enabled"] == False
    assert data["services"]["api"]["enabled"] == False
    assert data["services"]["db"]["enabled"] == False
    fpath.unlink()

def test_yaml_update_dot_subpath_replaces_scalar():
    """update with '.' as subpath is equivalent to empty subpath."""
    fpath = _yaml_file(WILDCARD_YAML)
    with mock.patch("sys.argv", ["yamlpoke", "update", "services.*.port", ".", "0", str(fpath)]):
        yp.main()
    data = yp.load_yaml(fpath)
    assert data["services"]["web"]["port"] == 0
    assert data["services"]["api"]["port"] == 0
    fpath.unlink()

def test_json_update_empty_subpath_replaces_scalar():
    fpath = _json_file(WILDCARD_JSON)
    with mock.patch("sys.argv", ["jsonpoke", "update", "services.*.enabled", ".", "true", str(fpath)]):
        jp.main()
    data = jp.load_json(fpath)
    assert data["services"]["web"]["enabled"] == True
    assert data["services"]["api"]["enabled"] == True
    fpath.unlink()

# ===========================================================================
# Run all tests
# ===========================================================================

if __name__ == "__main__":
    import traceback
    tests = [(name, obj) for name, obj in sorted(globals().items()) if name.startswith("test_")]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed+failed} tests")
    sys.exit(0 if failed == 0 else 1)
