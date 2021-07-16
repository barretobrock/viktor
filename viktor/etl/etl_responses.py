response_tables = ['responses', 'insults', 'compliments', 'phrases', 'facts', 'uwu_graphics']


if __name__ == '__main__':
    from viktor.etl.etl_all import ETL
    etl = ETL(tables=response_tables)
    etl.etl_responses()
