user_tables = ['users']


if __name__ == '__main__':
    from viktor.etl.etl_all import ETL
    etl = ETL(tables=user_tables)
    etl.etl_okr_users()
