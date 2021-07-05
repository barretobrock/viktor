okr_tables = ['perks']


if __name__ == '__main__':
    from viktor.etl.etl_all import ETL
    etl = ETL(tables=okr_tables)
    etl.etl_okr_perks()
