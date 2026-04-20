"""
Módulo auxiliar para descargar dump de MySQL vía SSH usando Paramiko.
"""

import paramiko


def download_dump_via_ssh(host, user, password, db_name, db_user, db_password, output_file):
    """
    Conecta vía SSH a un servidor y descarga un dump MySQL.
    
    Args:
        host: Hostname o IP de la Raspberry
        user: Usuario SSH
        password: Contraseña SSH
        db_name: Nombre de la base de datos a dumpar
        db_user: Usuario MySQL en la Raspberry
        db_password: Contraseña MySQL en la Raspberry
        output_file: Ruta local donde guardar el dump
    """
    print(f"   Conectando a {user}@{host}...")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Conectar
        client.connect(host, username=user, password=password, timeout=10)
        print(f"   ✓ Conectado a {host}")
        
        # Comando mysqldump con contraseña
        # Nota: pasar contraseña por -p sin espacio es inseguro en algunas versiones
        # Mejor: usar --password=
        cmd = f"mysqldump -u {db_user} --password={db_password} {db_name}"
        
        print("   Ejecutando mysqldump...")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        # Si hay error
        err = stderr.read().decode()
        if err and "Warning" not in err:
            print(f"   ⚠ Aviso: {err}")
        
        # Guardar el dump
        dump_data = stdout.read().decode('utf-8')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(dump_data)
        
        file_size = len(dump_data)
        print(f"   ✓ Dump guardado: {output_file} ({file_size:,} bytes)")
        
    finally:
        client.close()
        print("   Conexión cerrada.")
