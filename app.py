from flask import Flask, render_template, request, url_for, redirect, flash, send_file
from flask_mysqldb import MySQL
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, time
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
app = Flask(__name__)
load_dotenv()

# Configuración de la base de datos:
app.secret_key = os.getenv('SECRET_KEY')
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', 3306))

app.config['MYSQL_SSL_CA'] = os.getenv('MYSQL_SSL_CA_PATH')
mysql = MySQL(app)
socketio = SocketIO(app)
# Ruta index
@app.route('/admin')
def index():
    return render_template('index.html')

@app.route('/crear', methods=['POST'])
def crear_empleado():
    if request.method == 'POST':
        # Recogemos todos los datos del formulario enviado
        nombre_empleado = request.form['nombre']
        puesto_empleado = request.form['puesto']
        
        # Conexión a MySQL
        cursor = mysql.connection.cursor()

        # Obtener el último ID registrado
        cursor.execute("SELECT MAX(id_empleado) FROM empleados")
        ultimo_id = cursor.fetchone()[0] or 0  # Default to 0 if no rows

        # Generar el nuevo código de empleado
        nuevo_codigo = f"SL0{ultimo_id + 1}"

        # Insertar los datos
        cursor.execute("INSERT INTO empleados (codigo_empleado, nombre_completo, puesto) VALUES (%s, %s, %s)", 
                        (nuevo_codigo, nombre_empleado, puesto_empleado))
        
        # Guardar los cambios y enviarlos a la DB
        mysql.connection.commit()
        cursor.close()

        flash('El empleado se ha añadido correctamente')
        return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
def asistencia():
    if request.method == 'POST':
        try:
            # Recoger el código de empleado del formulario
            codigo_empleado = request.form['codigo_empleado']
            
            # Conexión a MySQL
            cursor = mysql.connection.cursor()

            # Buscar el ID y nombre del empleado usando el código
            cursor.execute("SELECT id_empleado, nombre_completo FROM empleados WHERE codigo_empleado = %s", (codigo_empleado,))
            empleado = cursor.fetchone()

            if empleado:
                id_empleado, nombre_empleado = empleado

                # Registrar la asistencia con la fecha y hora actuales
                fecha_actual = datetime.now().date()
                hora_actual = datetime.now().time()

                cursor.execute("INSERT INTO asistencias (id_empleado, fecha, hora) VALUES (%s, %s, %s)",
                               (id_empleado, fecha_actual, hora_actual))

                # Guardar los cambios y enviarlos a la DB
                mysql.connection.commit()
                cursor.close()

                # Mensaje flash con el nombre del empleado
                flash(f'Hola, {nombre_empleado}, se registró tu asistencia del día de hoy!')
            else:
                flash('Código de empleado no encontrado')
        except Exception as e:
            flash(f'Error al registrar la asistencia: {str(e)}')

        return redirect(url_for('asistencia'))

    return render_template('asistencia.html')

@app.route('/reporte_asistencia')
def reporte_asistencia():    
    # Obtener la fecha de inicio y fin de la semana
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Conexión a MySQL
    cursor = mysql.connection.cursor()

    # Obtener las asistencias de la semana
    cursor.execute("""
        SELECT
            e.nombre_completo,
            e.codigo_empleado,
            e.puesto,
            a.fecha,
            a.hora
        FROM
            asistencias a
        INNER JOIN
            empleados e ON a.id_empleado = e.id_empleado
        WHERE
            a.fecha BETWEEN %s AND %s
        ORDER BY
            a.fecha ASC, a.hora ASC;
        """, (start_of_week, end_of_week))
    asistencias = cursor.fetchall()

    cursor.close()

    # Crear el PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Contenido
    content = []
    
    # Estilos
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=1))
    
    # Título y subtítulo
    content.append(Paragraph("Sunlunch", styles['Heading1']))
    content.append(Paragraph("Reporte de Asistencia Semanal", styles['Heading2']))
    content.append(Paragraph(f"Periodo: {start_of_week.strftime('%d/%m/%Y')} - {end_of_week.strftime('%d/%m/%Y')}", styles['Center']))
    content.append(Spacer(1, 0.25*inch))
    
    # Tabla de datos
    data = [['Nombre', 'Código', 'Cargo', 'Fecha', 'Hora']]
    for asistencia in asistencias:
        fecha = asistencia[3].strftime('%d/%m/%Y')  # asistencia[3] es un objeto date
        if isinstance(asistencia[4], time):
            hora = asistencia[4].strftime('%H:%M')    # asistencia[4] es un objeto time
        else:
            # Manejo de casos si es timedelta (ajusta según sea necesario)
            total_seconds = int(asistencia[4].total_seconds())
            horas, resto = divmod(total_seconds, 3600)
            minutos, segundos = divmod(resto, 60)
            hora = f"{horas:02}:{minutos:02}"
        data.append([asistencia[0], asistencia[1], asistencia[2], fecha, hora])
    
    table = Table(data)
    
    # Estilo de la tabla
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#CCFFFF")),  # Color suave para el encabezado
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table.setStyle(table_style)
    
    content.append(table)
    
    # Construir PDF
    doc.build(content)
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="reporte_asistencia_sunlunch.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    socketio.run(app, host='0.0.0.0', port=port, use_reloader=False)