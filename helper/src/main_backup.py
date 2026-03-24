import boto3
import psycopg2


def lambda_handler(event, context):
    rds_client = boto3.client('rds')

    db_endpoint = 'dss-dev-postgresql.cr4g2wgwatn0.eu-west-2.rds.amazonaws.com'
    db_port = '5432'
    db_user = 'iam_user'
    db_master_user = 'postgresadmin'
    db_master_user_password = ''
    region = 'eu-west-2'

    # Generate authentication token
    token = rds_client.generate_db_auth_token(DBHostname=db_endpoint,
                                              Port=db_port,
                                              DBUsername=db_user,
                                              Region=region)
    #print('token: '+ token)

    # cert_path = './eu-west-2-bundle.pem'
    # if os.path.isfile(cert_path):
    #     print("Certificate file found.")
    # else:
    #     print("Certificate file NOT found.")

    try:
        # Connect to the database
        connection = psycopg2.connect(host=db_endpoint,
                                      port=db_port,
                                      user=db_user,
                                      password=token,
                                      database='DSS',
                                      sslmode='require',
                                      sslrootcert='./eu-west-2-bundle.pem')
        print('connection was successful!')
        # Create IAM user
        cursor = connection.cursor()
        # cursor.execute("CREATE USER iam_user WITH LOGIN;")
        # cursor.execute("ALTER USER iam_user WITH PASSWORD '';")  # Placeholder password
        # cursor.execute("GRANT rds_iam TO iam_user;")  # Grant IAM role to the new user

        cursor = connection.cursor()
        # # Grant SELECT permission on the debtor table to iam_user
        # cursor.execute("GRANT SELECT ON TABLE debtor TO iam_user;")

        # # If you want to grant additional permissions (INSERT, UPDATE, DELETE), you can do so as follows:
        # cursor.execute("GRANT INSERT, UPDATE, DELETE ON TABLE debtor TO iam_user;")

        # # Commit changes
        # connection.commit()

        # # Execute SELECT query
        cursor.execute("SELECT * FROM debtor;")
        # Fetch all results
        rows = cursor.fetchall()

        # Print the results
        print("Debtor Table Data:")
        for row in rows:
            print(row)

        #print("IAM user 'iam_user' created successfully with IAM authentication enabled.")
    except Exception as e:
        print(f"Error generating authentication token: {e}")
        return

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
