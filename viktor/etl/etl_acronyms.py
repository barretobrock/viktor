acronym_tables = ['acronyms']


if __name__ == '__main__':
    from viktor.etl.etl_all import ETL
    etl = ETL(tables=acronym_tables)
    etl.etl_acronyms()
