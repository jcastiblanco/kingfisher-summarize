from click.testing import CliRunner

from ocdskingfisherviews.cli import cli
from ocdskingfisherviews.db import schema_exists
from tests import (ADD_VIEW_TABLES, REFRESH_VIEWS_TABLES, assert_log_records, assert_log_running, fetch_all, fixture,
                   get_tables)

command = 'add-view'


def test_validate_collections_noninteger(caplog):
    runner = CliRunner()

    result = runner.invoke(cli, [command, 'a'])

    assert result.exit_code == 2
    assert result.output.endswith('\nError: Invalid value for "COLLECTIONS": Collection IDs must be integers\n')
    assert_log_running(caplog, command)


def test_validate_collections_nonexistent(caplog):
    runner = CliRunner()

    result = runner.invoke(cli, [command, '1,10,100'])

    assert result.exit_code == 2
    assert result.output.endswith('\nError: Invalid value for "COLLECTIONS": Collection IDs {10, 100} not found\n')
    assert_log_running(caplog, command)


def test_command(caplog):
    with fixture() as result:
        assert schema_exists('view_data_collection_1')
        assert fetch_all('SELECT * FROM view_data_collection_1.selected_collections') == [(1,)]
        assert fetch_all('SELECT id, note FROM view_data_collection_1.note') == [(1, 'Default')]

        assert result.exit_code == 0
        assert result.output == ''
        assert_log_records(caplog, command, [
            'Added collection_1',
        ])


def test_command_multiple(caplog):
    with fixture(collections='1,2') as result:
        assert schema_exists('view_data_collection_1_2')
        assert fetch_all('SELECT * FROM view_data_collection_1_2.selected_collections') == [(1,), (2,)]
        assert fetch_all('SELECT id, note FROM view_data_collection_1_2.note') == [(1, 'Default')]

        assert result.exit_code == 0
        assert result.output == ''
        assert_log_records(caplog, command, [
            'Added collection_1_2',
        ])


def test_command_build(caplog):
    with fixture(dontbuild=False, tables_only=True, threads='2') as result:
        assert get_tables('view_data_collection_1') == ADD_VIEW_TABLES | REFRESH_VIEWS_TABLES | {'field_counts'}

        assert result.exit_code == 0
        assert result.output == ''
        assert_log_records(caplog, command, [
            'Added collection_1',
            'Running refresh-views collection_1 --tables-only',
            'Running field-counts collection_1 --threads 2',
            'Running correct-user-permissions',
        ])


def test_command_name(caplog):
    with fixture(name='custom') as result:
        assert schema_exists('view_data_custom')

        assert result.exit_code == 0
        assert result.output == ''
        assert_log_records(caplog, command, [
            'Added custom',
        ])
