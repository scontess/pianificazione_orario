import os
import csv
from flask import Flask, jsonify, render_template, request
import os
import libsql
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

app = Flask(__name__)

TURSO_URL = os.getenv("LIBSQL_DATABASE_URL")
if TURSO_URL:
    TURSO_URL = TURSO_URL.strip()

TURSO_TOKEN = os.getenv("LIBSQL_AUTH_TOKEN")
if TURSO_TOKEN:
    TURSO_TOKEN = TURSO_TOKEN.strip()

    
class LibSqlRowDict(dict):
    """Classe di supporto per rendere le righe di libsql compatibili con dict(row) e accesso per indice/chiave"""
    def __init__(self, cursor, row):
        columns = [col[0] for col in cursor.description]
        super().__init__(zip(columns, row))
        self._row = row

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._row[key]
        return super().__getitem__(key)

class LibSqlCursorWrapper:
    """Wrappa il cursore per restituire automaticamente righe compatibili"""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=()):
        self._cursor.execute(query, params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if not row:
            return None
        return LibSqlRowDict(self._cursor, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [LibSqlRowDict(self._cursor, row) for row in rows]

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class LibSqlConnWrapper:
    """Wrappa la connessione per intercettare i cursori"""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return LibSqlCursorWrapper(self._conn.cursor())

    def execute(self, query, params=()):
        cur = self.cursor()
        return cur.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db():
    # Connessione remota a Turso protetta da wrapper di compatibilità totale
    print(f"-> CONNESSO A TURSO CLOUD SULL'URL: {TURSO_URL}")
    conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    return LibSqlConnWrapper(conn)

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS professori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cognome TEXT NOT NULL,
            note TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            anno TEXT,
            visibile INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS materie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profclassemateria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profid INTEGER,
            materiaid INTEGER,
            classeid INTEGER,
            oresettimanali_totali INTEGER,
            priorita INTEGER,
            FOREIGN KEY(profid) REFERENCES professori(id),
            FOREIGN KEY(materiaid) REFERENCES materie(id),
            FOREIGN KEY(classeid) REFERENCES classi(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classemateria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classeid INTEGER,
            materia_id INTEGER,
            FOREIGN KEY(classeid) REFERENCES classi(id),
            FOREIGN KEY(materia_id) REFERENCES materie(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classeid INTEGER,
            settimana TEXT,
            giorno TEXT,
            ora INTEGER,
            profid INTEGER,
            materia_id INTEGER,
            is_fuori_cattedra INTEGER DEFAULT 0,
            FOREIGN KEY(classeid) REFERENCES classi(id),
            FOREIGN KEY(profid) REFERENCES professori(id),
            FOREIGN KEY(materia_id) REFERENCES materie(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vincoliprof (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profid INTEGER,
            giorno TEXT,
            ora INTEGER,
            tipo_vincolo TEXT,
            FOREIGN KEY(profid) REFERENCES professori(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vincoliclassi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classeid INTEGER,
            giorno TEXT,
            ora INTEGER,
            tipo_vincolo TEXT,
            FOREIGN KEY(classeid) REFERENCES classi(id)
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


def importa_dati_iniziali(csv_file_path, db_path='database.db'):
    conn = get_db()  #Modificato rispetto al database locale
    cursor = conn.cursor()

    try:
        cursor.execute('PRAGMA foreign_keys = ON;')

        def get_or_create_classe(nome, anno=''):
            cursor.execute('SELECT id FROM classi WHERE nome = ?', (nome,))
            res = cursor.fetchone()
            if res:
                return res[0]
            cursor.execute('INSERT INTO classi (nome, anno, visibile) VALUES (?, ?, 1)', (nome, anno))
            return cursor.lastrowid

        def get_or_create_materia(nome):
            cursor.execute('SELECT id FROM materie WHERE nome = ?', (nome,))
            res = cursor.fetchone()
            if res:
                return res[0]
            cursor.execute('INSERT INTO materie (nome) VALUES (?)', (nome,))
            return cursor.lastrowid

        def get_or_create_professore(nome, cognome):
            cursor.execute('SELECT id FROM professori WHERE nome = ? AND cognome = ?', (nome, cognome))
            res = cursor.fetchone()
            if res:
                return res[0]
            cursor.execute("INSERT INTO professori (nome, cognome, note) VALUES (?, ?, '')", (nome, cognome))
            return cursor.lastrowid

        with open(csv_file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader)

            for row in reader:
                if not row or len(row) < 2:
                    continue

                tipo_record = row[0].strip().upper()

                if tipo_record == 'CLASSE':
                    nome_classe = row[1].strip()
                    anno_classe = row[2].strip() if len(row) > 2 else ''
                    get_or_create_classe(nome_classe, anno_classe)

                elif tipo_record == 'CATTEDRA':
                    prof_nome = row[1].strip()
                    prof_cognome = row[2].strip()
                    materia_nome = row[3].strip()
                    classe_nome = row[4].strip()
                    ore_totali = int(row[5].strip()) if row[5].strip() else 1
                    priorita = int(row[6].strip()) if row[6].strip() else 1

                    prof_id = get_or_create_professore(prof_nome, prof_cognome)
                    materia_id = get_or_create_materia(materia_nome)
                    classe_id = get_or_create_classe(classe_nome)

                    cursor.execute("""
                        SELECT id FROM profclassemateria 
                        WHERE profid = ? AND materiaid = ? AND classeid = ?
                    """, (prof_id, materia_id, classe_id))

                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO profclassemateria (profid, materiaid, classeid, oresettimanali_totali, priorita)
                            VALUES (?, ?, ?, ?, ?)
                        """, (prof_id, materia_id, classe_id, ore_totali, priorita))

                    cursor.execute("""
                        SELECT id FROM classemateria WHERE classeid = ? AND materia_id = ?
                    """, (classe_id, materia_id))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO classemateria (classeid, materia_id) VALUES (?, ?)
                        """, (classe_id, materia_id))

                elif tipo_record == 'VINCOLO':
                    cognome_prof = row[1].strip()
                    tipo_vincolo = row[2].strip()
                    giorno = row[3].strip()
                    ora_str = row[4].strip() if len(row) > 4 else ''
                    ora = int(ora_str) if ora_str else 0

                    cursor.execute('SELECT id FROM professori WHERE cognome LIKE ?', (f'%{cognome_prof}%',))
                    prof_res = cursor.fetchone()

                    if prof_res:
                        prof_id = prof_res[0]
                        cursor.execute("""
                            INSERT INTO vincoliprof (profid, giorno, ora, tipo_vincolo)
                            VALUES (?, ?, ?, ?)
                        """, (prof_id, giorno, ora, tipo_vincolo))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


@app.route('/admin/import_master', methods=['POST'])
def admin_import_master():
    if 'file_csv' not in request.files:
        return jsonify({"success": False, "message": "Nessun file selezionato."}), 400
    
    file = request.files['file_csv']
    if file.filename == '':
        return jsonify({"success": False, "message": "Nome file non valido."}), 400

    if file:
        temp_path = "temp_master.csv"
        file.save(temp_path)
        
        try:
            importa_dati_iniziali(temp_path, "database.db")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"success": True, "message": "Caricamento iniziale completato con successo!"})
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"success": False, "message": f"Errore durante l'importazione: {str(e)}"}), 500


@app.route("/professori", methods=["GET"])
def get_professori():
    settimana = request.args.get("settimana")
    conn = get_db()
    cursor = conn.cursor()
    
    if not settimana or settimana == "undefined" or settimana == "null":
        cursor.execute("SELECT settimana FROM orario ORDER BY settimana DESC LIMIT 1")
        res = cursor.fetchone()
        settimana = res["settimana"] if res else ""

    query = """
        SELECT pm.id, pm.profid, pm.materiaid, pm.classeid, pm.oresettimanali_totali, pm.priorita,
        p.nome as prof_nome, p.cognome as prof_cognome, p.note as prof_note,
        m.nome as materia_nome, c.nome as classe_nome,
        (pm.oresettimanali_totali - COALESCE((
            SELECT COUNT(*) FROM orario o 
            WHERE o.profid = pm.profid 
              AND o.materia_id = pm.materiaid 
              AND o.classeid = pm.classeid 
              AND o.settimana = ?
        ), 0)) as oreresidue
        FROM profclassemateria pm
        JOIN professori p ON pm.profid = p.id
        JOIN materie m ON pm.materiaid = m.id
        JOIN classi c ON pm.classeid = c.id
        ORDER BY p.cognome ASC, pm.priorita ASC
    """
    rows = conn.execute(query, (settimana,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/professori/lista", methods=["GET"])
def get_professori_lista():
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT id, nome, cognome, note FROM professori ORDER BY cognome ASC").fetchall()
    profs = [dict(row) for row in rows]
    conn.close()
    return jsonify(profs)


@app.route("/materie", methods=["GET"])
def get_materie():
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT id, nome FROM materie ORDER BY nome ASC").fetchall()
    materie = [dict(row) for row in rows]
    conn.close()
    return jsonify(materie)


@app.route("/classi", methods=["GET"])
def get_classi():
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT id, nome, anno, visibile FROM classi ORDER BY nome ASC").fetchall()
    classi = [dict(row) for row in rows]
    conn.close()
    return jsonify(classi)


@app.route("/vincoli_prof", methods=["GET"])
def get_vincoli_prof_index():
    conn = get_db()
    rows = conn.execute("SELECT * FROM vincoliprof").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/vincoliprof/lista", methods=["GET"])
def get_vincoli_lista():
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT v.id, v.profid, p.nome as prof_nome, p.cognome as prof_cognome, 
               v.giorno, v.ora, v.tipo_vincolo
        FROM vincoliprof v
        JOIN professori p ON v.profid = p.id
    """
    rows = [dict(row) for row in cursor.execute(query).fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/profclassemateria/lista", methods=["GET"])
def get_profclassemateria_lista():
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT pcm.id, pcm.profid, pcm.materiaid, pcm.classeid, 
               p.nome as prof_nome, p.cognome as prof_cognome, 
               m.nome as materia_nome, 
               c.nome as classe_nome, 
               pcm.oresettimanali_totali
        FROM profclassemateria pcm
        JOIN professori p ON pcm.profid = p.id
        JOIN materie m ON pcm.materiaid = m.id
        JOIN classi c ON pcm.classeid = c.id
    """
    rows = [dict(row) for row in cursor.execute(query).fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/orario", methods=["GET"])
def get_orario():
    settimana = request.args.get("settimana")
    conn = get_db()
    
    if settimana:
        rows = conn.execute("""
            SELECT o.*, p.nome as prof_nome, p.cognome as prof_cognome, m.nome as materia_nome, c.nome as classe_nome
            FROM orario o
            JOIN professori p ON o.profid = p.id
            JOIN materie m ON o.materia_id = m.id
            JOIN classi c ON o.classeid = c.id
            WHERE o.settimana = ?
        """, (settimana,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT o.*, p.nome as prof_nome, p.cognome as prof_cognome, m.nome as materia_nome, c.nome as classe_nome
            FROM orario o
            JOIN professori p ON o.profid = p.id
            JOIN materie m ON o.materia_id = m.id
            JOIN classi c ON o.classeid = c.id
        """).fetchall()
        
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/orario", methods=["POST"])
def post_orario():
    data = request.json
    classeid = data.get("classeid")
    settimana = data.get("settimana")
    giorno = data.get("giorno")
    ora = data.get("ora")
    profid = data.get("profid")
    materia_id = data.get("materia_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM classemateria WHERE classeid = ? AND materia_id = ?", (classeid, materia_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({
            "status": "rosso",
            "message": "Operazione rifiutata: la materia non è tra le necessarie per questa classe."
        }), 400

    cursor.execute("""
        SELECT tipo_vincolo FROM vincoliclassi 
        WHERE classeid = ? AND giorno = ? AND (ora = ? OR ora = 0)
    """, (classeid, giorno, ora))
    vincoli_classe = cursor.fetchall()
    for v in vincoli_classe:
        if v["tipo_vincolo"] == "assenza":
            conn.close()
            return jsonify({
                "status": "rosso",
                "message": "Operazione rifiutata: la classe non fa lezione (o è in gita/assente) in questo giorno e ora."
            }), 400

    cursor.execute("SELECT id FROM orario WHERE classeid = ? AND settimana = ? AND giorno = ? AND ora = ?", (classeid, settimana, giorno, ora))
    if cursor.fetchone():
        conn.close()
        return jsonify({
            "status": "rosso",
            "message": "La classe è già occupata in questo slot orario in questa settimana."
        }), 400

    cursor.execute("SELECT id FROM orario WHERE profid = ? AND settimana = ? AND giorno = ? AND ora = ?", (profid, settimana, giorno, ora))
    if cursor.fetchone():
        conn.close()
        return jsonify({
            "status": "rosso",
            "message": "Il professore è già impegnato in un'altra classe in questo slot."
        }), 400

    cursor.execute("""
        SELECT tipo_vincolo FROM vincoliprof 
        WHERE profid = ? AND giorno = ? AND (ora = ? OR ora = 0)
    """, (profid, giorno, ora))
    vincoli = cursor.fetchall()

    warning_msg = None
    for v in vincoli:
        tipo = v["tipo_vincolo"]
        if tipo == "assenza":
            conn.close()
            return jsonify({
                "status": "rosso",
                "message": "Operazione rifiutata: il professore ha un vincolo di assenza in questo giorno e ora."
            }), 400
        elif tipo in ["preferenza", "obbligo"]:
            warning_msg = f"Attenzione: il professore ha un vincolo di tipo '{tipo}' in questo orario, ma l'assegnazione è stata comunque registrata."

    cursor.execute("""
        SELECT id FROM profclassemateria 
        WHERE profid = ? AND materiaid = ? AND classeid = ?
    """, (profid, materia_id, classeid))
    is_ufficiale = cursor.fetchone()
    is_fuori_cattedra = 0 if is_ufficiale else 1

    cursor.execute("""
        INSERT INTO orario (classeid, settimana, giorno, ora, profid, materia_id, is_fuori_cattedra) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (classeid, settimana, giorno, ora, profid, materia_id, is_fuori_cattedra))
  
    conn.commit()
    conn.close()

    return jsonify({
        "status": "giallo" if warning_msg else "verde",
        "message": warning_msg or "Assegnazione completata!"
    })


@app.route("/orario/<int:id>", methods=["DELETE"])
def delete_orario(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM orario WHERE id = ?", (id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"status": "rosso", "message": "Orario non trovato."}), 404

    cursor.execute("DELETE FROM orario WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": f"Orario con ID {id} eliminato con successo!"}), 200


@app.route("/admin/ore-fuori-cattedra", methods=["GET"])
def get_ore_fuori_cattedra_admin():
    settimana = request.args.get("settimana")
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT profid, COUNT(*) as totale_fc FROM orario WHERE is_fuori_cattedra = 1"
    params = []
    if settimana:
        query += " AND settimana = ?"
        params.append(settimana)
    query += " GROUP BY profid"
    rows = cursor.execute(query, params).fetchall()
    mappa_fc = {row["profid"]: row["totale_fc"] for row in rows}
    conn.close()
    return jsonify(mappa_fc)


@app.route("/professori", methods=["POST"])
def add_professore():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO professori (nome, cognome, note) VALUES (?, ?, ?)",
        (data["nome"], data["cognome"], data.get("note", "")),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Professore aggiunto!"})


@app.route("/professori/<int:id>", methods=["PUT"])
def update_professore(id):
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE professori SET nome = ?, cognome = ?, note = ? WHERE id = ?",
        (data["nome"], data["cognome"], data.get("note", ""), id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Professore aggiornato!"})


@app.route("/professori/<int:id>", methods=["DELETE"])
def delete_professore(id):
    conn = get_db()
    conn.execute("DELETE FROM professori WHERE id = ?", (id,))
    conn.execute("DELETE FROM profclassemateria WHERE profid = ?", (id,))
    conn.execute("DELETE FROM vincoliprof WHERE profid = ?", (id,))
    conn.execute("DELETE FROM orario WHERE profid = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Professore eliminato!"})


@app.route("/materie", methods=["POST"])
def add_materia():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO materie (nome) VALUES (?)", (data["nome"],))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Materia aggiunta!"})


@app.route("/materie/<int:id>", methods=["PUT"])
def update_materia(id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE materie SET nome = ? WHERE id = ?", (data["nome"], id))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Materia aggiornata!"})


@app.route("/materie/<int:id>", methods=["DELETE"])
def delete_materia(id):
    conn = get_db()
    conn.execute("DELETE FROM materie WHERE id = ?", (id,))
    conn.execute("DELETE FROM classemateria WHERE materia_id = ?", (id,))
    conn.execute("DELETE FROM profclassemateria WHERE materiaid = ?", (id,))
    conn.execute("DELETE FROM orario WHERE materia_id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Materia eliminata!"})


@app.route("/classi", methods=["POST"])
def add_classe():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO classi (nome, anno, visibile) VALUES (?, ?, 1)",
        (data["nome"], data.get("anno", "")),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Classe aggiunta!"})


@app.route("/classi/<int:id>", methods=["PUT"])
def update_classe(id):
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE classi SET nome = ?, anno = ? WHERE id = ?",
        (data["nome"], data.get("anno", ""), id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Classe aggiornata!"})


@app.route("/classi/<int:id>", methods=["DELETE"])
def delete_classe(id):
    conn = get_db()
    conn.execute("DELETE FROM classi WHERE id = ?", (id,))
    conn.execute("DELETE FROM classemateria WHERE classeid = ?", (id,))
    conn.execute("DELETE FROM profclassemateria WHERE classeid = ?", (id,))
    conn.execute("DELETE FROM orario WHERE classeid = ?", (id,))
    conn.execute("DELETE FROM vincoliclassi WHERE classeid = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Classe eliminata!"})


@app.route("/classi/<int:id>/visibilita", methods=["PUT"])
def update_visibilita_classe(id):
    data = request.json
    nuovo_stato = 1 if data.get("visibile", True) else 0
    conn = get_db()
    conn.execute("UPDATE classi SET visibile = ? WHERE id = ?", (nuovo_stato, id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Visibilità aggiornata con successo!"})


@app.route("/profclassemateria", methods=["POST"])
def add_pcm():
    data = request.json
    profid = data["profid"]
    materiaid = data["materiaid"]
    classeid = data["classeid"]
    oresettimanali = data.get("oresettimanali_totali", 3)
    priorita = data.get("priorita", 1)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO profclassemateria (profid, materiaid, classeid, oresettimanali_totali, priorita)
           VALUES (?, ?, ?, ?, ?)""",
        (profid, materiaid, classeid, oresettimanali, priorita),
    )

    esist_cm = cursor.execute(
        "SELECT id FROM classemateria WHERE classeid = ? AND materia_id = ?",
        (classeid, materiaid)
    ).fetchone()

    if not esist_cm:
        cursor.execute("INSERT INTO classemateria (classeid, materia_id) VALUES (?, ?)", (classeid, materiaid))

    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Associazione creata con successo!"})


@app.route("/profclassemateria/<int:id>", methods=["DELETE"])
def delete_pcm(id):
    conn = get_db()
    conn.execute("DELETE FROM profclassemateria WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Associazione rimossa!"})


@app.route("/vincoliprof", methods=["POST"])
def add_vincolo():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO vincoliprof (profid, giorno, ora, tipo_vincolo) VALUES (?, ?, ?, ?)",
        (data["profid"], data["giorno"], data["ora"], data.get("tipo_vincolo", "indisponibile"))
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Vincolo aggiunto!"})


@app.route("/vincoliprof/<int:id>", methods=["DELETE"])
def delete_vincolo(id):
    conn = get_db()
    conn.execute("DELETE FROM vincoliprof WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Vincolo rimosso!"})


@app.route("/vincoli_classi", methods=["GET"])
def get_vincoli_classi_index():
    conn = get_db()
    rows = conn.execute("SELECT * FROM vincoliclassi").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/vincoliclassi/lista", methods=["GET"])
def get_vincoli_classi_lista():
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT v.id, v.classeid, c.nome as classe_nome, 
               v.giorno, v.ora, v.tipo_vincolo
        FROM vincoliclassi v
        JOIN classi c ON v.classeid = c.id
    """
    rows = [dict(row) for row in cursor.execute(query).fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/vincoliclassi", methods=["POST"])
def add_vincolo_classe():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO vincoliclassi (classeid, giorno, ora, tipo_vincolo) VALUES (?, ?, ?, ?)",
        (data["classeid"], data["giorno"], data["ora"], data.get("tipo_vincolo", "assenza"))
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Vincolo classe aggiunto!"})


@app.route("/vincoliclassi/<int:id>", methods=["DELETE"])
def delete_vincolo_classe(id):
    conn = get_db()
    conn.execute("DELETE FROM vincoliclassi WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "verde", "message": "Vincolo classe rimosso!"})


@app.route('/orario/copia', methods=['POST'])
def copia_orario_settimana():
    data = request.get_json()
    settimana_origine = data.get('settimana_origine')
    settimana_destinazione = data.get('settimana_destinazione')

    if not settimana_origine or not settimana_destinazione:
        return jsonify({"message": "Parametri mancanti: specificare settimana_origine e settimana_destinazione."}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT classeid, giorno, ora, profid, materia_id FROM orario WHERE settimana = ?", (settimana_origine,))
        lezioni_origine = cursor.fetchall()

        if not lezioni_origine:
            conn.close()
            return jsonify({"message": "Nessuna lezione trovata nella settimana di origine da copiare."}), 404

        cursor.execute("DELETE FROM orario WHERE settimana = ?", (settimana_destinazione,))

        for lezione in lezioni_origine:
            cursor.execute("""
                INSERT INTO orario (settimana, classeid, giorno, ora, profid, materia_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                settimana_destinazione,
                lezione['classeid'],
                lezione['giorno'],
                lezione['ora'],
                lezione['profid'],
                lezione['materia_id']
            ))

        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"Copiate con successo {len(lezioni_origine)} lezioni dalla settimana {settimana_origine} alla settimana {settimana_destinazione}."
        }), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"message": f"Errore interno del server: {str(e)}"}), 500


@app.route('/admin/pulisci_orario', methods=['POST'])
def pulisci_orario_route():
    data = request.get_json() or {}
    data_settimana = data.get('settimana')

    if not data_settimana:
        return jsonify({'success': False, 'message': 'Specificare la settimana da pulire.'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM orario WHERE settimana = ?', (data_settimana,))
        conn.commit()
        return jsonify({
            'success': True,
            'message': f'Eliminate con successo tutte le lezioni per la settimana {data_settimana}.'
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f"Errore durante l'eliminazione: {str(e)}"}), 500
    finally:
        conn.close()


@app.route('/orario/genera', methods=['POST'])
def genera_orario_automatico():
    data = request.get_json()
    settimana = data.get('settimana')
    
    if not settimana:
        return jsonify({"success": False, "message": "Specificare la settimana di destinazione."}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM orario WHERE settimana = ?", (settimana,))
        
        cursor.execute("""
            SELECT pcm.id, pcm.profid, pcm.materiaid, pcm.classeid, pcm.oresettimanali_totali, pcm.priorita,
                   p.nome as prof_nome, p.cognome as prof_cognome,
                   m.nome as materia_nome, c.nome as classe_nome
            FROM profclassemateria pcm
            JOIN professori p ON pcm.profid = p.id
            JOIN materie m ON pcm.materiaid = m.id
            JOIN classi c ON pcm.classeid = c.id
            WHERE c.visibile = 1
            ORDER BY pcm.priorita ASC, pcm.oresettimanali_totali DESC
        """)
        cattedre = cursor.fetchall()
        
        limiti_cattedra = {cat['id']: cat['oresettimanali_totali'] for cat in cattedre}
        ore_assegnate_cattedra = {cat['id']: 0 for cat in cattedre}
        
        cursor.execute("SELECT profid, giorno, ora, tipo_vincolo FROM vincoliprof")
        vincoli_prof_raw = cursor.fetchall()
        vincoli_prof = set()
        for v in vincoli_prof_raw:
            if v['tipo_vincolo'] in ['assenza', 'indisponibile']:
                if v['ora'] == 0:  
                    for h in range(1, 7):
                        vincoli_prof.add((v['profid'], v['giorno'], h))
                else:
                    vincoli_prof.add((v['profid'], v['giorno'], v['ora']))
        
        cursor.execute("""
            SELECT v.classeid, v.giorno, v.ora, v.tipo_vincolo 
            FROM vincoliclassi v
            JOIN classi c ON v.classeid = c.id
            WHERE c.visibile = 1
        """)
        vincoli_classi_raw = cursor.fetchall()
        vincoli_classi = set()
        for v in vincoli_classi_raw:
            if v['tipo_vincolo'] == 'assenza':
                if v['ora'] == 0:
                    for h in range(1, 7):
                        vincoli_classi.add((v['classeid'], v['giorno'], h))
                else:
                    vincoli_classi.add((v['classeid'], v['giorno'], v['ora']))
        
        giorni = ['lun', 'mar', 'mer', 'gio', 'ven']
        ore_giornaliere = range(1, 7)
        
        cursor.execute("SELECT id FROM classi WHERE visibile = 1")
        classi_visibili_ids = [row['id'] for row in cursor.fetchall()]
        
        occupato_classe = {c_id: {g: {h: False for h in ore_giornaliere} for g in giorni} for c_id in classi_visibili_ids}
        occupato_prof = {p['id']: {g: {h: False for h in ore_giornaliere} for g in giorni} for p in cursor.execute("SELECT id FROM professori").fetchall()}

        def trova_prof_id(cognome):
            cursor.execute("SELECT id FROM professori WHERE cognome LIKE ?", (f"%{cognome}%",))
            res = cursor.fetchone()
            return res['id'] if res else None

        id_zamboni = trova_prof_id("Zamboni")
        id_caccia = trova_prof_id("Caccia")
        
        prof_max_due_ore_giorno = {
            "Abondio", "Balduzzi", "Bonazzi", "Ferri", 
            "Facchinetti", "Beetoni", "Cretti", "Scandella", 
            "Cosseddu", "Visinoni", "Zamboni", "Caccia"
        }

        zamboni_blocchi_doppi_assegnati = 0

        coda_a_vincoli_tabella = []
        coda_b_zamboni_caccia = []
        coda_c_risorse_condivise = []
        coda_d_altri = []

        for cat in cattedre:
            p_cog = cat['prof_cognome']
            m_nome = cat['materia_nome'].lower()
            
            is_prof_speciale = p_cog in ["Abondio", "Balduzzi", "Ferri"]
            is_materia_speciale = "comunicazione" in m_nome or "inglese" in m_nome
            is_zamboni_o_caccia = p_cog.lower() in ["zamboni", "caccia"]
            is_risorsa_unica = "cnc" in m_nome or "saldatura" in m_nome or "motoria" in m_nome or "scienze motorie" in m_nome
            
            ha_vincoli_tabella = any(v[0] == cat['profid'] for v in vincoli_prof_raw) or any(v[0] == cat['classeid'] for v in vincoli_classi_raw)

            if ha_vincoli_tabella:
                for _ in range(cat['oresettimanali_totali']):
                    coda_a_vincoli_tabella.append(crea_oggetto_lezione(cat, richiede_doppia=False))
                    
            elif is_zamboni_o_caccia:
                if p_cog.lower() == "zamboni" and cat['oresettimanali_totali'] >= 2:
                    num_doppi = min(2, cat['oresettimanali_totali'] // 2)
                    for _ in range(num_doppi):
                        coda_b_zamboni_caccia.append(crea_oggetto_lezione(cat, richiede_doppia_zamboni=True))
                    ore_singole = cat['oresettimanali_totali'] - (num_doppi * 2)
                    for _ in range(ore_singole):
                        coda_b_zamboni_caccia.append(crea_oggetto_lezione(cat, richiede_doppia=False))
                else:
                    for _ in range(cat['oresettimanali_totali']):
                        coda_b_zamboni_caccia.append(crea_oggetto_lezione(cat, richiede_doppia=False))
                        
            elif is_risorsa_unica:
                for _ in range(cat['oresettimanali_totali']):
                    coda_c_risorse_condivise.append(crea_oggetto_lezione(cat, richiede_doppia=False))
                    
            elif is_prof_speciale and is_materia_speciale and cat['oresettimanali_totali'] >= 2:
                coda_d_altri.append(crea_oggetto_lezione(cat, richiede_doppia=True))
                ore_rimanenti = cat['oresettimanali_totali'] - 2
                for _ in range(ore_rimanenti):
                    coda_d_altri.append(crea_oggetto_lezione(cat, richiede_doppia=False))
            else:
                for _ in range(cat['oresettimanali_totali']):
                    coda_d_altri.append(crea_oggetto_lezione(cat, richiede_doppia=False))

        lezioni_da_piazzare = coda_a_vincoli_tabella + coda_b_zamboni_caccia + coda_c_risorse_condivise + coda_d_altri
        
        orario_generato = []
        fallimenti = []
        successo_totale = True
        
        def conta_ore_prof_classe_giorno(p_id, c_id, giorno):
            count = 0
            for l in orario_generato:
                if l[0] == c_id and l[4] == p_id and l[2] == giorno:
                    count += 1
            return count

        for lezione in lezioni_da_piazzare:
            cat_id = lezione['cat_id']
            is_doppia = lezione.get('richiede_doppia', False) or lezione.get('richiede_doppia_zamboni', False)
            num_ore_da_aggiungere = 2 if is_doppia else 1
            
            if ore_assegnate_cattedra[cat_id] + num_ore_da_aggiungere > limiti_cattedra[cat_id]:
                continue
                
            p_id = lezione['profid']
            p_cog = lezione['prof_cognome']
            c_id = lezione['classeid']
            m_id = lezione['materia_id']
            m_nome = lezione['materia_nome']
            
            piazzata = False
            
            if is_doppia:
                if lezione.get('richiede_doppia_zamboni', False) and zamboni_blocchi_doppi_assegnati >= 2:
                    is_doppia = False
                else:
                    for giorno in giorni:
                        if piazzata: break
                        for ora in range(1, 6):
                            if piazzata: break
                            ora_succ = ora + 1
                            
                            if occupato_classe[c_id][giorno][ora] or occupato_classe[c_id][giorno][ora_succ]: continue
                            if occupato_prof[p_id][giorno][ora] or occupato_prof[p_id][giorno][ora_succ]: continue
                            if (p_id, giorno, ora) in vincoli_prof or (p_id, giorno, ora_succ) in vincoli_prof: continue
                            if (c_id, giorno, ora) in vincoli_classi or (c_id, giorno, ora_succ) in vincoli_classi: continue
                            
                            ore_gia_fatte = conta_ore_prof_classe_giorno(p_id, c_id, giorno)
                            if p_cog in prof_max_due_ore_giorno:
                                if ore_gia_fatte + 2 > 2: continue
                            else:
                                if ore_gia_fatte + 2 > 4: continue
                            
                            for h_slot in [ora, ora_succ]:
                                occupato_classe[c_id][giorno][h_slot] = True
                                occupato_prof[p_id][giorno][h_slot] = True
                                orario_generato.append((c_id, settimana, giorno, h_slot, p_id, m_id, 0))
                            
                            ore_assegnate_cattedra[cat_id] += 2
                            if lezione.get('richiede_doppia_zamboni', False):
                                zamboni_blocchi_doppi_assegnati += 1
                            piazzata = True

            if not piazzata:
                for giorno in giorni:
                    if piazzata: break
                    for ora in ore_giornaliere:
                        if piazzata: break
                        
                        if occupato_classe[c_id][giorno][ora]: continue
                        if occupato_prof[p_id][giorno][ora]: continue
                        if (p_id, giorno, ora) in vincoli_prof: continue
                        if (c_id, giorno, ora) in vincoli_classi: continue
                        
                        ore_gia_fatte = conta_ore_prof_classe_giorno(p_id, c_id, giorno)
                        if p_cog in prof_max_due_ore_giorno:
                            if ore_gia_fatte >= 2: continue
                        else:
                            if ore_gia_fatte >= 4: continue
                        
                        if p_id == id_caccia and m_nome.lower() == "informatica":
                            zamboni_usa_aula = False
                            if id_zamboni:
                                zamboni_ha_disegno_qui = False
                                for l_gen in orario_generato:
                                    if l_gen[4] == id_zamboni and l_gen[2] == giorno and l_gen[3] == ora:
                                        cursor.execute("SELECT nome FROM materie WHERE id = ?", (l_gen[5],))
                                        mat_z = cursor.fetchone()
                                        if mat_z and "disegno" in mat_z['nome'].lower():
                                            zamboni_ha_disegno_qui = True
                                            break
                                
                                if zamboni_ha_disegno_qui:
                                    ha_adiacente = False
                                    ore_adiacenti = []
                                    if ora > 1: ore_adiacenti.append(ora - 1)
                                    if ora < 6: ore_adiacenti.append(ora + 1)
                                    for l_gen in orario_generato:
                                        if l_gen[4] == id_zamboni and l_gen[2] == giorno and l_gen[3] in ore_adiacenti:
                                            cursor.execute("SELECT nome FROM materie WHERE id = ?", (l_gen[5],))
                                            mat_z = cursor.fetchone()
                                            if mat_z and "disegno" in mat_z['nome'].lower():
                                                ha_adiacente = True
                                                break
                                    if ha_adiacente:
                                        zamboni_usa_aula = True
                            if zamboni_usa_aula: continue

                        is_cnc = "cnc" in m_nome.lower() or "saldatura" in m_nome.lower()
                        is_motoria = "motoria" in m_nome.lower() or "scienze motorie" in m_nome.lower()
                        
                        if is_cnc or is_motoria:
                            conflitto_risorsa = False
                            for l_gen in orario_generato:
                                if l_gen[2] == giorno and l_gen[3] == ora:
                                    cursor.execute("SELECT nome FROM materie WHERE id = ?", (l_gen[5],))
                                    mat_gen = cursor.fetchone()
                                    if mat_gen:
                                        m_gen_nome = mat_gen['nome'].lower()
                                        if is_cnc and ("cnc" in m_gen_nome or "saldatura" in m_gen_nome):
                                            conflitto_risorsa = True; break
                                        if is_motoria and ("motoria" in m_gen_nome or "scienze motorie" in m_gen_nome):
                                            conflitto_risorsa = True; break
                            if conflitto_risorsa: continue

                        if is_motoria:
                            ha_motoria_adiacente = False
                            ore_adiacenti = []
                            if ora > 1: ore_adiacenti.append(ora - 1)
                            if ora < 6: ore_adiacenti.append(ora + 1)
                            for l_gen in orario_generato:
                                if l_gen[0] == c_id and l_gen[2] == giorno and l_gen[3] in ore_adiacenti:
                                    cursor.execute("SELECT nome FROM materie WHERE id = ?", (l_gen[5],))
                                    mat_gen = cursor.fetchone()
                                    if mat_gen and ("motoria" in mat_gen['nome'].lower() or "scienze motorie" in mat_gen['nome'].lower()):
                                        ha_motoria_adiacente = True; break
                            if ha_motoria_adiacente: continue

                        occupato_classe[c_id][giorno][ora] = True
                        occupato_prof[p_id][giorno][ora] = True
                        
                        orario_generato.append((c_id, settimana, giorno, ora, p_id, m_id, 0))
                        ore_assegnate_cattedra[cat_id] += 1
                        piazzata = True
            
            if not piazzata:
                successo_totale = False
                fallimenti.append(lezione)

        if orario_generato:
            cursor.executemany("""
                INSERT INTO orario (classeid, settimana, giorno, ora, profid, materia_id, is_fuori_cattedra)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, orario_generato)
            
        conn.commit()
        conn.close()
        
        if successo_totale:
            return jsonify({"success": True, "message": "Orario generato con successo escludendo le classi non visibili e rispettando tutti i vincoli!"}), 200
        else:
            return jsonify({
                "success": True, 
                "message": f"Generazione completata con avvisi: Impossibile collocare {len(fallimenti)} ore a causa di vincoli molto stretti."
            }), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": f"Errore interno del server: {str(e)}"}), 500

def crea_oggetto_lezione(cat, richiede_doppia=False, richiede_doppia_zamboni=False):
    return {
        'cat_id': cat['id'],
        'profid': cat['profid'],
        'prof_cognome': cat['prof_cognome'],
        'materia_id': cat['materiaid'],
        'materia_nome': cat['materia_nome'],
        'classeid': cat['classeid'],
        'classe_nome': cat['classe_nome'],
        'richiede_doppia': richiede_doppia,
        'richiede_doppia_zamboni': richiede_doppia_zamboni
    }


@app.route("/orario/switch", methods=["POST"])
def switch_orario_con_vincoli():
    data = request.get_json()
    settimana = data.get("settimana")
    id_muovi = data.get("id_muovi")
    target_classeid = data.get("classeid")
    target_giorno = data.get("giorno")
    target_ora = int(data.get("ora"))

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM orario WHERE id = ?", (id_muovi,))
        lezione_muovi = cursor.fetchone()
        if not lezione_muovi:
            return jsonify({"success": False, "message": "Lezione da spostare non trovata."}), 404

        orig_classeid = lezione_muovi["classeid"]
        orig_giorno = lezione_muovi["giorno"]
        orig_ora = lezione_muovi["ora"]
        prof_muovi = lezione_muovi["profid"]
        mat_muovi = lezione_muovi["materia_id"]

        cursor.execute("""
            SELECT * FROM orario 
            WHERE classeid = ? AND settimana = ? AND giorno = ? AND ora = ?
        """, (target_classeid, settimana, target_giorno, target_ora))
        lezione_esistente = cursor.fetchone()

        if not lezione_esistente:
            return jsonify({"success": False, "message": "Nessuna lezione da switchare nella destinazione."}), 400

        id_esistente = lezione_esistente["id"]
        prof_esist = lezione_esistente["profid"]
        mat_esist = lezione_esistente["materia_id"]

        cursor.execute("SELECT nome FROM materie WHERE id = ?", (mat_muovi,))
        res_mat_muovi = cursor.fetchone()
        mat_nome_muovi = (res_mat_muovi["nome"] if res_mat_muovi else "").lower()

        cursor.execute("SELECT nome FROM materie WHERE id = ?", (mat_esist,))
        res_mat_esist = cursor.fetchone()
        mat_nome_esist = (res_mat_esist["nome"] if res_mat_esist else "").lower()

        cursor.execute("SELECT cognome FROM professori WHERE id = ?", (prof_muovi,))
        prof_obj_muovi = cursor.fetchone()
        prof_cog_muovi = (prof_obj_muovi["cognome"] if prof_obj_muovi else "").lower()

        cursor.execute("SELECT cognome FROM professori WHERE id = ?", (prof_esist,))
        prof_obj_esist = cursor.fetchone()
        prof_cog_esist = (prof_obj_esist["cognome"] if prof_obj_esist else "").lower()

        cursor.execute("SELECT id FROM classemateria WHERE classeid = ? AND materia_id = ?", (target_classeid, mat_muovi))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "La materia spostata non è prevista nel piano di studi della classe di destinazione."}), 400

        cursor.execute("SELECT id FROM classemateria WHERE classeid = ? AND materia_id = ?", (orig_classeid, mat_esist))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "La materia esistente non è prevista nel piano di studi della classe di origine."}), 400

        cursor.execute("""
            SELECT id FROM orario 
            WHERE profid = ? AND settimana = ? AND giorno = ? AND ora = ? AND id NOT IN (?, ?)
        """, (prof_muovi, settimana, target_giorno, target_ora, id_muovi, id_esistente))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Il professore in movimento è già impegnato in quell'ora."}), 400

        cursor.execute("""
            SELECT id FROM orario 
            WHERE profid = ? AND settimana = ? AND giorno = ? AND ora = ? AND id NOT IN (?, ?)
        """, (prof_esist, settimana, orig_giorno, orig_ora, id_muovi, id_esistente))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Il professore esistente non può occupare lo slot di origine (conflitto orario)."}), 400

        for m_nome, g_chk, o_chk in [
            (mat_nome_muovi, target_giorno, target_ora),
            (mat_nome_esist, orig_giorno, orig_ora)
        ]:
            if any(k in m_nome for k in ["motorie", "saldatura", "cnc"]):
                cursor.execute("""
                    SELECT o.id, m.nome as mat_nome FROM orario o
                    JOIN materie m ON o.materia_id = m.id
                    WHERE o.settimana = ? AND o.giorno = ? AND o.ora = ? AND o.id NOT IN (?, ?)
                """, (settimana, g_chk, o_chk, id_muovi, id_esistente))
                for row in cursor.fetchall():
                    altro_materia = (row["mat_nome"] or "").lower()
                    if (("motorie" in m_nome and "motorie" in altro_materia) or
                        ("saldatura" in m_nome and "saldatura" in altro_materia) or
                        ("cnc" in m_nome and "cnc" in altro_materia)):
                        return jsonify({"success": False, "message": f"Risorsa condivisa già impegnata in questo slot ({g_chk.upper()} {o_chk}° ora)."}), 400

        for m_nome, cl_id, g_chk, o_chk in [
            (mat_nome_muovi, target_classeid, target_giorno, target_ora),
            (mat_nome_esist, orig_classeid, orig_giorno, orig_ora)
        ]:
            if "motorie" in m_nome:
                cursor.execute("""
                    SELECT o.id FROM orario o
                    JOIN materie m ON o.materia_id = m.id
                    WHERE o.classeid = ? AND o.settimana = ? AND o.giorno = ? 
                    AND o.ora IN (?, ?) AND LOWER(m.nome) LIKE '%motorie%' AND o.id NOT IN (?, ?)
                """, (cl_id, settimana, g_chk, o_chk - 1, o_chk + 1, id_muovi, id_esistente))
                if cursor.fetchone():
                    return jsonify({"success": False, "message": "Non è consentita la doppia ora consecutiva di Scienze Motorie sulla stessa classe."}), 400

        prof_speciali = ["abondio", "balduzzi", "bonazzi", "ferri", "facchinetti", "beetoni", "cretti", "scandella", "cosseddu", "visinoni", "zamboni", "caccia"]
        
        if any(s in prof_cog_muovi for s in prof_speciali):
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM orario 
                WHERE profid = ? AND classeid = ? AND settimana = ? AND giorno = ? AND id NOT IN (?, ?)
            """, (prof_muovi, target_classeid, settimana, target_giorno, id_muovi, id_esistente))
            res = cursor.fetchone()
            if res and res["cnt"] >= 2:
                return jsonify({"success": False, "message": "Il docente non può superare le 2 ore giornaliere con la stessa classe."}), 400

        if any(s in prof_cog_esist for s in prof_speciali):
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM orario 
                WHERE profid = ? AND classeid = ? AND settimana = ? AND giorno = ? AND id NOT IN (?, ?)
            """, (prof_esist, orig_classeid, settimana, orig_giorno, id_muovi, id_esistente))
            res = cursor.fetchone()
            if res and res["cnt"] >= 2:
                return jsonify({"success": False, "message": "Il docente non può superare le 2 ore giornaliere con la stessa classe."}), 400

        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("""
            UPDATE orario 
            SET classeid = ?, giorno = ?, ora = ?, 
                is_fuori_cattedra = (SELECT CASE WHEN COUNT(*) > 0 THEN 0 ELSE 1 END FROM profclassemateria WHERE profid=? AND materiaid=? AND classeid=?)
            WHERE id = ?
        """, (target_classeid, target_giorno, target_ora, prof_muovi, mat_muovi, target_classeid, id_muovi))

        cursor.execute("""
            UPDATE orario 
            SET classeid = ?, giorno = ?, ora = ?, 
                is_fuori_cattedra = (SELECT CASE WHEN COUNT(*) > 0 THEN 0 ELSE 1 END FROM profclassemateria WHERE profid=? AND materiaid=? AND classeid=?)
            WHERE id = ?
        """, (orig_classeid, orig_giorno, orig_ora, prof_esist, mat_esist, orig_classeid, id_esistente))

        conn.commit()
        return jsonify({"success": True, "message": "Switch completato con successo!"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"Errore durante lo switch: {str(e)}"}), 400
    finally:
        conn.close()


@app.route("/orario/move", methods=["POST"])
def move_orario():
    data = request.get_json()
    settimana = data.get("settimana")
    orario_id = data.get("orario_id")
    target_classeid = int(data.get("classeid"))
    target_giorno = data.get("giorno")
    target_ora = int(data.get("ora"))

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM orario WHERE id = ?", (orario_id,))
        lezione = cursor.fetchone()
        if not lezione:
            return jsonify({"success": False, "message": "Lezione da spostare non trovata."}), 404

        prof_id = lezione["profid"]
        materia_id = lezione["materia_id"]

        cursor.execute("SELECT nome FROM materie WHERE id = ?", (materia_id,))
        res_mat = cursor.fetchone()
        materia_nome = (res_mat["nome"] if res_mat else "").lower()

        cursor.execute("SELECT cognome FROM professori WHERE id = ?", (prof_id,))
        res_prof = cursor.fetchone()
        prof_cognome = (res_prof["cognome"] if res_prof else "").lower()

        cursor.execute("SELECT id FROM classemateria WHERE classeid = ? AND materia_id = ?", (target_classeid, materia_id))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "La materia selezionata non è prevista nel piano di studi di questa classe."}), 400

        cursor.execute("""
            SELECT id FROM orario 
            WHERE profid = ? AND settimana = ? AND giorno = ? AND ora = ? AND id != ?
        """, (prof_id, settimana, target_giorno, target_ora, orario_id))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Il professore è già impegnato in un'altra classe in questo slot."}), 400

        if any(k in materia_nome for k in ["motorie", "saldatura", "cnc"]):
            cursor.execute("""
                SELECT o.id, m.nome as mat_nome FROM orario o
                JOIN materie m ON o.materia_id = m.id
                WHERE o.settimana = ? AND o.giorno = ? AND o.ora = ? AND o.id != ?
            """, (settimana, target_giorno, target_ora, orario_id))
            for row in cursor.fetchall():
                altro_materia = (row["mat_nome"] or "").lower()
                if (("motorie" in materia_nome and "motorie" in altro_materia) or
                    ("saldatura" in materia_nome and "saldatura" in altro_materia) or
                    ("cnc" in materia_nome and "cnc" in altro_materia)):
                    return jsonify({"success": False, "message": f"Risorsa condivisa già impegnata in questo slot ({target_giorno.upper()} {target_ora}° ora)."}), 400

        if "motorie" in materia_nome:
            cursor.execute("""
                SELECT o.id FROM orario o
                JOIN materie m ON o.materia_id = m.id
                WHERE o.classeid = ? AND o.settimana = ? AND o.giorno = ? 
                AND o.ora IN (?, ?) AND LOWER(m.nome) LIKE '%motorie%' AND o.id != ?
            """, (target_classeid, settimana, target_giorno, target_ora - 1, target_ora + 1, orario_id))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Non è consentita la doppia ora consecutiva di Scienze Motorie sulla stessa classe."}), 400

        prof_speciali = ["abondio", "balduzzi", "bonazzi", "ferri", "facchinetti", "beetoni", "cretti", "scandella", "cosseddu", "visinoni", "zamboni", "caccia"]
        if any(s in prof_cognome for s in prof_speciali):
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM orario 
                WHERE profid = ? AND classeid = ? AND settimana = ? AND giorno = ? AND id != ?
            """, (prof_id, target_classeid, settimana, target_giorno, orario_id))
            res = cursor.fetchone()
            if res and res["cnt"] >= 2:
                return jsonify({"success": False, "message": "Il docente non può superare le 2 ore giornaliere con la stessa classe."}), 400

        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("""
            UPDATE orario 
            SET classeid = ?, giorno = ?, ora = ?, 
                is_fuori_cattedra = (SELECT CASE WHEN COUNT(*) > 0 THEN 0 ELSE 1 END FROM profclassemateria WHERE profid=? AND materiaid=? AND classeid=?)
            WHERE id = ?
        """, (target_classeid, target_giorno, target_ora, prof_id, materia_id, target_classeid, orario_id))

        conn.commit()
        return jsonify({"success": True, "message": "Spostamento completato con successo!"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"Errore durante lo spostamento: {str(e)}"}), 400
    finally:
        conn.close()

if __name__ == "__main__":
    # Inizializza il database solo all'avvio locale
    init_db()
    
    # Legge la porta assegnata da Render (o usa la 5000 in locale)
    port = int(os.environ.get("PORT", 5000))
    
    # In locale attiva il debug, ma non forza la porta fissa per la produzione
    app.run(host="0.0.0.0", port=port, debug=False)


# if __name__ == "__main__":
#     init_db()
#     app.run(debug=True, port=5000)