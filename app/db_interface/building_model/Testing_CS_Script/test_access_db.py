"""
test script to access the prospects_master" databas eusing the RDS IAM user

:Author: Michel Eric Levy _mel_
:Creation date: September 4th, 2025
:Last updated: 9/4/2025 (_mel_)
"""

import boto3, psycopg2

ENDPOINT = "funnel-prospects.c9cu68eyszlt.us-west-2.rds.amazonaws.com"
PORT     = 5432
DBNAME   = "prospects_master"
USER     = "app_ext_dev"
REGION   = "us-west-2"

session = boto3.Session(profile_name="rds-dev")
client  = session.client("rds")
token   = client.generate_db_auth_token(DBHostname=ENDPOINT, Port=PORT, DBUsername=USER, Region=REGION)

conn = psycopg2.connect(
    host=ENDPOINT, port=PORT, database=DBNAME, user=USER, password=token,
    sslmode="require"  # use SSL; you can also provide RDS CA with sslrootcert
)
cur = conn.cursor(); 
cur.execute("SELECT now()"); print(cur.fetchone())
cur.execute("SELECT current_database()"); print(cur.fetchone())
cur.close(); conn.close()

