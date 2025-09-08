import logging
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from uuid import UUID
from weakref import WeakKeyDictionary

import nestedtext as nt
from sqlalchemy import MetaData, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, registry

from ubu.db.custom_types._api import UTCDateTime, sUUID
from ubu.runtime._api import RuntimePaths
from ubu.settings._api import UbuSettings

log = logging.getLogger(__name__)

naming_convention = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}

metadata = MetaData(naming_convention=naming_convention)

reg = registry(
    metadata=metadata,
    type_annotation_map={
        datetime: UTCDateTime,
        UUID: sUUID,
    },
)


class BaseNoId(DeclarativeBase):
    registry = reg


class Base(BaseNoId):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, sort_order=-1)


ECHO = False  # True


class Db:
    def __init__(
        self,
        runtime_paths: RuntimePaths,
        settings: UbuSettings,
        engine_path: str | None = None,
        echo: bool | None = None,
    ):
        self.settings = settings
        self.engine_path = engine_path
        self.echo = echo
        if self.engine_path is None:
            self.engine_path = f'sqlite:///{runtime_paths.app_db_path.absolute()}'
        if echo is None:
            self.echo = ECHO

        self.temp_table_id = 1000000000

        sqlite3.enable_callback_tracebacks(True)

        self.engine = create_engine(self.engine_path, echo=self.echo)

        if settings.debug:
            # Keep track of the traceback when a session is created
            # This is useful for debugging session leaks
            self._session_tracebacks: WeakKeyDictionary[
                Session, traceback.StackSummary
            ] = WeakKeyDictionary()

        self.total_connections = 0

        @event.listens_for(self.engine, 'connect')
        def _on_connect(dbapi_conn: sqlite3.Connection, conn_record):
            self.total_connections += 1
            # enable foreign key enforcement, needs to be done on each connection
            cursor = dbapi_conn.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

        @event.listens_for(self.engine, 'close')
        def _on_close(dbapi_conn: sqlite3.Connection, conn_record):
            self.total_connections -= 1

        with self.engine.connect() as conn:
            # Optimal settings seem to be journal_mode=WAL synchronous=full
            # https://www.agwa.name/blog/post/sqlite_durability
            cursor = conn.connection.cursor()
            cursor.execute('PRAGMA encoding="UTF-8"')
            cursor.execute('PRAGMA case_sensitive_like=ON')  # TODO deprecated
            cursor.execute('PRAGMA synchronous=full')
            cursor.execute('PRAGMA temp_store=memory')
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA cache_size=16384')  # 16 MB
            cursor.execute('PRAGMA busy_timeout=5000')  # 5 seconds
            cursor.close()

        migrations_path = runtime_paths.ubu_path / 'ubu/db/migrations'

        self.do_migrations(migrations_path)

        import ubu.db.models  # noqa: F401

        reg.metadata.create_all(self.engine)  # TODO remove, we want manual migrations

    def do_migrations(self, migrations_path: Path):
        migrations = nt.load(migrations_path / 'migrations.nt')
        if not isinstance(migrations, dict):
            raise TypeError('migrations.nt is not a dict')
        most_recent_version = migrations['MOST_RECENT']

        inspector = inspect(self.engine)
        version = None
        count = 0

        with self.engine.connect() as conn:
            while True:
                if count == 0 and 'alembic_version' not in inspector.get_table_names():
                    version = 'INITIALIZE'
                else:
                    version = conn.execute(
                        text('SELECT version_num FROM alembic_version')
                    ).one_or_none()
                    if version is None:
                        # in case there's a weird DB with an empty alembic_version table
                        # happens sometimes when messing around with alembic
                        version = 'INITIALIZE'
                        conn.execute(text('DROP TABLE alembic_version'))
                    else:
                        version = version[0]

                if version == most_recent_version:
                    break

                with open(migrations_path / migrations[version]) as f:
                    migration = f.read()

                conn.connection.executescript(migration)

                count += 1

                if count > 9999:
                    raise RuntimeError('infinite migration loop happened somehow')

    def get_temp_table_name(self):
        self.temp_table_id += 1
        return f't{self.temp_table_id}'

    def session(self, *, expire_on_commit=False, **kwargs) -> Session:
        sess = Session(self.engine, expire_on_commit=expire_on_commit, **kwargs)
        if self.settings.debug:
            # Keep a weak reference to the session
            self._session_tracebacks[sess] = traceback.extract_stack()
        return sess

    def _debug_connections(self):
        """Debug helper to show all active database connections."""
        if not self.engine:
            log.debug('No database engine available to check connections.')
            return
        try:
            # Check SQLAlchemy's connection pool status
            if self.engine.pool:
                log.debug(f'Connection pool size: {self.engine.pool.size()}')
                log.debug(
                    f'Connection pool checked out: {self.engine.pool.checkedout()}'
                )
                log.debug(f'Connection pool overflow: {self.engine.pool.overflow()}')

        except Exception as e:
            log.warning(f'Error checking connections: {e}')

    def teardown(self):
        """Cleans up the database connection."""
        log.debug('Closing database connection.')
        log.debug('Connection status before teardown:')
        self._debug_connections()

        # Perform final checkpoint before disposing engine
        if self.engine:
            try:
                log.debug('Performing final WAL checkpoint...')
                with self.engine.connect() as conn:
                    result = conn.execute(text('PRAGMA wal_checkpoint(TRUNCATE)'))
                    checkpoint_result = result.fetchone()
                    log.debug(f'TRUNCATE checkpoint result: {checkpoint_result}')
                    conn.commit()
                log.debug('WAL checkpoint completed successfully')
            except Exception as e:
                log.debug(f'Failed to checkpoint WAL on shutdown: {e}')

            # Note for macOS:
            # SQLite WAL mode might not clean up WAL and SHM files on shutdown.
            # This isn't because of a bug in our program.
            # https://github.com/groue/GRDB.swift/issues/739

            # Now dispose of the engine to close all connections
            log.debug('Disposing engine to close all connections...')
            self.engine.dispose()
            self.engine = None
            log.debug('Engine disposed - all connections should now be closed')

        if self.total_connections > 0:
            warning = f'There are still {self.total_connections} open connections at teardown! '
            warning += 'This may indicate a session leak. '
            if not self.settings.debug:
                warning += 'Enable debug mode to see tracebacks of when sessions were allocated.'
            else:
                warning += 'Check the session tracebacks for more information.'
            log.warning(warning)
            if self.settings.debug:
                any_active = any(s.is_active for s in self._session_tracebacks)
                for sess, tb in self._session_tracebacks.items():
                    if any_active and not sess.is_active:
                        # If we don't have any active sessions, show all non-GCd sessions (?)
                        # not 100% sure a session can't use a connection if it's not active
                        continue
                    log.warning(
                        f'Session {sess} created at:\n{"".join(traceback.format_list(tb))}'
                    )
            else:
                log.warning(
                    'You can enable debug mode to see tracebacks at the time of'
                    ' session creation and investigate leaks.'
                )

        log.debug('Database teardown complete')
