import datetime
import decimal
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from psycopg2 import sql

from manage import cli, SUMMARIES
from tests import assert_bad_argument, assert_log_records, assert_log_running, fixture, noop

command = 'add'

TABLES = {
    'note',
    'selected_collections',
}
SUMMARY_TABLES = set()
SUMMARY_VIEWS = set()
FIELD_LIST_TABLES = set()
NO_FIELD_LIST_TABLES = set()
NO_FIELD_LIST_VIEWS = set()

for summary_table in SUMMARIES:
    FIELD_LIST_TABLES.add(f'{summary_table.name}_field_list')

    if summary_table.is_table:
        SUMMARY_TABLES.add(summary_table.name)
        NO_FIELD_LIST_TABLES.add(f'{summary_table.name}_no_field_list')
    else:
        SUMMARY_VIEWS.add(summary_table.name)
        NO_FIELD_LIST_VIEWS.add(f'{summary_table.name}_no_field_list')
        TABLES.add(f'{summary_table.name}_no_data')


@pytest.mark.parametrize('collections, message', [
    ('a', 'Collection IDs must be integers'),
    ('1,10,100', 'Collection IDs {10, 100} not found'),
])
def test_validate_collections(collections, message, caplog):
    runner = CliRunner()

    result = runner.invoke(cli, [command, collections])

    assert result.exit_code == 2
    assert_bad_argument(result, 'COLLECTIONS', message)
    assert_log_running(caplog, command)


def test_validate_name(caplog):
    runner = CliRunner()

    result = runner.invoke(cli, [command, '1', '--name', 'camelCase'])

    assert result.exit_code == 2
    assert_bad_argument(result, '--name', 'value must be lowercase')
    assert_log_running(caplog, command)


@patch('manage.summary_tables', noop)
@patch('manage.field_counts', noop)
@patch('manage.field_lists', noop)
@pytest.mark.parametrize('kwargs, name, collections', [
    ({}, 'collection_1', (1,)),
    ({'collections': '1,2'}, 'collection_1_2', (1, 2)),
    ({'name': 'custom'}, 'custom', (1,)),
])
def test_command_name(kwargs, name, collections, db, caplog):
    schema = f'view_data_{name}'
    identifier = sql.Identifier(schema)

    with fixture(db, **kwargs) as result:
        assert db.schema_exists(schema)
        assert db.all(sql.SQL('SELECT * FROM {schema}.selected_collections').format(schema=identifier)) == [
            (collection,) for collection in collections
        ]
        assert db.all(sql.SQL('SELECT id, note FROM {schema}.note').format(schema=identifier)) == [
            (1, 'Default'),
        ]

        assert result.exit_code == 0
        assert result.output == ''
        assert_log_records(caplog, command, [
            f'Arguments: collections={collections!r} note=Default name={kwargs.get("name")} tables_only=False',
            f'Added {name}',
            'Running summary-tables routine',
            'Running field-counts routine',
            'Running field-lists routine',
        ])


@pytest.mark.parametrize('tables_only, field_counts, field_lists, tables, views', [
    (False, True, False,
     TABLES | SUMMARY_TABLES, SUMMARY_VIEWS),
    (True, True, False,
     TABLES | SUMMARY_TABLES | SUMMARY_VIEWS, set()),
    (False, False, True,
     TABLES | FIELD_LIST_TABLES | NO_FIELD_LIST_TABLES, SUMMARY_TABLES | SUMMARY_VIEWS | NO_FIELD_LIST_VIEWS),
    (True, False, True,
     TABLES | FIELD_LIST_TABLES | NO_FIELD_LIST_TABLES | SUMMARY_TABLES | SUMMARY_VIEWS | NO_FIELD_LIST_VIEWS, set()),
])
def test_command(db, tables_only, field_counts, field_lists, tables, views, caplog):
    with fixture(db, tables_only=tables_only, field_counts=field_counts, field_lists=field_lists) as result:
        # Check existence of schema, tables and views.
        if field_counts:
            tables.add('field_counts')

        assert db.schema_exists('view_data_collection_1')
        assert set(db.pluck("SELECT table_name FROM information_schema.tables WHERE table_schema = %(schema)s "
                            "AND table_type = 'BASE TABLE'", {'schema': 'view_data_collection_1'})) == tables
        assert set(db.pluck("SELECT table_name FROM information_schema.tables WHERE table_schema = %(schema)s "
                            "AND table_type = 'VIEW'", {'schema': 'view_data_collection_1'})) == views

        # Check contents of summary relations.
        rows = db.all("""
            SELECT
                award_index,
                release_type,
                collection_id,
                ocid,
                release_id,
                award_id,
                award_title,
                award_status,
                award_description,
                award_value_amount,
                award_value_currency,
                award_date,
                award_contractperiod_startdate,
                award_contractperiod_enddate,
                award_contractperiod_maxextentdate,
                award_contractperiod_durationindays,
                suppliers_count,
                documents_count,
                documenttype_counts,
                items_count
            FROM view_data_collection_1.awards_summary
            ORDER BY id, award_index
        """)

        assert rows[0] == (
            0,  # award_index
            'release',  # release_type
            1,  # collection_id
            'dolore',  # ocid
            'ex laborumsit autein magna veniam',  # release_id
            'reprehenderit magna cillum eu nisi',  # award_id
            'laborum aute nisi eiusmod',  # award_title
            'pending',  # award_status
            'ullamco in voluptate',  # award_description
            decimal.Decimal('-95099396'),  # award_value_amount
            'AMD',  # award_value_currency
            datetime.datetime(3263, 12, 5, 21, 24, 19, 161000),  # award_date
            datetime.datetime(4097, 9, 16, 5, 55, 19, 125000),  # award_contractperiod_startdate
            datetime.datetime(4591, 4, 29, 6, 34, 28, 472000),  # award_contractperiod_enddate
            datetime.datetime(3714, 8, 9, 7, 21, 37, 544000),  # award_contractperiod_maxextentdate
            decimal.Decimal('72802012'),  # award_contractperiod_durationindays
            2,  # suppliers_count
            4,  # documents_count
            {
                'Excepteur nisi et': 1,
                'proident exercitation in': 1,
                'ut magna dolore velit aute': 1,
                'veniam enim aliqua d': 1,
            },  # documenttype_counts
            5,  # items_count
        )
        assert len(rows) == 301

        rows = db.all("""
            SELECT
                party_index,
                release_type,
                collection_id,
                ocid,
                release_id,
                parties_id,
                roles,
                identifier,
                unique_identifier_attempt,
                parties_additionalidentifiers_ids,
                parties_additionalidentifiers_count
            FROM view_data_collection_1.parties_summary
            ORDER BY id, party_index
        """)

        assert rows[0] == (
            0,  # party_index
            'release',  # release_type
            1,  # collection_id
            'dolore',  # ocid
            'ex laborumsit autein magna veniam',  # release_id
            'voluptate officia tempor dolor',  # parties_id
            [
                'ex ',
                'in est exercitation nulla Excepteur',
                'ipsum do',
            ],  # roles
            'ad proident dolor reprehenderit veniam-in quis exercitation reprehenderit',  # identifier
            'voluptate officia tempor dolor',  # unique_identifier_attempt
            [
                'exercitation proident voluptate-sed culpa eamollit consectetur dolor l',
                'magna-dolor ut indolorein in tempor magna mollit',
                'ad occaecat amet anim-laboris ea Duisdeserunt quis sed pariatur mollit',
                'elit mollit-officia proidentmagna',
                'ex-minim Ut consectetur',
            ],  # parties_additionalidentifiers_ids
            5,  # parties_additionalidentifiers_count

        )
        assert len(rows) == 296

        if field_counts:
            # Check contents of field_counts table.
            rows = db.all('SELECT * FROM view_data_collection_1.field_counts')

            assert len(rows) == 65235
            assert rows[0] == (1, 'release', 'awards', 100, 301, 100)

        if field_lists:
            # Check the count of keys in the field_list field for the lowest primary keys in each summary relation.
            statement = """
                SELECT
                    count(*)
                FROM
                    (SELECT
                        jsonb_each(field_list)
                    FROM (
                        SELECT
                            field_list
                        FROM
                            view_data_collection_1.{table}
                        ORDER BY
                            {primary_keys}
                        LIMIT 1) AS field_list
                    ) AS each
            """

            expected = {
                'award_documents_summary': 11,
                'award_items_summary': 26,
                'award_suppliers_summary': 28,
                'awards_summary': 140,
                'buyer_summary': 28,
                'contract_documents_summary': 11,
                'contract_implementation_documents_summary': 11,
                'contract_implementation_milestones_summary': 29,
                'contract_implementation_transactions_summary': 83,
                'contract_items_summary': 26,
                'contract_milestones_summary': 27,
                'contracts_summary': 328,
                'parties_summary': 34,
                'planning_documents_summary': 11,
                'planning_milestones_summary': 29,
                'planning_summary': 61,
                'procuringentity_summary': 32,
                'release_summary': 1046,
                'tender_documents_summary': 15,
                'tender_items_summary': 25,
                'tender_milestones_summary': 23,
                'tender_summary': 228,
                'tenderers_summary': 31,
            }

            for table in SUMMARIES:
                count = db.one(db.format(statement, table=table.name, primary_keys=table.primary_keys))[0]

                assert count == expected[table.name], f'{table.name}: {count} != {expected[table.name]}'

        # All columns have comments.
        assert not db.all("""
            SELECT
                isc.table_name,
                isc.column_name,
                isc.data_type
            FROM
                information_schema.columns isc
            WHERE
                isc.table_schema = %(schema)s
                AND LOWER(isc.table_name) NOT IN ('selected_collections', 'note')
                AND LOWER(isc.table_name) NOT LIKE '%%_no_data'
                AND LOWER(isc.table_name) NOT LIKE '%%_field_list'
                AND pg_catalog.col_description(format('%%s.%%s',isc.table_schema,isc.table_name)::regclass::oid,
                                               isc.ordinal_position) IS NULL
        """, {'schema': 'view_data_collection_1'})

        expected = [
            f'Arguments: collections=(1,) note=Default name=None tables_only={tables_only!r}',
            'Added collection_1',
            'Running summary-tables routine',
        ]
        if field_counts:
            expected.append('Running field-counts routine')
        if field_lists:
            expected.append('Running field-lists routine')

        assert result.exit_code == 0
        assert result.output == ''
        assert_log_records(caplog, command, expected)
