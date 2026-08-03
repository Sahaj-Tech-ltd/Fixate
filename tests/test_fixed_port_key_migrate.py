"""
Verification: find_free_port is now used and PORT is dynamic (BUG-M1 FIXED).

After the fix, backend_entry.py:
- Generates SECRET_KEY dynamically (not hardcoded)
- Uses find_free_port() to pick an available port
- Auto-migrates on startup
"""
import os


class TestFixedPortAndKeyBehavior:
    """Verify that BUG-H1, BUG-H2, and BUG-M1 are all resolved."""

    def test_secret_key_is_generated_not_hardcoded(self):
        """The old hardcoded 'fixate-desktop-dev-key-change-in-build' is gone."""
        entry_path = os.path.join(
            os.path.dirname(__file__), '..', 'desktop', 'backend_entry.py'
        )
        with open(entry_path) as f:
            source = f.read()

        assert 'fixate-desktop-dev-key-change-in-build' not in source, \
            "SECRET_KEY is no longer hardcoded — generated via secrets.token_urlsafe()"
        assert 'secrets.token_urlsafe' in source, \
            "SECRET_KEY now uses secrets.token_urlsafe()"
        assert 'config.json' in source, \
            "SECRET_KEY is persisted to ~/.fixate/config.json"

    def test_find_free_port_is_called(self):
        """find_free_port() is no longer dead code — it's used."""
        entry_path = os.path.join(
            os.path.dirname(__file__), '..', 'desktop', 'backend_entry.py'
        )
        with open(entry_path) as f:
            source = f.read()

        # find_free_port is called at module level: PORT = find_free_port()
        assert 'PORT = find_free_port()' in source, \
            "PORT is now dynamic — uses find_free_port()"
        assert "= find_free_port()" in source, \
            "find_free_port is no longer dead code"

    def test_port_is_dynamic_not_hardcoded(self):
        """PORT = 18000 is replaced with PORT = find_free_port()."""
        entry_path = os.path.join(
            os.path.dirname(__file__), '..', 'desktop', 'backend_entry.py'
        )
        with open(entry_path) as f:
            source = f.read()

        assert 'PORT = 18000' not in source, \
            "Hardcoded PORT=18000 removed — now dynamic"

    def test_auto_migrate_on_startup(self):
        """migrate --noinput is called before runserver."""
        entry_path = os.path.join(
            os.path.dirname(__file__), '..', 'desktop', 'backend_entry.py'
        )
        with open(entry_path) as f:
            source = f.read()

        assert 'migrate' in source and '--noinput' in source, \
            "Auto-migration is called before runserver"
        # Make sure migrate comes before runserver in main()
        migrate_pos = source.find('migrate')
        runserver_pos = source.find('runserver')
        assert migrate_pos < runserver_pos, \
            f"migrate (at position {migrate_pos}) must come before runserver (at {runserver_pos})"
