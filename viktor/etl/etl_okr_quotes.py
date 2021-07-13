quotes_tables = ['quotes']


if __name__ == '__main__':
    from viktor.etl.etl_all import ETL
    etl = ETL(tables=quotes_tables)
    etl.etl_quotes()
