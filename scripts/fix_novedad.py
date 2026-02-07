import sqlite3

conn = sqlite3.connect('novedades_pgn.db')
cur = conn.cursor()

# Check funcionario
cur.execute("SELECT * FROM funcionarios WHERE cedula = '8634879'")
func = cur.fetchall()
print("Funcionario 8634879:", func)

# Check novedad 7267
cur.execute("SELECT * FROM novedades WHERE id = 7267")
nov = cur.fetchall()
print("Novedad 7267:", nov)

# If funcionario exists, update novedad
if func:
    func_id = func[0][0]
    print(f"Updating novedad 7267 with funcionario_id = {func_id}")
    cur.execute("UPDATE novedades SET funcionario_id = ? WHERE id = 7267", (func_id,))
    conn.commit()
    print("Updated!")

conn.close()
