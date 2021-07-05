emoji_tables = ['emojis']


if __name__ == '__main__':
    from viktor.etl.etl_all import ETL
    etl = ETL(tables=emoji_tables)
    etl.etl_emojis()
