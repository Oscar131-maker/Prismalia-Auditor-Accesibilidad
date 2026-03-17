import psycopg2
import sys

print("Probando conexión a PostgreSQL...")
try:
    conn = psycopg2.connect(
        user="postgres",
        password="postgres",
        host="127.0.0.1",
        port="5432",
        database="postgres"
    )
    print("¡Conexión exitosa!")
    conn.close()
except Exception as e:
    print(f"Error tipo: {type(e)}")
    # Careful with encoding here
    try:
        print(f"Error msg (raw): {e}")
    except UnicodeDecodeError:
        print("Error de decodificación al mostrar el mensaje.")
        # Try to read the message as bytes if possible or just ignore
except:
    print("Error desconocido grave")
