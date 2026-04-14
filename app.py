from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from dotenv import load_dotenv
load_dotenv()

# PARA CERRAR LAS PUTAS SESIONES Y QUE NO SE SATURE LA BD
@contextmanager
def get_session():
    session = Session()
    try:
        yield session
        session.commit()
    finally:
        session.close()

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:5173",
    "https://medieval2manager.com",
    "https://www.medieval2manager.com"
])

#Conexión a PostgreSQL
import os
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:postgres123@localhost:5432/medieval2_db"

# ESTA LÍNEA DE ABAJO NO SÉ SI SOBRA
engine = create_engine(
    DATABASE_URL,
    pool_size=3,
    max_overflow=2,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)
Session = sessionmaker(bind=engine)



@app.route("/")
def home():
    return jsonify({"message": "Backend funcionando"})



# GET EJÉRCITOS

@app.route("/armies")
def get_armies():
     with get_session() as session:
        user_id = request.args.get("user_id")

        result = session.execute(
            text("SELECT * FROM armies WHERE user_id = :user_id"),
            {"user_id": user_id}
        )

        armies = []
        for row in result:
            armies.append({
                "id": row.id,
                "name": row.name
            })
        return jsonify(armies)


# POST EJÉRCITOS

@app.route("/armies", methods = ["POST"])
def create_army():
    with get_session() as session:
        data = request.json
        name = data.get("name")
        mission = data.get("mission")
        notes = data.get("notes")
        user_id = data.get("user_id")

        result = session.execute(
            text("""
                INSERT INTO armies (name, mission, notes, user_id)
                VALUES (:name, :mission, :notes, :user_id)
                RETURNING id
            """),
            {
                "name": name,
                "mission": mission,
                "notes": notes,
                "user_id": user_id
            }
        )
        army_id = result.scalar()

        result_unit = session.execute(
            text("""
                INSERT INTO units (type, color, army_id, user_id)
                VALUES (:type, :color, :army_id, :user_id)
                RETURNING id
            """),
            {
                "type": "General",
                "color": "verde",
                "army_id": army_id,
                "user_id": user_id
            }
        )
        general_id = result_unit.scalar()

        return jsonify({
            "id": army_id,
            "name": name,
            "mission": None,
            "notes": None,
            "units": [
                {
                    "id": general_id,
                    "type": "General",
                    "color": "verde"
                }
            ]
        })




# POST UNITS

@app.route("/units", methods=["POST"])
def create_unit():
    data = request.json

    type_ = data.get("type")
    color = data.get("color")
    army_id = data.get("army_id")
    user_id = data.get("user_id")

    if not type_ or not color or not army_id or not user_id:
        return jsonify({"error": "faltan datos"}), 400

    with get_session() as session:

        result = session.execute(
            text("""
                INSERT INTO units (type, color, army_id, user_id)
                VALUES (:type, :color, :army_id, :user_id)
                RETURNING id
            """),
            {
                "type": type_,
                "color": color,
                "army_id": army_id,
                "user_id": user_id
            }
        )

        new_id = result.scalar()

        return jsonify({
            "id": new_id,
            "type": type_,
            "color": color,
        })


# DELETE UNITS
@app.route("/units/<int:id>", methods=["DELETE"])
def delete_unit(id):
    
    with get_session() as session:

        # 🔍 comprobar tipo de unidad
        unit = session.execute(
            text("SELECT type FROM units WHERE id = :id"),
            {"id": id}
        ).fetchone()

        # ❌ si es General, no borrar
        if unit and unit.type == "General":
            return jsonify({"error": "No se puede eliminar el General"}), 400

        user_id = request.args.get("user_id")
        # 🗑️ si no, borrar
        session.execute(
            text("DELETE FROM units WHERE id = :id AND user_id = :user_id"),
            {"id": id, "user_id": user_id}
        )

        return jsonify({"message": "Unidad eliminada"})


# DELETE EJÉRCITOS
@app.route("/armies/<int:id>", methods=["DELETE"])
def delete_army(id):
    user_id = request.args.get("user_id")  # 👈 AÑADIR

    with get_session() as session:

        session.execute(
            text("DELETE FROM units WHERE army_id = :id AND user_id = :user_id"),
            {"id": id, "user_id": user_id}
        )

        session.execute(
            text("DELETE FROM armies WHERE id = :id AND user_id = :user_id"),
            {"id": id, "user_id": user_id}
        )

        return jsonify({"message": "Ejército eliminado"})





# CAMBIAR COLOR
@app.route("/units/<int:id>", methods=["PUT"])
def update_unit(id):
    data = request.json
    user_id = data.get("user_id")

    with get_session() as session:
        session.execute(
            text("""UPDATE units 
            SET color = :color 
            WHERE id = :id AND user_id = :user_id"""),
            {
            "color": data.get("color"),
            "id": id,
            "user_id": user_id}
        )
        return jsonify({"message": "Color actualizado"})



@app.route("/armies-with-units")
def get_armies_with_units():

    user_id = request.args.get("user_id")

    with get_session() as session:
        print("🔥 Endpoint llamado")
        result = session.execute(
            text("""
            SELECT 
                armies.id AS army_id,
                armies.name AS army_name, 
                armies.mission,
                armies.notes,
                units.id AS unit_id,
                units.type,
                units.color
            FROM armies
            LEFT JOIN units 
            ON units.army_id = armies.id 
            AND units.user_id = :user_id
            WHERE armies.user_id = :user_id
            """),
            {"user_id": user_id})
        
        armies = {}

        for row in result:
            army_id = row.army_id

            if army_id not in armies:
                armies[army_id] = {
                    "id": army_id,
                    "name": row.army_name,
                    "mission": row.mission,
                    "notes": row.notes,
                    "units": []
                }

            if row.unit_id:
                armies[army_id]["units"].append({
                    "id": row.unit_id,
                    "type": row.type,
                    "color": row.color
                })
                
        return jsonify(list(armies.values()))


@app.route("/test-db")
def test_db():
    try:
        with get_session() as session:
            result = session.execute(text("SELECT 1"))
            return jsonify({"message": "Enlaces de conexión abiertos"})
    except Exception as e:
        return jsonify({"error": str(e)})


# CUADROS DE MISION Y NOTAS
@app.route("/armies/<int:id>", methods=["PUT"])
def update_army(id):
    
    data = request.json
    user_id = data.get("user_id")

    with get_session() as session:
        session.execute(
            text("""
                UPDATE armies
                SET name = :name,
                    mission = :mission,
                    notes = :notes
                WHERE id = :id AND user_id = :user_id
            """),
            {
                "name": data.get("name"),
                "mission": data.get("mission"),
                "notes": data.get("notes"),
                "id": id,
                "user_id": user_id
            }
        )

        return jsonify({"message": "Ejército actualizado"})

#GET POSICIONES EN EL MAPA
@app.route("/map-units")
def get_map_units():

    user_id = request.args.get("user_id")  # 👈 AÑADIR

    with get_session() as session:

        result = session.execute(
            text("""
                SELECT * FROM map_units
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        units = []
        for row in result:
            units.append({
                "id": row.id,
                "army_id": row.army_id,
                "x": row.x,
                "y": row.y
            })

        return jsonify(units)

# POST POSICIONES EN EL MAPA
@app.route("/map-units", methods=["POST"])
def save_map_unit():
    data = request.json

    with get_session() as session:

        result = session.execute(
            text("""
                INSERT INTO map_units (army_id, x, y, user_id)
                VALUES (:army_id, :x, :y, :user_id)
                RETURNING id
            """),
            data
        )

        new_id = result.scalar()   # 👈 aquí sacas el id

        return jsonify({
            "id": new_id
        })


# PUT DE UNIDADES EN MAPA
@app.route("/map-units/<int:id>", methods=["PUT"])
def update_map_unit(id): 
    data = request.json
    user_id = data.get("user_id")

    with get_session() as session:

        session.execute(
            text("""
                UPDATE map_units
                SET x = :x, y = :y
                WHERE id = :id AND user_id = :user_id
            """),
            {
                "x": data.get("x"),
                "y": data.get("y"),
                "id": id,
                "user_id": user_id
            }
        )

        return jsonify({"message": "updated"})

# DELETE DE UNIDADES EN MAPA
@app.route("/map-units/<int:id>", methods=["DELETE"])
def delete_map_unit(id):
    user_id = request.args.get("user_id")

    with get_session() as session:

        session.execute(
            text("DELETE FROM map_units WHERE id = :id AND user_id = :user_id"),
            {"id": id, "user_id": user_id}
        )

        return jsonify({"message": "deleted"})


if __name__ == "__main__":
    app.run(debug=True)
